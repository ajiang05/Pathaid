"""Bounded generic-directory traversal and immutable snapshot persistence."""

from __future__ import annotations

import time
import urllib.robotparser
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Callable, Protocol
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import select

from .database import Database
from .models import SourceScanRun, SourceScope, SourceSnapshot
from .source_acquisition import (
    AcquisitionConfig,
    AcquisitionError,
    AcquiredSource,
    Resolver,
    SingleHopTransport,
    WebSourceRequest,
    acquire_web_source,
    validate_source_url,
)
from .source_registry import RegistryError, path_is_within


SCHOLARSHIP_TERMS = ("scholarship", "scholarships", "fellowship", "fellowships", "financial aid", "financial-aid", "award")
ROBOTS_USER_AGENT = "PathAid"


@dataclass(frozen=True)
class ScopeBoundary:
    id: str
    canonical_url: str
    hostname: str
    allowed_path_prefix: str
    max_depth: int
    page_budget: int
    requests_per_minute: int
    scan_interval_hours: int

    def allows(self, raw_url: str) -> bool:
        try:
            candidate = validate_source_url(raw_url)
        except AcquisitionError:
            return False
        return candidate.hostname == self.hostname and path_is_within(urlsplit(candidate.url).path, self.allowed_path_prefix)


class PageFetcher(Protocol):
    def fetch(self, url: str, boundary: ScopeBoundary) -> AcquiredSource: ...


class RobotsPolicy(Protocol):
    def allowed(self, url: str) -> bool: ...


@dataclass(frozen=True)
class TraversedPage:
    depth: int
    acquired: AcquiredSource


@dataclass(frozen=True)
class TraversalResult:
    pages: tuple[TraversedPage, ...]
    truncated: bool


class TraversalFailure(AcquisitionError):
    def __init__(self, source: AcquisitionError, pages_attempted: int):
        super().__init__(source.code, source.safe_message, retryable=source.retryable)
        self.pages_attempted = pages_attempted


class SafePageFetcher:
    """Production fetcher that cannot bypass the shared SSRF/redirect boundary."""

    def __init__(self, *, config: AcquisitionConfig = AcquisitionConfig(), resolver: Resolver | None = None, transport: SingleHopTransport | None = None):
        self.config = config
        self.resolver = resolver
        self.transport = transport

    def fetch(self, url: str, boundary: ScopeBoundary) -> AcquiredSource:
        return acquire_web_source(
            WebSourceRequest(url), self.config, resolver=self.resolver, transport=self.transport,
            url_policy=lambda candidate: boundary.allows(candidate.url),
        )


class RobotsTxtPolicy:
    """Fail-closed robots policy fetched through the safe HTTP boundary."""

    def __init__(self, *, config: AcquisitionConfig = AcquisitionConfig(), resolver: Resolver | None = None, transport: SingleHopTransport | None = None):
        self.config = config
        self.resolver = resolver
        self.transport = transport
        self._cache: dict[tuple[str, str], urllib.robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        target = validate_source_url(url)
        key = (target.scheme, target.hostname)
        parser = self._cache.get(key)
        if parser is None:
            host = f"[{target.hostname}]" if ":" in target.hostname else target.hostname
            robots_url = urlunsplit((target.scheme, host, "/robots.txt", "", ""))
            try:
                acquired = acquire_web_source(
                    WebSourceRequest(robots_url), self.config, resolver=self.resolver, transport=self.transport,
                    url_policy=lambda candidate: candidate.hostname == target.hostname and urlsplit(candidate.url).path == "/robots.txt",
                )
            except AcquisitionError as error:
                if error.code != "source_not_found":
                    raise
                parser = urllib.robotparser.RobotFileParser()
                parser.parse([])
            else:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(acquired.normalized_text.splitlines())
            self._cache[key] = parser
        return parser.can_fetch(ROBOTS_USER_AGENT, target.url)


def canonicalize_link(base_url: str, href: str) -> str | None:
    without_fragment, _fragment = urldefrag(urljoin(base_url, href))
    try:
        return validate_source_url(without_fragment).url
    except AcquisitionError:
        return None


def _scholarship_related(url: str, text: str) -> bool:
    haystack = f"{url} {text}".replace("_", " ").casefold()
    return any(term in haystack for term in SCHOLARSHIP_TERMS)


def traverse_generic_directory(
    boundary: ScopeBoundary,
    fetcher: PageFetcher,
    robots: RobotsPolicy,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> TraversalResult:
    """Breadth-first traversal bounded by approval, depth, rate, and page count."""

    queue = deque([(boundary.canonical_url, 0)])
    queued = {boundary.canonical_url}
    pages: list[TraversedPage] = []
    attempted = 0
    delay = 60.0 / boundary.requests_per_minute
    while queue and len(pages) < boundary.page_budget:
        url, depth = queue.popleft()
        if attempted:
            sleeper(delay)
        attempted += 1
        try:
            if not robots.allowed(url):
                raise AcquisitionError("robots_denied", "The source disallows PathAid in robots.txt.")
            acquired = fetcher.fetch(url, boundary)
        except AcquisitionError as error:
            raise TraversalFailure(error, attempted) from error
        pages.append(TraversedPage(depth, acquired))
        if depth >= boundary.max_depth:
            continue
        candidates = acquired.discovered_link_candidates
        if not candidates:
            candidates = tuple(SimpleNamespace(href=href, text="") for href in acquired.discovered_links)
        for link in candidates:
            candidate = canonicalize_link(acquired.final_url, link.href)
            if candidate is None or candidate in queued:
                continue
            if not boundary.allows(candidate) or not _scholarship_related(candidate, link.text):
                continue
            queued.add(candidate)
            queue.append((candidate, depth + 1))
    return TraversalResult(tuple(pages), bool(queue))


def _boundary(scope: SourceScope) -> ScopeBoundary:
    return ScopeBoundary(
        id=scope.id, canonical_url=scope.canonical_url, hostname=scope.hostname,
        allowed_path_prefix=scope.allowed_path_prefix, max_depth=scope.max_depth,
        page_budget=scope.page_budget, requests_per_minute=scope.requests_per_minute,
        scan_interval_hours=scope.scan_interval_hours,
    )


def execute_generic_scan(
    database: Database,
    source_id: str,
    *,
    fetcher: PageFetcher | None = None,
    robots: RobotsPolicy | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> SourceScanRun:
    """Execute the generic adapter through the shared persistence boundary."""

    fetcher = fetcher or SafePageFetcher()
    robots = robots or RobotsTxtPolicy()
    return execute_bounded_scan(
        database,
        source_id,
        adapter="generic",
        traverse=lambda boundary: traverse_generic_directory(boundary, fetcher, robots, sleeper=sleeper),
        now=now,
    )


def execute_bounded_scan(
    database: Database,
    source_id: str,
    *,
    adapter: str,
    traverse: Callable[[ScopeBoundary], TraversalResult],
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> SourceScanRun:
    """Run any registered adapter outside transactions and persist one outcome."""

    started = now()
    run_id = str(uuid4())
    with database.sessions.begin() as db:
        scope = db.get(SourceScope, source_id)
        if scope is None:
            raise RegistryError("source_not_found", "Source not found.")
        if scope.adapter != adapter or scope.status != "active" or scope.confirmed_at is None:
            raise RegistryError("source_not_scannable", "The source is not confirmed, active, or compatible with this adapter.")
        if scope.policy_status == "blocked":
            raise RegistryError("policy_blocked", "Source policy prohibits automation.")
        boundary = _boundary(scope)
        db.add(SourceScanRun(
            id=run_id, source_scope_id=scope.id, status="running", started_at=started,
            pages_attempted=0, snapshots_created=0, unchanged_pages=0, traversal_truncated=False,
        ))

    try:
        traversal = traverse(boundary)
    except TraversalFailure as error:
        finished = now()
        with database.sessions.begin() as db:
            run = db.get(SourceScanRun, run_id)
            scope = db.get(SourceScope, source_id)
            run.status = "failed"
            run.finished_at = finished
            run.pages_attempted = error.pages_attempted
            run.error_code = error.code
            scope.last_attempt_at = finished
            scope.last_error_code = error.code
            scope.scan_requested_at = None
        return run

    finished = now()
    with database.sessions.begin() as db:
        run = db.get(SourceScanRun, run_id)
        scope = db.get(SourceScope, source_id)
        created = 0
        unchanged = 0
        for page in traversal.pages:
            acquired = page.acquired
            previous = db.scalar(
                select(SourceSnapshot)
                .where(SourceSnapshot.source_scope_id == source_id, SourceSnapshot.canonical_url == acquired.original_url)
                .order_by(SourceSnapshot.acquired_at.desc(), SourceSnapshot.id.desc())
                .limit(1)
            )
            if previous is not None and previous.content_hash == acquired.content_hash:
                unchanged += 1
                continue
            db.add(SourceSnapshot(
                id=str(uuid4()), source_scope_id=source_id, scan_run_id=run_id,
                canonical_url=acquired.original_url, final_url=acquired.final_url, acquired_at=finished,
                content_hash=acquired.content_hash, media_type=acquired.media_type,
                normalized_text=acquired.normalized_text, source_byte_count=acquired.source_byte_count,
                redirect_count=acquired.redirect_count, depth=page.depth,
            ))
            created += 1
        run.status = "succeeded"
        run.finished_at = finished
        run.pages_attempted = len(traversal.pages)
        run.snapshots_created = created
        run.unchanged_pages = unchanged
        run.traversal_truncated = traversal.truncated
        scope.last_attempt_at = finished
        scope.last_success_at = finished
        if created:
            scope.last_content_change_at = finished
        scope.next_scan_at = finished + timedelta(hours=scope.scan_interval_hours)
        scope.scan_requested_at = None
        scope.last_error_code = None
    return run
