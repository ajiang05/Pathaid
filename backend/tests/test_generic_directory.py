"""Saved-fixture tests for bounded generic scholarship traversal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import Database
from app.generic_directory import RobotsTxtPolicy, ScopeBoundary, TraversalFailure, execute_generic_scan, traverse_generic_directory
from app.local_data import upgrade_database
from app.models import Scholarship, ScholarshipVersion, SourcePageState, SourceScanRun, SourceScope, SourceSnapshot
from app.source_acquisition import AcquisitionError, AcquiredSource, DiscoveredLink, hash_text
from app.source_registry import RegistryError


def acquired(url: str, text: str, links=()):
    return AcquiredSource(
        original_url=url, final_url=url, acquisition_method="webpage", media_type="text/html",
        normalized_text=text, content_hash=hash_text(text), source_byte_count=len(text.encode()),
        redirect_count=0, discovered_links=tuple(item.href for item in links),
        discovered_link_candidates=tuple(links),
    )


class FixtureFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, url, boundary):
        self.calls.append(url)
        outcome = self.pages[url]
        if isinstance(outcome, Exception):
            raise outcome
        assert boundary.allows(url)
        return outcome


class FixtureRobots:
    def __init__(self, denied=()):
        self.denied = set(denied)
        self.calls = []

    def allowed(self, url):
        self.calls.append(url)
        return url not in self.denied


class RobotsTransport:
    def __init__(self, body):
        self.body = body
        self.calls = 0

    def fetch(self, _url, _address, *, timeout_seconds, max_response_bytes):
        from app.source_acquisition import HttpResponse

        self.calls += 1
        return HttpResponse(200, {"content-type": "text/plain; charset=utf-8"}, self.body)


def boundary(**overrides):
    values = {
        "id": "scope-1", "canonical_url": "https://example.edu/aid", "hostname": "example.edu",
        "allowed_path_prefix": "/aid", "max_depth": 1, "page_budget": 10,
        "requests_per_minute": 12, "scan_interval_hours": 24,
    }
    values.update(overrides)
    return ScopeBoundary(**values)


def database_with_scope(tmp_path, **overrides):
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    database = Database(settings)
    values = {
        "id": "scope-1", "name": "Fixture directory", "ownership": "sponsor", "adapter": "generic",
        "canonical_url": "https://example.edu/aid", "hostname": "example.edu", "allowed_path_prefix": "/aid",
        "institution_unit_id": None, "school_revision": None, "status": "active",
        "confirmed_at": datetime(2026, 11, 1, tzinfo=timezone.utc), "max_depth": 1, "page_budget": 10,
        "requests_per_minute": 60, "scan_interval_hours": 24, "policy_status": "allowed",
    }
    values.update(overrides)
    with database.sessions.begin() as db:
        db.add(SourceScope(**values))
    return database


def test_follows_only_related_same_scope_links_within_depth_and_paces_requests():
    root = "https://example.edu/aid"
    one = "https://example.edu/aid/scholarship-one"
    apply = "https://example.edu/aid/apply?id=7"
    pages = {
        root: acquired(root, "Directory", (
            DiscoveredLink("/aid/scholarship-one", "Details"),
            DiscoveredLink("/aid/apply?id=7", "Community Scholarship"),
            DiscoveredLink("/aid/news", "Campus news"),
            DiscoveredLink("https://outside.example/scholarship", "Scholarship"),
            DiscoveredLink("/other/scholarship", "Scholarship"),
        )),
        one: acquired(one, "First", (DiscoveredLink("/aid/scholarship-too-deep", "Scholarship"),)),
        apply: acquired(apply, "Second"),
    }
    delays = []
    result = traverse_generic_directory(boundary(), FixtureFetcher(pages), FixtureRobots(), sleeper=delays.append)
    assert [page.acquired.original_url for page in result.pages] == [root, one, apply]
    assert [page.depth for page in result.pages] == [0, 1, 1]
    assert delays == [5.0, 5.0]
    assert result.truncated is False


def test_page_budget_stops_before_fetching_extra_candidates():
    root = "https://example.edu/aid"
    pages = {root: acquired(root, "Directory", (DiscoveredLink("/aid/scholarship-one", "Scholarship"),))}
    fetcher = FixtureFetcher(pages)
    result = traverse_generic_directory(boundary(page_budget=1), fetcher, FixtureRobots(), sleeper=lambda _delay: None)
    assert fetcher.calls == [root]
    assert result.truncated is True


def test_robots_denial_fails_closed_before_page_fetch():
    root = "https://example.edu/aid"
    fetcher = FixtureFetcher({})
    with pytest.raises(TraversalFailure) as captured:
        traverse_generic_directory(boundary(), fetcher, FixtureRobots({root}), sleeper=lambda _delay: None)
    assert captured.value.code == "robots_denied"
    assert captured.value.pages_attempted == 1
    assert fetcher.calls == []


def test_production_robots_policy_uses_pathaid_agent_and_caches_host_rules():
    transport = RobotsTransport(b"User-agent: PathAid\nDisallow: /aid/private\nAllow: /aid/public\n")
    policy = RobotsTxtPolicy(resolver=lambda _host, _port: ["93.184.216.34"], transport=transport)
    assert policy.allowed("https://example.edu/aid/public") is True
    assert policy.allowed("https://example.edu/aid/private") is False
    assert transport.calls == 1


def test_success_retains_snapshots_and_unchanged_refresh_creates_no_duplicate(tmp_path):
    database = database_with_scope(tmp_path)
    root = "https://example.edu/aid"
    fetcher = FixtureFetcher({root: acquired(root, "Scholarship directory v1")})
    moments = iter([datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc), datetime(2026, 11, 1, 12, 1, tzinfo=timezone.utc)])
    first = execute_generic_scan(database, "scope-1", fetcher=fetcher, robots=FixtureRobots(), sleeper=lambda _delay: None, now=lambda: next(moments))
    assert first.status == "succeeded" and first.snapshots_created == 1

    moments = iter([datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc), datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)])
    second = execute_generic_scan(database, "scope-1", fetcher=fetcher, robots=FixtureRobots(), sleeper=lambda _delay: None, now=lambda: next(moments))
    assert second.status == "succeeded" and second.snapshots_created == 0 and second.unchanged_pages == 1
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SourceSnapshot)) == 1
        scope = db.get(SourceScope, "scope-1")
        assert scope.last_success_at is not None
        assert scope.next_scan_at - scope.last_success_at == timedelta(hours=24)
    database.close()


def test_failed_refresh_preserves_last_snapshot_and_records_safe_error(tmp_path):
    database = database_with_scope(tmp_path)
    root = "https://example.edu/aid"
    good = FixtureFetcher({root: acquired(root, "Valid retained evidence")})
    moments = iter([datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc), datetime(2026, 11, 1, 12, 1, tzinfo=timezone.utc)])
    execute_generic_scan(database, "scope-1", fetcher=good, robots=FixtureRobots(), sleeper=lambda _delay: None, now=lambda: next(moments))

    failed = FixtureFetcher({root: AcquisitionError("timeout", "Source acquisition timed out.", retryable=True)})
    moments = iter([datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc), datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)])
    run = execute_generic_scan(database, "scope-1", fetcher=failed, robots=FixtureRobots(), sleeper=lambda _delay: None, now=lambda: next(moments))
    assert run.status == "failed" and run.error_code == "timeout"
    with database.sessions() as db:
        snapshots = db.scalars(select(SourceSnapshot)).all()
        assert len(snapshots) == 1 and snapshots[0].normalized_text == "Valid retained evidence"
        assert db.get(SourceScope, "scope-1").last_error_code == "timeout"
    database.close()


def test_snapshot_rows_reject_update_and_delete(tmp_path):
    database = database_with_scope(tmp_path)
    root = "https://example.edu/aid"
    moments = iter([datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc), datetime(2026, 11, 1, 12, 1, tzinfo=timezone.utc)])
    execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher({root: acquired(root, "Immutable")}), robots=FixtureRobots(), sleeper=lambda _delay: None, now=lambda: next(moments))
    with pytest.raises(IntegrityError):
        with database.sessions.begin() as db:
            db.execute(update(SourceSnapshot).values(normalized_text="Changed"))
    with database.sessions() as db:
        assert db.scalar(select(SourceSnapshot.normalized_text)) == "Immutable"
    database.close()


def test_unconfirmed_paused_incompatible_and_policy_gated_scopes_never_scan(tmp_path):
    cases = [
        {"status": "proposed", "confirmed_at": None},
        {"status": "paused"},
        {"adapter": "academicworks"},
        {"policy_status": "blocked"},
        {"policy_status": "unknown"},
    ]
    for index, values in enumerate(cases):
        database = database_with_scope(tmp_path / str(index), **values)
        with pytest.raises(RegistryError) as captured:
            execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher({}), robots=FixtureRobots(), sleeper=lambda _delay: None)
        assert getattr(captured.value, "code", None) in {"source_not_scannable", "policy_blocked", "policy_unchecked"}
        with database.sessions() as db:
            assert db.scalar(select(func.count()).select_from(SourceScanRun)) == 0
        database.close()


def _attach_scholarship(database, source_url: str):
    """Attach a minimal active version to one previously acquired detail URL."""

    with database.sessions.begin() as db:
        snapshot = db.scalar(select(SourceSnapshot).where(SourceSnapshot.canonical_url == source_url))
        scholarship = Scholarship(id="scholarship-1", source_url=source_url, status="active")
        db.add(scholarship); db.flush()
        version = ScholarshipVersion(
            id="version-1", scholarship_id=scholarship.id, source_snapshot_id=snapshot.id,
            draft_hash="b" * 64, material_fingerprint="c" * 64, data={}, validation_findings=[],
            extraction_model="fixture", prompt_version="2.0.0", schema_version="1.0.0",
            activated_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )
        db.add(version); db.flush()
        scholarship.active_version_id = version.id


def test_complete_scan_marks_missing_page_inactive_and_identical_return_reactivates(tmp_path):
    database = database_with_scope(tmp_path)
    root, detail = "https://example.edu/aid", "https://example.edu/aid/scholarship-one"
    first_pages = {
        root: acquired(root, "Directory v1", (DiscoveredLink(detail, "Scholarship"),)),
        detail: acquired(detail, "Scholarship details"),
    }
    moments = iter([datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, 0, 1, tzinfo=timezone.utc)])
    execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher(first_pages), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    _attach_scholarship(database, detail)

    moments = iter([datetime(2026, 11, 2, tzinfo=timezone.utc), datetime(2026, 11, 2, 0, 1, tzinfo=timezone.utc)])
    execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher({root: acquired(root, "Directory v2")}), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    with database.sessions() as db:
        state = db.scalar(select(SourcePageState).where(SourcePageState.canonical_url == detail))
        assert state.status == "disappeared" and state.missed_scan_count == 1
        assert db.get(Scholarship, "scholarship-1").status == "inactive"

    # The detail content is byte-identical to its retained snapshot, but its
    # observed presence is enough to restore the prior validated scholarship.
    moments = iter([datetime(2026, 11, 3, tzinfo=timezone.utc), datetime(2026, 11, 3, 0, 1, tzinfo=timezone.utc)])
    returned = {
        root: acquired(root, "Directory v3", (DiscoveredLink(detail, "Scholarship"),)),
        detail: acquired(detail, "Scholarship details"),
    }
    run = execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher(returned), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    assert run.unchanged_pages == 1
    with database.sessions() as db:
        state = db.scalar(select(SourcePageState).where(SourcePageState.canonical_url == detail))
        assert state.status == "current" and state.missed_scan_count == 0 and state.missing_since is None
        assert db.get(Scholarship, "scholarship-1").status == "active"
    database.close()


def test_truncated_scan_does_not_infer_disappearance(tmp_path):
    database = database_with_scope(tmp_path)
    root, detail = "https://example.edu/aid", "https://example.edu/aid/scholarship-one"
    pages = {root: acquired(root, "Directory", (DiscoveredLink(detail, "Scholarship"),)), detail: acquired(detail, "Details")}
    moments = iter([datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, 0, 1, tzinfo=timezone.utc)])
    execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher(pages), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    _attach_scholarship(database, detail)
    with database.sessions.begin() as db:
        db.get(SourceScope, "scope-1").page_budget = 1
    moments = iter([datetime(2026, 11, 2, tzinfo=timezone.utc), datetime(2026, 11, 2, 0, 1, tzinfo=timezone.utc)])
    run = execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher({root: acquired(root, "Directory changed", (DiscoveredLink(detail, "Scholarship"),))}), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    assert run.traversal_truncated is True
    with database.sessions() as db:
        assert db.get(Scholarship, "scholarship-1").status == "active"
        assert db.scalar(select(SourcePageState.status).where(SourcePageState.canonical_url == detail)) == "current"
    database.close()


def test_confirmed_not_found_detail_disappears_but_history_remains(tmp_path):
    database = database_with_scope(tmp_path)
    root, detail = "https://example.edu/aid", "https://example.edu/aid/scholarship-one"
    pages = {root: acquired(root, "Directory", (DiscoveredLink(detail, "Scholarship"),)), detail: acquired(detail, "Details")}
    moments = iter([datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, 0, 1, tzinfo=timezone.utc)])
    execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher(pages), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    _attach_scholarship(database, detail)
    missing = {root: pages[root], detail: AcquisitionError("source_not_found", "Not found")}
    moments = iter([datetime(2026, 11, 2, tzinfo=timezone.utc), datetime(2026, 11, 2, 0, 1, tzinfo=timezone.utc)])
    run = execute_generic_scan(database, "scope-1", fetcher=FixtureFetcher(missing), robots=FixtureRobots(), sleeper=lambda _: None, now=lambda: next(moments))
    assert run.status == "failed" and run.error_code == "source_not_found"
    with database.sessions() as db:
        assert db.get(Scholarship, "scholarship-1").status == "inactive"
        assert db.scalar(select(func.count()).select_from(SourceSnapshot)) == 2
        assert db.scalar(select(func.count()).select_from(ScholarshipVersion)) == 1
    database.close()
