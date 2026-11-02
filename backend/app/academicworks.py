"""Public-listing adapter for Blackbaud Award Management / AcademicWorks."""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from urllib.parse import parse_qs, urlsplit

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


OPPORTUNITY_PATH = re.compile(r"^/opportunities/(?P<identifier>[1-9]\d*)/?$")
PLATFORM_MARKERS = ("opportunities table", "all opportunities", "our opportunities")


@dataclass(frozen=True)
class PortalRoute:
    url: str
    kind: str
    depth: int


def _is_listing_page(url: str, root: str) -> bool:
    candidate = urlsplit(url)
    root_parts = urlsplit(root)
    listing_paths = {"", "/opportunities", root_parts.path.rstrip("/")}
    if candidate.path.rstrip("/") not in listing_paths:
        return False
    query = parse_qs(candidate.query, keep_blank_values=True)
    if set(query).difference({"page"}):
        return False
    if "page" not in query:
        return True
    values = query["page"]
    return len(values) == 1 and re.fullmatch(r"-?\d+", values[0]) is not None


def _page_number(url: str) -> int:
    values = parse_qs(urlsplit(url).query).get("page")
    return int(values[0]) if values and re.fullmatch(r"\d+", values[0]) else 0


def _platform_listing(text: str, links) -> bool:
    normalized = text.casefold()
    has_marker = any(marker in normalized for marker in PLATFORM_MARKERS)
    has_opportunity_links = any(OPPORTUNITY_PATH.fullmatch(urlsplit(link.href).path) for link in links)
    return has_marker and (has_opportunity_links or "blackbaud" in normalized)


def traverse_academicworks(
    boundary: ScopeBoundary,
    fetcher: PageFetcher,
    robots: RobotsPolicy,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> TraversalResult:
    """Follow only public pagination and numeric opportunity-detail routes."""

    queue = deque([PortalRoute(boundary.canonical_url, "listing", 0)])
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
            raise TraversalFailure(error, attempted, route.url) from error
        links = acquired.discovered_link_candidates
        if route.kind == "listing" and not _platform_listing(acquired.normalized_text, links):
            error = AcquisitionError("adapter_signature_mismatch", "The page is not a public AcademicWorks opportunity listing.")
            raise TraversalFailure(error, attempted, route.url)
        pages.append(TraversedPage(route.depth, acquired))
        if route.kind != "listing":
            continue

        details: list[PortalRoute] = []
        pagination: list[PortalRoute] = []
        for link in links:
            candidate = canonicalize_link(acquired.final_url, link.href)
            if candidate is None or candidate in queued or not boundary.allows(candidate):
                continue
            path = urlsplit(candidate).path
            if route.depth < boundary.max_depth and OPPORTUNITY_PATH.fullmatch(path):
                details.append(PortalRoute(candidate, "detail", route.depth + 1))
            elif _is_listing_page(candidate, boundary.canonical_url) and _page_number(candidate) > _page_number(route.url):
                pagination.append(PortalRoute(candidate, "listing", route.depth))
        for candidate in details + pagination:
            if candidate.url not in queued:
                queued.add(candidate.url)
                queue.append(candidate)
    return TraversalResult(tuple(pages), bool(queue))


def execute_academicworks_scan(
    database: Database,
    source_id: str,
    *,
    fetcher: PageFetcher | None = None,
    robots: RobotsPolicy | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] | None = None,
) -> SourceScanRun:
    """Execute a confirmed AcademicWorks source through shared persistence."""

    fetcher = fetcher or SafePageFetcher()
    robots = robots or RobotsTxtPolicy()
    traversal = lambda boundary: traverse_academicworks(boundary, fetcher, robots, sleeper=sleeper)
    if now is None:
        return execute_bounded_scan(database, source_id, adapter="academicworks", traverse=traversal)
    return execute_bounded_scan(database, source_id, adapter="academicworks", traverse=traversal, now=now)
