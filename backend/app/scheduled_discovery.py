"""Durable scheduling and scope policy for approved scholarship sources."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .database import SessionLocal
from .models import DiscoveredCandidate, IngestionRun, ScheduledScan, ScheduledSource
from .orchestration import IngestionSubmission, create_ingestion_run
from .source_acquisition import AcquiredSource, ValidatedUrl, WebSourceRequest, validate_source_url


LOGGER = logging.getLogger("pathaid.scheduler")
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC time; scheduler tests inject fixed time."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SchedulerConfig:
    """Small bounded scheduler controls loaded from deployment settings."""

    poll_seconds: float = 60.0
    batch_size: int = 25
    user_agent: str = "PathaidBot/1.0"

    @classmethod
    def from_env(cls) -> "SchedulerConfig":
        return cls(
            poll_seconds=_positive_float("PATHAID_SCHEDULER_POLL_SECONDS", 60),
            batch_size=_bounded_int("PATHAID_SCHEDULER_BATCH_SIZE", 25, 1, 100),
            user_agent=os.environ.get("PATHAID_SCHEDULER_USER_AGENT", "PathaidBot/1.0").strip() or "PathaidBot/1.0",
        )


def normalize_source_policy(url: str, allowed_path_prefix: str | None) -> tuple[str, str, str]:
    """Return a canonical URL, hostname, and normalized allowed path."""

    validated = validate_source_url(url)
    path = allowed_path_prefix or urlsplit(validated.url).path or "/"
    if not path.startswith("/") or "?" in path or "#" in path:
        raise ValueError("allowed_path_prefix must be an absolute URL path")
    return validated.url, validated.hostname, path


def enqueue_due_sources(
    db: Session,
    *,
    clock: Clock = utc_now,
    limit: int = 25,
) -> list[IngestionRun]:
    """Create at most one ingestion run for each due source/window."""

    current = clock()
    due = list(
        db.scalars(
            select(ScheduledSource)
            .where(ScheduledSource.enabled.is_(True), ScheduledSource.next_scan_at <= current)
            .order_by(ScheduledSource.next_scan_at, ScheduledSource.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    runs: list[IngestionRun] = []
    claimed_hosts: set[str] = set()
    for source in due:
        # One source per host per cycle provides a deployment-configurable
        # minimum delay without coordinating timers in worker memory.
        if source.allowed_hostname in claimed_hosts:
            continue
        claimed_hosts.add(source.allowed_hostname)
        window = _aware(source.next_scan_at)
        existing = db.scalar(
            select(ScheduledScan).where(
                ScheduledScan.source_id == source.id,
                ScheduledScan.window_start == window,
            )
        )
        if existing is None:
            scan = ScheduledScan(source_id=source.id, window_start=window, outcome="queued")
            db.add(scan)
            db.flush()
            key = f"scheduled:{source.id}:{window.isoformat()}"
            run = create_ingestion_run(
                db,
                IngestionSubmission(
                    key,
                    WebSourceRequest(source.canonical_url),
                    source.target_program_id,
                    scheduled_source_id=source.id,
                    scheduled_scan_id=scan.id,
                ),
                commit=False,
            )
            runs.append(run)
        source.next_scan_at = _next_scan(source, current)
    # Commit the whole claimed batch together. Committing inside the loop would
    # release PostgreSQL row locks while later sources were still being handled.
    try:
        db.commit()
    except IntegrityError:
        # The source/window unique constraint is the final concurrency guard on
        # databases that do not support SKIP LOCKED (including SQLite tests).
        db.rollback()
        return []
    return runs


def allowed_candidate_urls(source: ScheduledSource, acquired: AcquiredSource) -> list[str]:
    """Canonicalize links and enforce the configured one-hop discovery scope."""

    if source.source_type != "discovery_page" or source.discovery_link_limit == 0:
        return []
    accepted: list[str] = []
    seen: set[str] = set()
    for href in acquired.discovered_links:
        try:
            candidate = validate_source_url(urljoin(acquired.final_url, href))
        except Exception:
            continue
        if not source_url_in_scope(source, candidate):
            continue
        if candidate.url in seen or candidate.url == acquired.final_url:
            continue
        seen.add(candidate.url)
        accepted.append(candidate.url)
        if len(accepted) >= source.discovery_link_limit:
            break
    return accepted


def source_url_in_scope(source: ScheduledSource, candidate: ValidatedUrl) -> bool:
    """Return whether a validated URL stays inside an approved source scope."""

    path = urlsplit(candidate.url).path or "/"
    return candidate.hostname == source.allowed_hostname and _path_in_scope(path, source.allowed_path_prefix)


def create_candidate_runs(
    db: Session,
    source: ScheduledSource,
    scan: ScheduledScan,
    urls: list[str],
) -> int:
    """Persist deduplicated private candidates and queue their acquisition."""

    created = 0
    for url in urls:
        candidate = db.scalar(
            select(DiscoveredCandidate).where(
                DiscoveredCandidate.source_id == source.id,
                DiscoveredCandidate.canonical_url == url,
            )
        )
        if candidate is not None:
            continue
        candidate = DiscoveredCandidate(source_id=source.id, first_scan_id=scan.id, canonical_url=url, status="queued")
        db.add(candidate)
        db.flush()
        key_hash = hashlib.sha256(url.encode()).hexdigest()[:24]
        create_ingestion_run(
            db,
            IngestionSubmission(
                f"candidate:{source.id}:{key_hash}",
                WebSourceRequest(url),
                scheduled_source_id=source.id,
                discovered_candidate_id=candidate.id,
            ),
            commit=False,
        )
        created += 1
    return created


def robots_allows(source: ScheduledSource, robots_text: str, target_url: str, user_agent: str) -> bool:
    """Evaluate a safely acquired robots file without performing network I/O."""

    if not source.respect_robots:
        return True
    parser = RobotFileParser()
    parser.set_url(f"{urlsplit(source.canonical_url).scheme}://{source.allowed_hostname}/robots.txt")
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(user_agent, target_url)


def scheduler_cycle(session_factory: sessionmaker = SessionLocal, *, config: SchedulerConfig, clock: Clock = utc_now) -> int:
    """Enqueue one bounded batch and return its size."""

    with session_factory() as db:
        return len(enqueue_due_sources(db, clock=clock, limit=config.batch_size))


def run_forever(session_factory: sessionmaker = SessionLocal, *, config: SchedulerConfig) -> None:
    """Poll durable schedules until interrupted."""

    while True:
        scheduler_cycle(session_factory, config=config)
        time.sleep(config.poll_seconds)


def main() -> None:
    """Run one scheduling cycle or continuously."""

    parser = argparse.ArgumentParser(description="Schedule approved Pathaid source scans")
    parser.add_argument("--once", action="store_true", help="Enqueue one due batch and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = SchedulerConfig.from_env()
    if args.once:
        scheduler_cycle(config=config)
    else:
        try:
            run_forever(config=config)
        except KeyboardInterrupt:
            LOGGER.info("scheduler_stopped")


def _next_scan(source: ScheduledSource, current: datetime) -> datetime:
    """Advance the prior window without drifting after a delayed cycle."""

    next_scan = _aware(source.next_scan_at) + timedelta(hours=source.cadence_hours)
    while next_scan <= current:
        next_scan += timedelta(hours=source.cadence_hours)
    return next_scan


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _path_in_scope(path: str, prefix: str) -> bool:
    """Match a path segment boundary so ``/awards`` excludes ``/awards-old``."""

    boundary = prefix.rstrip("/") or "/"
    return path.startswith("/") if boundary == "/" else path == boundary or path.startswith(f"{boundary}/")


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be positive") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be between {minimum} and {maximum}") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


if __name__ == "__main__":
    main()
