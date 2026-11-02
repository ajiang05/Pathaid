"""Representative public Kaleidoscope marketplace adapter tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.database import Database
from app.generic_directory import ScopeBoundary, TraversalFailure
from app.kaleidoscope import execute_kaleidoscope_scan, traverse_kaleidoscope
from app.local_data import upgrade_database
from app.models import SourceScope, SourceSnapshot
from app.source_acquisition import AcquiredSource, extract_html_link_candidates, hash_text, normalize_html
from app.source_registry import RegistryError


FIXTURES = Path(__file__).parent / "fixtures"


def html_page(url: str, fixture: str) -> AcquiredSource:
    raw = (FIXTURES / fixture).read_text(encoding="utf-8")
    text = normalize_html(raw, 100_000)
    links = extract_html_link_candidates(raw)
    return AcquiredSource(
        original_url=url, final_url=url, acquisition_method="webpage", media_type="text/html",
        normalized_text=text, content_hash=hash_text(text), source_byte_count=len(raw.encode()),
        redirect_count=0, discovered_links=tuple(item.href for item in links), discovered_link_candidates=links,
    )


def text_page(url: str, text: str) -> AcquiredSource:
    return AcquiredSource(
        original_url=url, final_url=url, acquisition_method="webpage", media_type="text/html",
        normalized_text=text, content_hash=hash_text(text), source_byte_count=len(text.encode()),
        redirect_count=0, discovered_links=(), discovered_link_candidates=(),
    )


class Fetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, url, boundary):
        self.calls.append(url)
        assert boundary.allows(url)
        return self.pages[url]


class Robots:
    def __init__(self, allowed=True):
        self.result = allowed

    def allowed(self, _url):
        return self.result


def boundary(**changes) -> ScopeBoundary:
    values = {
        "id": "kaleidoscope-1", "canonical_url": "https://apply.mykaleidoscope.com/",
        "hostname": "apply.mykaleidoscope.com", "allowed_path_prefix": "/", "max_depth": 1,
        "page_budget": 10, "requests_per_minute": 60, "scan_interval_hours": 24,
    }
    values.update(changes)
    return ScopeBoundary(**values)


def database_with_scope(tmp_path, adapter="kaleidoscope") -> Database:
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    database = Database(settings)
    with database.sessions.begin() as db:
        db.add(SourceScope(
            id="kaleidoscope-1", name="Kaleidoscope marketplace", ownership="sponsor", adapter=adapter,
            canonical_url="https://apply.mykaleidoscope.com/", hostname="apply.mykaleidoscope.com",
            allowed_path_prefix="/", status="active", confirmed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            max_depth=1, page_budget=10, requests_per_minute=60, scan_interval_hours=24,
            policy_status="allowed",
        ))
    return database


def test_follows_only_public_program_summaries():
    root = "https://apply.mykaleidoscope.com/"
    first = "https://apply.mykaleidoscope.com/program/CommunityService2027"
    second = "https://apply.mykaleidoscope.com/program/College_Student-Award"
    fetcher = Fetcher({
        root: html_page(root, "kaleidoscope_marketplace.html"),
        first: html_page(first, "kaleidoscope_program.html"),
        second: text_page(second, "Kaleidoscope College Award Qualifications Log In to Apply"),
    })
    result = traverse_kaleidoscope(boundary(), fetcher, Robots(), sleeper=lambda _delay: None)
    assert [page.acquired.original_url for page in result.pages] == [root, first, second]
    assert not any("login" in url or "programs/" in url or "?" in url or "outside.example" in url for url in fetcher.calls)
    assert result.truncated is False


def test_marketplace_and_program_signatures_fail_closed():
    root = "https://apply.mykaleidoscope.com/"
    with pytest.raises(TraversalFailure) as mismatch:
        traverse_kaleidoscope(boundary(), Fetcher({root: text_page(root, "Generic marketplace")}), Robots(), sleeper=lambda _delay: None)
    assert mismatch.value.code == "adapter_signature_mismatch"

    listing = html_page(root, "kaleidoscope_marketplace.html")
    first = "https://apply.mykaleidoscope.com/program/CommunityService2027"
    pages = {root: listing, first: text_page(first, "Unrelated page")}
    # Limit the fixture to one program so the first invalid detail deterministically fails.
    links = tuple(item for item in listing.discovered_link_candidates if item.href == "/program/CommunityService2027")
    pages[root] = AcquiredSource(**{**listing.__dict__, "discovered_links": tuple(item.href for item in links), "discovered_link_candidates": links})
    with pytest.raises(TraversalFailure) as detail_mismatch:
        traverse_kaleidoscope(boundary(), Fetcher(pages), Robots(), sleeper=lambda _delay: None)
    assert detail_mismatch.value.code == "adapter_signature_mismatch"


def test_robots_depth_and_page_budgets_are_enforced():
    root = "https://apply.mykaleidoscope.com/"
    listing = html_page(root, "kaleidoscope_marketplace.html")
    with pytest.raises(TraversalFailure) as denied:
        traverse_kaleidoscope(boundary(), Fetcher({}), Robots(False), sleeper=lambda _delay: None)
    assert denied.value.code == "robots_denied"

    result = traverse_kaleidoscope(boundary(max_depth=0), Fetcher({root: listing}), Robots(), sleeper=lambda _delay: None)
    assert len(result.pages) == 1 and result.truncated is False

    result = traverse_kaleidoscope(boundary(page_budget=1), Fetcher({root: listing}), Robots(), sleeper=lambda _delay: None)
    assert len(result.pages) == 1 and result.truncated is True


def test_scan_uses_shared_immutable_snapshot_persistence(tmp_path):
    database = database_with_scope(tmp_path)
    root = "https://apply.mykaleidoscope.com/"
    first = "https://apply.mykaleidoscope.com/program/CommunityService2027"
    second = "https://apply.mykaleidoscope.com/program/College_Student-Award"
    pages = {
        root: html_page(root, "kaleidoscope_marketplace.html"),
        first: html_page(first, "kaleidoscope_program.html"),
        second: text_page(second, "Kaleidoscope College Award Qualifications Log In to Apply"),
    }
    run = execute_kaleidoscope_scan(database, "kaleidoscope-1", fetcher=Fetcher(pages), robots=Robots(), sleeper=lambda _delay: None)
    assert run.status == "succeeded" and run.snapshots_created == 3
    second_run = execute_kaleidoscope_scan(database, "kaleidoscope-1", fetcher=Fetcher(pages), robots=Robots(), sleeper=lambda _delay: None)
    assert second_run.status == "succeeded" and second_run.snapshots_created == 0 and second_run.unchanged_pages == 3
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SourceSnapshot)) == 3
    database.close()


def test_adapter_cannot_scan_a_scope_registered_for_another_adapter(tmp_path):
    database = database_with_scope(tmp_path, adapter="generic")
    with pytest.raises(RegistryError) as captured:
        execute_kaleidoscope_scan(database, "kaleidoscope-1", fetcher=Fetcher({}), robots=Robots(), sleeper=lambda _delay: None)
    assert captured.value.code == "source_not_scannable"
    database.close()
