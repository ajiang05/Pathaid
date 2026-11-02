"""Representative public AcademicWorks/Blackbaud listing adapter tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.academicworks import execute_academicworks_scan, traverse_academicworks
from app.config import Settings
from app.database import Database
from app.generic_directory import ScopeBoundary, TraversalFailure
from app.local_data import upgrade_database
from app.models import SourceScope, SourceSnapshot
from app.source_acquisition import AcquiredSource, extract_html_link_candidates, hash_text, normalize_html
from app.source_registry import RegistryError


FIXTURES = Path(__file__).parent / "fixtures"


def html_page(url: str, fixture: str):
    raw = (FIXTURES / fixture).read_text(encoding="utf-8")
    text = normalize_html(raw, 100_000)
    links = extract_html_link_candidates(raw)
    return AcquiredSource(
        original_url=url, final_url=url, acquisition_method="webpage", media_type="text/html",
        normalized_text=text, content_hash=hash_text(text), source_byte_count=len(raw.encode()),
        redirect_count=0, discovered_links=tuple(item.href for item in links), discovered_link_candidates=links,
    )


def text_page(url: str, text: str, links=()):
    return AcquiredSource(
        original_url=url, final_url=url, acquisition_method="webpage", media_type="text/html",
        normalized_text=text, content_hash=hash_text(text), source_byte_count=len(text.encode()),
        redirect_count=0, discovered_links=tuple(item.href for item in links), discovered_link_candidates=tuple(links),
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


def boundary(**changes):
    values = {
        "id": "academic-1", "canonical_url": "https://school.academicworks.com/opportunities", "hostname": "school.academicworks.com",
        "allowed_path_prefix": "/", "max_depth": 1, "page_budget": 10,
        "requests_per_minute": 60, "scan_interval_hours": 24,
    }
    values.update(changes)
    return ScopeBoundary(**values)


def database_with_scope(tmp_path, adapter="academicworks"):
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    database = Database(settings)
    with database.sessions.begin() as db:
        db.add(SourceScope(
            id="academic-1", name="School opportunities", ownership="school", adapter=adapter,
            canonical_url="https://school.academicworks.com/opportunities", hostname="school.academicworks.com", allowed_path_prefix="/",
            status="active", confirmed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            max_depth=1, page_budget=10, requests_per_minute=60, scan_interval_hours=24, policy_status="allowed",
        ))
    return database


def test_follows_only_numeric_opportunities_and_public_pagination():
    root = "https://school.academicworks.com/opportunities"
    one = "https://school.academicworks.com/opportunities/33001"
    two = "https://school.academicworks.com/opportunities/33002"
    page_two = "https://school.academicworks.com/?page=2"
    three = "https://school.academicworks.com/opportunities/33003"
    listing = html_page(root, "academicworks_listing.html")
    page_two_links = type(listing.discovered_link_candidates[0])
    second_listing = text_page(page_two, "All Opportunities Opportunities Table", (
        page_two_links("/opportunities/33003", "Third Scholarship"),
        page_two_links("/?page=0", "Previous"),
    ))
    fetcher = Fetcher({
        root: listing,
        one: html_page(one, "academicworks_detail.html"),
        two: text_page(two, "Community Leadership Award details"),
        page_two: second_listing,
        three: text_page(three, "Third Scholarship details"),
    })
    result = traverse_academicworks(boundary(), fetcher, Robots(), sleeper=lambda _delay: None)
    assert [page.acquired.original_url for page in result.pages] == [root, one, two, page_two, three]
    assert not any("sign_in" in url or "external" in url or "outside.example" in url for url in fetcher.calls)
    assert result.truncated is False


def test_signature_mismatch_and_robots_denial_fail_closed():
    root = "https://school.academicworks.com/opportunities"
    with pytest.raises(TraversalFailure) as mismatch:
        traverse_academicworks(boundary(), Fetcher({root: text_page(root, "Generic page")}), Robots(), sleeper=lambda _delay: None)
    assert mismatch.value.code == "adapter_signature_mismatch"
    with pytest.raises(TraversalFailure) as denied:
        traverse_academicworks(boundary(), Fetcher({}), Robots(False), sleeper=lambda _delay: None)
    assert denied.value.code == "robots_denied"


def test_empty_branded_public_listing_is_valid():
    root = "https://school.academicworks.com/opportunities"
    empty = text_page(root, "All Opportunities Opportunities Table © Blackbaud, Inc.")
    result = traverse_academicworks(boundary(), Fetcher({root: empty}), Robots(), sleeper=lambda _delay: None)
    assert [page.acquired.original_url for page in result.pages] == [root]


def test_budget_and_depth_are_enforced_for_portal_routes():
    root = "https://school.academicworks.com/opportunities"
    listing = html_page(root, "academicworks_listing.html")
    fetcher = Fetcher({root: listing})
    result = traverse_academicworks(boundary(page_budget=1), fetcher, Robots(), sleeper=lambda _delay: None)
    assert fetcher.calls == [root]
    assert result.truncated is True

    fetcher = Fetcher({root: listing, "https://school.academicworks.com/?page=2": text_page("https://school.academicworks.com/?page=2", "All Opportunities Opportunities Table", listing.discovered_link_candidates[:1])})
    result = traverse_academicworks(boundary(max_depth=0, page_budget=2), fetcher, Robots(), sleeper=lambda _delay: None)
    assert all(page.depth == 0 for page in result.pages)
    assert not any("/opportunities/3300" in url for url in fetcher.calls)


def test_academicworks_scan_uses_shared_immutable_snapshot_persistence(tmp_path):
    database = database_with_scope(tmp_path)
    root = "https://school.academicworks.com/opportunities"
    one = "https://school.academicworks.com/opportunities/33001"
    two = "https://school.academicworks.com/opportunities/33002"
    page_two = "https://school.academicworks.com/?page=2"
    listing = html_page(root, "academicworks_listing.html")
    pages = {
        root: listing,
        one: html_page(one, "academicworks_detail.html"),
        two: text_page(two, "Opportunity details"),
        page_two: text_page(page_two, "All Opportunities Opportunities Table", ()),
    }
    # The empty second page lacks opportunity links, so the platform signature
    # must fail rather than treating a generic HTML page as portal data.
    run = execute_academicworks_scan(database, "academic-1", fetcher=Fetcher(pages), robots=Robots(), sleeper=lambda _delay: None)
    assert run.status == "failed" and run.error_code == "adapter_signature_mismatch"
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SourceSnapshot)) == 0

    # Remove pagination from the saved fixture and prove successful persistence.
    trimmed_links = tuple(item for item in listing.discovered_link_candidates if "page=" not in item.href)
    pages[root] = AcquiredSource(
        **{**listing.__dict__, "discovered_links": tuple(item.href for item in trimmed_links), "discovered_link_candidates": trimmed_links}
    )
    run = execute_academicworks_scan(database, "academic-1", fetcher=Fetcher(pages), robots=Robots(), sleeper=lambda _delay: None)
    assert run.status == "succeeded" and run.snapshots_created == 3
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SourceSnapshot)) == 3
    database.close()


def test_adapter_cannot_scan_a_scope_registered_for_another_adapter(tmp_path):
    database = database_with_scope(tmp_path, adapter="generic")
    with pytest.raises(RegistryError) as captured:
        execute_academicworks_scan(database, "academic-1", fetcher=Fetcher({}), robots=Robots(), sleeper=lambda _delay: None)
    assert captured.value.code == "source_not_scannable"
    database.close()
