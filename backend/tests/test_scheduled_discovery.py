"""Feature 12 tests for durable, bounded scholarship source refresh."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base
from app.database import get_db
from app.extraction import DeterministicExtractionStub
from app.extraction_schemas import ExtractedProgramDraft
from app.main import app, password_hash
from app.models import IngestionRun, ScheduledScan, ScheduledSource, SourceSnapshot
from app.orchestration import claim_next_run
from app.orchestration_stages import process_acquisition_stage, process_extraction_stage, process_validation_stage
from app.scheduled_discovery import allowed_candidate_urls, enqueue_due_sources, robots_allows
from app.source_acquisition import AcquiredSource, HttpResponse, hash_text


NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scheduled.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def source(**overrides) -> ScheduledSource:
    values = {
        "canonical_url": "https://aid.example.edu/scholarships",
        "source_type": "program_page",
        "enabled": True,
        "cadence_hours": 24,
        "allowed_hostname": "aid.example.edu",
        "allowed_path_prefix": "/scholarships",
        "discovery_link_limit": 0,
        "respect_robots": False,
        "next_scan_at": NOW,
        "created_by": "admin@pathaid.example",
    }
    values.update(overrides)
    return ScheduledSource(**values)


def test_due_window_is_enqueued_once_and_advanced(sessions):
    """Repeated scheduler cycles cannot duplicate one source/window."""

    with sessions() as db:
        db.add(source())
        db.commit()
        first = enqueue_due_sources(db, clock=lambda: NOW)
        second = enqueue_due_sources(db, clock=lambda: NOW)
        assert len(first) == 1
        assert second == []
        assert db.scalar(select(ScheduledScan).where(ScheduledScan.source_id == first[0].scheduled_source_id))
        assert db.query(IngestionRun).count() == 1
        stored = db.get(ScheduledSource, first[0].scheduled_source_id)
        next_scan = stored.next_scan_at.replace(tzinfo=timezone.utc) if stored.next_scan_at.tzinfo is None else stored.next_scan_at
        assert next_scan == datetime(2027, 1, 3, 12, tzinfo=timezone.utc)


def test_same_host_is_limited_to_one_source_per_cycle(sessions):
    """A scheduler batch does not burst several requests at one host."""

    with sessions() as db:
        db.add_all([
            source(canonical_url="https://aid.example.edu/scholarships/a"),
            source(canonical_url="https://aid.example.edu/scholarships/b"),
        ])
        db.commit()
        assert len(enqueue_due_sources(db, clock=lambda: NOW, limit=10)) == 1


def test_unchanged_page_completes_before_extraction(sessions):
    """Hash equality records freshness without a snapshot or model stage."""

    page = b"<html><body>Same scholarship text</body></html>"
    normalized_hash = hash_text("Same scholarship text")
    with sessions() as db:
        db.add(source(last_content_hash=normalized_hash))
        db.commit()
        run = enqueue_due_sources(db, clock=lambda: NOW)[0]
        lease = claim_next_run(db, "worker", clock=lambda: NOW)

        class Transport:
            def fetch(self, *_args, **_kwargs):
                return HttpResponse(200, {"content-type": "text/html; charset=utf-8"}, page)

        process_acquisition_stage(
            db,
            lease,
            clock=lambda: NOW,
            resolver=lambda _host, _port: ["93.184.216.34"],
            transport=Transport(),
        )
        db.refresh(run)
        scan = db.get(ScheduledScan, run.scheduled_scan_id)
        assert run.state == "unchanged"
        assert run.source_snapshot_id is None
        assert scan.outcome == "unchanged"
        assert db.query(SourceSnapshot).count() == 0


def test_discovery_links_are_canonical_bounded_and_same_scope():
    """One-hop discovery rejects other hosts and paths before queueing."""

    configured = source(
        source_type="discovery_page",
        discovery_link_limit=2,
        allowed_path_prefix="/scholarships/",
    )
    acquired = AcquiredSource(
        original_url=configured.canonical_url,
        final_url=configured.canonical_url,
        acquisition_method="webpage",
        media_type="text/html",
        normalized_text="Index",
        content_hash=hash_text("Index"),
        source_byte_count=100,
        redirect_count=0,
        discovered_links=(
            "/scholarships/a",
            "https://evil.example/scholarships/b",
            "/other/c",
            "/scholarships/d#fragment",
            "/scholarships/e",
        ),
    )
    assert allowed_candidate_urls(configured, acquired) == [
        "https://aid.example.edu/scholarships/a",
        "https://aid.example.edu/scholarships/e",
    ]


def test_discovery_scope_requires_a_path_segment_boundary():
    """A similarly named sibling path is outside an approved path prefix."""

    configured = source(source_type="discovery_page", discovery_link_limit=5)
    acquired = AcquiredSource(
        original_url=configured.canonical_url,
        final_url=configured.canonical_url,
        acquisition_method="webpage",
        media_type="text/html",
        normalized_text="Index",
        content_hash=hash_text("Index"),
        source_byte_count=100,
        redirect_count=0,
        discovered_links=("/scholarships/new", "/scholarships-archive/old"),
    )
    assert allowed_candidate_urls(configured, acquired) == ["https://aid.example.edu/scholarships/new"]


def test_discovery_scan_queues_private_candidate_run(sessions):
    """A changed index page queues scoped candidates without publishing them."""

    page = b'<html><body><a href="/scholarships/new-award">New award</a></body></html>'
    with sessions() as db:
        db.add(source(source_type="discovery_page", discovery_link_limit=5, allowed_path_prefix="/scholarships/"))
        db.commit()
        parent = enqueue_due_sources(db, clock=lambda: NOW)[0]
        lease = claim_next_run(db, "worker", clock=lambda: NOW)

        class Transport:
            def fetch(self, *_args, **_kwargs):
                return HttpResponse(200, {"content-type": "text/html; charset=utf-8"}, page)

        process_acquisition_stage(
            db,
            lease,
            clock=lambda: NOW,
            resolver=lambda _host, _port: ["93.184.216.34"],
            transport=Transport(),
        )
        db.refresh(parent)
        scan = db.get(ScheduledScan, parent.scheduled_scan_id)
        candidates = db.query(IngestionRun).filter(IngestionRun.discovered_candidate_id.is_not(None)).all()
        assert parent.state == "discovered"
        assert scan.outcome == "discovered"
        assert scan.candidate_count == 1
        assert len(candidates) == 1
        assert candidates[0].source_url == "https://aid.example.edu/scholarships/new-award"
        assert candidates[0].state == "queued"


def test_changed_program_hash_waits_for_validated_draft(sessions):
    """Acquisition alone cannot make failed extraction look unchanged later."""

    page = b"<html><body>Changed scholarship text</body></html>"
    with sessions() as db:
        db.add(source())
        db.commit()
        run = enqueue_due_sources(db, clock=lambda: NOW)[0]
        lease = claim_next_run(db, "worker", clock=lambda: NOW)

        class Transport:
            def fetch(self, *_args, **_kwargs):
                return HttpResponse(200, {"content-type": "text/html; charset=utf-8"}, page)

        process_acquisition_stage(
            db,
            lease,
            clock=lambda: NOW,
            resolver=lambda _host, _port: ["93.184.216.34"],
            transport=Transport(),
        )
        db.refresh(run)
        stored = db.get(ScheduledSource, run.scheduled_source_id)
        assert run.state == "extracting"
        assert stored.last_content_hash is None
        assert stored.last_success_at is None


def test_validated_scheduled_change_finishes_scan_and_sets_baseline(sessions):
    """A reviewable changed page leaves no scan stuck in the running state."""

    page = b"<html><body>Applicants must have a 3.0 GPA.</body></html>"
    with sessions() as db:
        db.add(source())
        db.commit()
        run = enqueue_due_sources(db, clock=lambda: NOW)[0]

        class Transport:
            def fetch(self, *_args, **_kwargs):
                return HttpResponse(200, {"content-type": "text/html; charset=utf-8"}, page)

        process_acquisition_stage(
            db,
            claim_next_run(db, "worker", clock=lambda: NOW),
            clock=lambda: NOW,
            resolver=lambda _host, _port: ["93.184.216.34"],
            transport=Transport(),
        )
        draft = ExtractedProgramDraft.model_validate(
            {
                "name": "Scheduled Scholarship",
                "description": "A scheduled scholarship source.",
                "categories": ["scholarships"],
                "coverage": {"national": True, "states": [], "institutions": []},
                "checklist": [],
                "eligibility_tree": {
                    "type": "condition",
                    "field": "gpa",
                    "operator": "gte",
                    "value": 3.0,
                    "evidence": {"snapshot_id": run.source_snapshot_id, "excerpt": "Applicants must have a 3.0 GPA."},
                    "exceptions_complete": True,
                },
                "coverage_complete": True,
                "award_cycle": None,
                "application_deadline": None,
                "deadline_timezone": None,
                "application_availability": "unknown",
                "assistance_amount": None,
                "selection_factors": [],
                "application_url": None,
                "unresolved_conditions": [],
            }
        )
        provider = DeterministicExtractionStub({run.source_snapshot_id: draft})
        process_extraction_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), provider, clock=lambda: NOW)
        process_validation_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)

        db.refresh(run)
        scan = db.get(ScheduledScan, run.scheduled_scan_id)
        stored = db.get(ScheduledSource, run.scheduled_source_id)
        assert run.state == "awaiting_review"
        assert scan.outcome == "changed"
        assert scan.completed_at is not None
        assert stored.last_content_hash == scan.content_hash
        assert stored.last_success_at is not None


def test_robots_policy_can_block_a_scheduled_target():
    configured = source(respect_robots=True)
    assert not robots_allows(configured, "User-agent: *\nDisallow: /scholarships", configured.canonical_url, "PathaidBot/1.0")


def test_admin_can_manage_approved_sources_but_anonymous_user_cannot(monkeypatch):
    """Only the protected admin boundary can configure crawler targets."""

    monkeypatch.setenv("PATHAID_ADMIN_EMAIL", "admin@pathaid.example")
    monkeypatch.setenv("PATHAID_ADMIN_PASSWORD_HASH", password_hash("strong admin password 123"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            body = {
                "canonical_url": "https://aid.example.edu/scholarships",
                "source_type": "discovery_page",
                "allowed_path_prefix": "/scholarships/",
                "discovery_link_limit": 10,
            }
            assert client.post("/api/admin/scheduled-sources", json=body).status_code == 401
            login = client.post("/api/admin/auth/login", json={
                "email": "admin@pathaid.example", "password": "strong admin password 123"
            })
            headers = {"X-CSRF-Token": login.json()["csrf_token"]}
            created = client.post("/api/admin/scheduled-sources", headers=headers, json=body)
            assert created.status_code == 201
            source_id = created.json()["id"]
            assert client.get("/api/admin/scheduled-sources").json()[0]["allowed_hostname"] == "aid.example.edu"
            paused = client.patch(f"/api/admin/scheduled-sources/{source_id}", headers=headers, json={"enabled": False})
            assert paused.status_code == 200
            assert paused.json()["enabled"] is False
            due = client.post(f"/api/admin/scheduled-sources/{source_id}/scan", headers=headers)
            assert due.status_code == 202
            assert due.json()["status"] == "due"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
