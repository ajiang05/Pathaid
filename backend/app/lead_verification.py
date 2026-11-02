"""Exact-page verification for scholarship leads found on manual aggregators."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select

from .database import Database
from .generic_directory import RobotsPolicy, RobotsTxtPolicy
from .models import ManualLead, ManualLeadSnapshot
from .source_acquisition import (
    AcquiredSource,
    AcquisitionConfig,
    AcquisitionError,
    Resolver,
    SingleHopTransport,
    WebSourceRequest,
    acquire_web_source,
    validate_source_url,
)
from .source_registry import RegistryError, manual_only_host


SCHOLARSHIP_TERMS = ("scholarship", "scholarships", "education award", "student award", "bursary")
TITLE_STOP_WORDS = {
    "a", "an", "and", "application", "award", "for", "fund", "lead", "of", "program",
    "scholarship", "scholarships", "the", "this", "year",
}


class LeadPageFetcher(Protocol):
    def fetch(self, url: str) -> AcquiredSource: ...


class SafeLeadPageFetcher:
    """Fetch one exact sponsor page while permitting only same-host redirects."""

    def __init__(
        self,
        *,
        config: AcquisitionConfig = AcquisitionConfig(),
        resolver: Resolver | None = None,
        transport: SingleHopTransport | None = None,
    ):
        self.config = config
        self.resolver = resolver
        self.transport = transport

    def fetch(self, url: str) -> AcquiredSource:
        target = validate_source_url(url)
        return acquire_web_source(
            WebSourceRequest(target.url),
            self.config,
            resolver=self.resolver,
            transport=self.transport,
            # A user confirms one URL, not a domain. Same-host redirects are
            # accepted only because the server may canonicalize that one page.
            url_policy=lambda candidate: candidate.hostname == target.hostname,
        )


def _title_tokens(title: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", title.casefold())
        if len(token) >= 3 and token not in TITLE_STOP_WORDS
    }


def _supports_lead(acquired: AcquiredSource, title: str) -> bool:
    """Require scholarship language plus identity overlap when available."""

    text = acquired.normalized_text.casefold()
    if not any(term in text for term in SCHOLARSHIP_TERMS):
        return False
    tokens = _title_tokens(title)
    return not tokens or any(token in text for token in tokens)


def _record_failure(database: Database, lead_id: str, error_code: str, attempted_at: datetime) -> ManualLead:
    with database.sessions.begin() as db:
        lead = db.get(ManualLead, lead_id)
        if lead is None:
            raise RegistryError("lead_not_found", "Lead not found.")
        lead.last_attempt_at = attempted_at
        lead.last_error_code = error_code
        # A transient network failure must not erase previously verified
        # evidence. A confirmed disappearance or mismatched page does.
        if error_code == "source_not_found":
            lead.status = "unavailable"
        elif error_code == "official_page_mismatch":
            lead.status = "rejected"
        elif lead.status != "official_verified":
            lead.status = "unverified"
        return lead


def verify_manual_lead(
    database: Database,
    lead_id: str,
    official_url: str,
    *,
    fetcher: LeadPageFetcher | None = None,
    robots: RobotsPolicy | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> ManualLead:
    """Verify one user-confirmed official URL and retain changed evidence."""

    try:
        target = validate_source_url(official_url)
    except AcquisitionError as error:
        raise RegistryError(error.code, error.safe_message) from error
    if manual_only_host(target.hostname):
        raise RegistryError("aggregator_not_official", "An aggregator URL cannot be used as official scholarship evidence.")

    with database.sessions() as db:
        lead = db.get(ManualLead, lead_id)
        if lead is None:
            raise RegistryError("lead_not_found", "Lead not found.")
        title = lead.title

    attempted_at = now()
    fetcher = fetcher or SafeLeadPageFetcher()
    robots = robots or RobotsTxtPolicy()
    try:
        if not robots.allowed(target.url):
            raise AcquisitionError("robots_denied", "The official page disallows PathAid in robots.txt.")
        acquired = fetcher.fetch(target.url)
    except AcquisitionError as error:
        return _record_failure(database, lead_id, error.code, attempted_at)
    if not _supports_lead(acquired, title):
        return _record_failure(database, lead_id, "official_page_mismatch", attempted_at)

    with database.sessions.begin() as db:
        lead = db.get(ManualLead, lead_id)
        if lead is None:
            raise RegistryError("lead_not_found", "Lead not found.")
        previous = db.scalar(
            select(ManualLeadSnapshot)
            .where(ManualLeadSnapshot.manual_lead_id == lead_id)
            .order_by(ManualLeadSnapshot.acquired_at.desc(), ManualLeadSnapshot.id.desc())
            .limit(1)
        )
        if previous is None or previous.content_hash != acquired.content_hash or previous.official_url != target.url:
            db.add(ManualLeadSnapshot(
                id=str(uuid4()), manual_lead_id=lead_id, official_url=target.url,
                final_url=acquired.final_url, acquired_at=attempted_at,
                content_hash=acquired.content_hash, media_type=acquired.media_type,
                normalized_text=acquired.normalized_text,
                source_byte_count=acquired.source_byte_count,
                redirect_count=acquired.redirect_count,
            ))
        lead.status = "official_verified"
        lead.official_url = target.url
        lead.official_hostname = urlsplit(acquired.final_url).hostname
        lead.last_attempt_at = attempted_at
        lead.verified_at = attempted_at
        lead.last_error_code = None
        return lead
