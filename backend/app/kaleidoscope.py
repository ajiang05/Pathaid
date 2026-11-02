"""Public-marketplace adapter for Kaleidoscope scholarship programs."""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from urllib.parse import urlsplit

from .database import Database
from .generic_directory import (
    PageFetcher,
    RobotsPolicy,
    RobotsTxtPolicy,
    SafePageFetcher,
    ScopeBoundary,
    TraversalFailure,
    TraversalResult,
    TraversedPage,
    canonicalize_link,
    execute_bounded_scan,
)
from .models import SourceScanRun
from .source_acquisition import AcquisitionError


# Kaleidoscope exposes public program summaries at stable, one-segment slugs.
# Authentication and form routes are deliberately outside this adapter.
PROGRAM_PATH = re.compile(r"^/program/(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]*)/?$")
MARKETPLACE_MARKERS = ("explore the marketplace", "search programs", "find scholarship programs")
PROGRAM_MARKERS = ("log in to apply", "selection process", "about the sponsor", "qualifications")


@dataclass(frozen=True)
class PortalRoute:
    url: str
    kind: str
    depth: int


def _public_program_url(url: str) -> bool:
    candidate = urlsplit(url)
    return not candidate.query and PROGRAM_PATH.fullmatch(candidate.path) is not None


def _marketplace_page(text: str, links) -> bool:
    normalized = text.casefold()
    branded = "kaleidoscope" in normalized
    marked = any(marker in normalized for marker in MARKETPLACE_MARKERS)
    has_program = any(_public_program_url(link.href) for link in links)
    # An empty marketplace is valid when its branding and marketplace heading
    # remain present; this prevents a temporary zero-result state from failing.
    return branded and marked and (has_program or "marketplace" in normalized)


def _program_page(text: str) -> bool:
    normalized = text.casefold()
    return "kaleidoscope" in normalized and any(marker in normalized for marker in PROGRAM_MARKERS)


def traverse_kaleidoscope(
    boundary: ScopeBoundary,
    fetcher: PageFetcher,
    robots: RobotsPolicy,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> TraversalResult:
    """Follow only Kaleidoscope's public marketplace and program summaries."""

    queue = deque([PortalRoute(boundary.canonical_url, "marketplace", 0)])
    queued = {boundary.canonical_url}
    pages: list[TraversedPage] = []
    attempted = 0
    delay = 60.0 / boundary.requests_per_minute
    while queue and len(pages) < boundary.page_budget:
        route = queue.popleft()
        if attempted:
            sleeper(delay)
        attempted += 1
        try:
            if not robots.allowed(route.url):
                raise AcquisitionError("robots_denied", "The source disallows PathAid in robots.txt.")
            acquired = fetcher.fetch(route.url, boundary)
        except AcquisitionError as error:
            raise TraversalFailure(error, attempted) from error

        links = acquired.discovered_link_candidates
        valid = _marketplace_page(acquired.normalized_text, links) if route.kind == "marketplace" else _program_page(acquired.normalized_text)
        if not valid:
            error = AcquisitionError("adapter_signature_mismatch", f"The page is not a public Kaleidoscope {route.kind} page.")
            raise TraversalFailure(error, attempted)
        pages.append(TraversedPage(route.depth, acquired))

        if route.kind != "marketplace" or route.depth >= boundary.max_depth:
            continue
        for link in links:
            candidate = canonicalize_link(acquired.final_url, link.href)
            if candidate is None or candidate in queued or not boundary.allows(candidate):
                continue
            if _public_program_url(candidate):
                queued.add(candidate)
                queue.append(PortalRoute(candidate, "program", route.depth + 1))
    return TraversalResult(tuple(pages), bool(queue))


def execute_kaleidoscope_scan(
    database: Database,
    source_id: str,
    *,
    fetcher: PageFetcher | None = None,
    robots: RobotsPolicy | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] | None = None,
) -> SourceScanRun:
    """Execute a confirmed Kaleidoscope source through shared persistence."""

    fetcher = fetcher or SafePageFetcher()
    robots = robots or RobotsTxtPolicy()
    traversal = lambda boundary: traverse_kaleidoscope(boundary, fetcher, robots, sleeper=sleeper)
    if now is None:
        return execute_bounded_scan(database, source_id, adapter="kaleidoscope", traverse=traversal)
    return execute_bounded_scan(database, source_id, adapter="kaleidoscope", traverse=traversal, now=now)
