"""Durable submission, leasing, retry, and transition helpers for ingestion."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import IngestionRun, Program
from .source_acquisition import PastedSourceRequest, WebSourceRequest


ACTIVE_STATES = ("queued", "acquiring", "extracting", "validating")
TERMINAL_STATES = ("published", "rejected", "failed")


class OrchestrationError(Exception):
    """Safe workflow coordination error for a caller or future admin API."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class OrchestrationConfig:
    """Bounded worker behavior shared by claiming and stage execution."""

    lease_seconds: int = 120
    maximum_stage_attempts: int = 3
    retry_base_seconds: int = 5


@dataclass(frozen=True)
class IngestionSubmission:
    """Internal request used later by the protected administrator API."""

    idempotency_key: str
    source: WebSourceRequest | PastedSourceRequest
    target_program_id: str | None = None


@dataclass(frozen=True)
class RunLease:
    """Fencing token proving one worker currently owns a run."""

    run_id: str
    worker_id: str
    token: str
    expires_at: datetime


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC timestamp; tests inject a fixed clock instead."""

    return datetime.now(timezone.utc)


def create_ingestion_run(db: Session, submission: IngestionSubmission) -> IngestionRun:
    """Persist or idempotently return one queued ingestion request."""

    key = submission.idempotency_key.strip()
    if not key or len(key) > 200:
        raise OrchestrationError("invalid_idempotency_key", "A valid idempotency key is required.")
    if submission.target_program_id and db.get(Program, submission.target_program_id) is None:
        raise OrchestrationError("program_not_found", "The target program does not exist.")

    method = "pasted_text" if isinstance(submission.source, PastedSourceRequest) else "webpage"
    source_text = submission.source.source_text if isinstance(submission.source, PastedSourceRequest) else None
    fingerprint = _submission_fingerprint(method, submission.source.source_url, source_text, submission.target_program_id)
    existing = db.scalar(select(IngestionRun).where(IngestionRun.idempotency_key == key))
    if existing is not None:
        return _same_request_or_conflict(existing, fingerprint)

    run = IngestionRun(
        idempotency_key=key,
        request_fingerprint=fingerprint,
        target_program_id=submission.target_program_id,
        source_url=submission.source.source_url,
        source_method=method,
        input_source_text=source_text,
        state="queued",
        validation_findings=[],
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent submission may have won the unique-key race. Fetch it
        # after rollback and apply the same fingerprint conflict rule.
        db.rollback()
        existing = db.scalar(select(IngestionRun).where(IngestionRun.idempotency_key == key))
        if existing is None:
            raise
        return _same_request_or_conflict(existing, fingerprint)
    db.refresh(run)
    return run


def claim_next_run(
    db: Session,
    worker_id: str,
    config: OrchestrationConfig = OrchestrationConfig(),
    *,
    clock: Clock = utc_now,
) -> RunLease | None:
    """Atomically lease the oldest due run and fence competing workers."""

    if not worker_id.strip():
        raise OrchestrationError("invalid_worker", "A worker identifier is required.")
    current = clock()
    candidates = list(
        db.scalars(
            select(IngestionRun.id)
            .where(
                IngestionRun.state.in_(ACTIVE_STATES),
                or_(IngestionRun.next_attempt_at.is_(None), IngestionRun.next_attempt_at <= current),
                or_(IngestionRun.lease_expires_at.is_(None), IngestionRun.lease_expires_at <= current),
            )
            .order_by(IngestionRun.created_at, IngestionRun.id)
            .limit(20)
        )
    )
    for run_id in candidates:
        token = secrets.token_hex(32)
        expiry = current + timedelta(seconds=config.lease_seconds)
        claimed = db.execute(
            update(IngestionRun)
            .where(
                IngestionRun.id == run_id,
                IngestionRun.state.in_(ACTIVE_STATES),
                or_(IngestionRun.next_attempt_at.is_(None), IngestionRun.next_attempt_at <= current),
                or_(IngestionRun.lease_expires_at.is_(None), IngestionRun.lease_expires_at <= current),
            )
            .values(
                state="acquiring" if db.get(IngestionRun, run_id).state == "queued" else db.get(IngestionRun, run_id).state,
                lease_owner=worker_id,
                lease_token=token,
                lease_expires_at=expiry,
                next_attempt_at=None,
                updated_at=current,
            )
        )
        if claimed.rowcount == 1:
            db.commit()
            return RunLease(run_id, worker_id, token, expiry)
        db.rollback()
    return None


def require_lease(db: Session, lease: RunLease, *, clock: Clock = utc_now) -> IngestionRun:
    """Load a run only when the caller still owns its unexpired lease."""

    run = db.get(IngestionRun, lease.run_id)
    expiry = _aware(run.lease_expires_at) if run is not None else None
    if run is None or run.lease_owner != lease.worker_id or run.lease_token != lease.token or expiry is None or expiry <= clock():
        raise OrchestrationError("lease_lost", "The worker no longer owns this ingestion run.")
    return run


def release_lease(run: IngestionRun) -> None:
    """Clear ownership after a stage transition or scheduled retry."""

    run.lease_owner = None
    run.lease_token = None
    run.lease_expires_at = None


def create_manual_retry(
    db: Session,
    failed_run_id: str,
    idempotency_key: str,
) -> IngestionRun:
    """Create a linked run and reuse a previously acquired snapshot when safe."""

    failed = db.get(IngestionRun, failed_run_id)
    if failed is None:
        raise OrchestrationError("run_not_found", "The ingestion run does not exist.")
    if failed.state != "failed":
        raise OrchestrationError("run_not_failed", "Only failed ingestion runs can be retried manually.")
    source = (
        PastedSourceRequest(failed.source_url, failed.input_source_text or "")
        if failed.source_method == "pasted_text"
        else WebSourceRequest(failed.source_url)
    )
    retry = create_ingestion_run(
        db,
        IngestionSubmission(idempotency_key=idempotency_key, source=source, target_program_id=failed.target_program_id),
    )
    if retry.parent_run_id is None:
        retry.parent_run_id = failed.id
        if failed.source_snapshot_id:
            # A new model call can repair extraction/validation while avoiding
            # another network acquisition of an already retained source.
            retry.source_snapshot_id = failed.source_snapshot_id
            retry.state = "extracting"
        db.commit()
        db.refresh(retry)
    return retry


def retry_delay(config: OrchestrationConfig, completed_attempts: int) -> timedelta:
    """Return bounded exponential backoff after a transient stage failure."""

    return timedelta(seconds=config.retry_base_seconds * (2 ** max(0, completed_attempts - 1)))


def _submission_fingerprint(method: str, url: str, text: str | None, program_id: str | None) -> str:
    """Hash canonical input so idempotency conflicts do not echo source text."""

    encoded = json.dumps(
        {"method": method, "url": url, "text": text, "target_program_id": program_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _same_request_or_conflict(run: IngestionRun, fingerprint: str) -> IngestionRun:
    """Return a duplicate request or fail safely when its payload differs."""

    if run.request_fingerprint != fingerprint:
        raise OrchestrationError("idempotency_conflict", "The idempotency key was already used for different input.")
    return run


def _aware(value: datetime | None) -> datetime | None:
    """Treat SQLite's naive test timestamps as UTC."""

    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
