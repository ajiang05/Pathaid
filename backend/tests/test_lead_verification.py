"""Acceptance tests for exact-page official evidence verification."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DatabaseError

from app.config import Settings
from app.database import Database
from app.lead_verification import verify_manual_lead
from app.local_data import upgrade_database
from app.models import ManualLead, ManualLeadSnapshot
from app.source_acquisition import AcquiredSource, AcquisitionError, hash_text
from app.source_registry import RegistryError


class Fetcher:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Robots:
    def __init__(self, allowed=True):
        self.result = allowed

    def allowed(self, _url):
        return self.result


def page(url: str, text: str, *, final_url: str | None = None) -> AcquiredSource:
    return AcquiredSource(
        original_url=url, final_url=final_url or url, acquisition_method="webpage", media_type="text/html",
        normalized_text=text, content_hash=hash_text(text), source_byte_count=len(text.encode()), redirect_count=0,
    )


def lead_database(tmp_path) -> Database:
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    database = Database(settings)
    with database.sessions.begin() as db:
        db.add(ManualLead(
            id="lead-1", title="Ada Lovelace Computing Scholarship",
            canonical_url="https://bigfuture.collegeboard.org/scholarships/ada",
            hostname="bigfuture.collegeboard.org", status="unverified",
        ))
    return database


def test_verified_official_page_is_snapshotted_once_when_unchanged(tmp_path):
    database = lead_database(tmp_path)
    official = "https://ada-foundation.example/scholarship"
    acquired = page(official, "Ada Lovelace Computing Scholarship eligibility and application details")
    first = verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(acquired), robots=Robots())
    assert first.status == "official_verified"
    assert first.official_url == official and first.official_hostname == "ada-foundation.example"
    assert first.verified_at is not None and first.last_error_code is None

    second = verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(acquired), robots=Robots())
    assert second.status == "official_verified"
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ManualLeadSnapshot)) == 1
    database.close()


def test_changed_official_content_creates_new_immutable_evidence(tmp_path):
    database = lead_database(tmp_path)
    official = "https://ada-foundation.example/scholarship"
    verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(page(official, "Ada Computing Scholarship opens today")), robots=Robots())
    verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(page(official, "Ada Computing Scholarship deadline extended")), robots=Robots())
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ManualLeadSnapshot)) == 2
        snapshot_id = db.scalar(select(ManualLeadSnapshot.id).limit(1))
    with pytest.raises(DatabaseError):
        with database.sessions.begin() as db:
            db.execute(update(ManualLeadSnapshot).where(ManualLeadSnapshot.id == snapshot_id).values(normalized_text="changed"))
    database.close()


def test_aggregator_cannot_be_confirmed_as_official_evidence(tmp_path):
    database = lead_database(tmp_path)
    fetcher = Fetcher(page("https://bold.org/scholarships/example", "Ada Scholarship"))
    with pytest.raises(RegistryError) as captured:
        verify_manual_lead(database, "lead-1", "https://bold.org/scholarships/example", fetcher=fetcher, robots=Robots())
    assert captured.value.code == "aggregator_not_official"
    assert fetcher.calls == []
    database.close()


def test_mismatch_missing_and_robots_denial_do_not_create_evidence(tmp_path):
    database = lead_database(tmp_path)
    official = "https://sponsor.example/scholarship"
    mismatch = verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(page(official, "Generic home page")), robots=Robots())
    assert mismatch.status == "rejected" and mismatch.last_error_code == "official_page_mismatch"
    missing = verify_manual_lead(
        database, "lead-1", official,
        fetcher=Fetcher(AcquisitionError("source_not_found", "Not found")), robots=Robots(),
    )
    assert missing.status == "unavailable" and missing.last_error_code == "source_not_found"
    denied = verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(page(official, "Ada Scholarship")), robots=Robots(False))
    assert denied.status == "unverified" and denied.last_error_code == "robots_denied"
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ManualLeadSnapshot)) == 0
    database.close()


def test_transient_failure_preserves_prior_verified_evidence(tmp_path):
    database = lead_database(tmp_path)
    official = "https://sponsor.example/scholarship"
    verify_manual_lead(database, "lead-1", official, fetcher=Fetcher(page(official, "Ada Lovelace Scholarship details")), robots=Robots())
    failed = verify_manual_lead(
        database, "lead-1", official,
        fetcher=Fetcher(AcquisitionError("upstream_unavailable", "Try later", retryable=True)), robots=Robots(),
    )
    assert failed.status == "official_verified" and failed.last_error_code == "upstream_unavailable"
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ManualLeadSnapshot)) == 1
    database.close()
