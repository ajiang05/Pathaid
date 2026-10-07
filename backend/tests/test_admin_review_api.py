"""Protected API tests for inspecting and editing review drafts."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, password_hash
from app.models import IngestionRun, Program, ProgramRevision, ReviewEvent, SourceSnapshot


SOURCE = "Synthetic Award. Applicants must have a 3.0 GPA."


@pytest.fixture
def review_client(monkeypatch):
    """Provide an authenticated-capable API and reviewable synthetic draft."""

    monkeypatch.setenv("PATHAID_ADMIN_EMAIL", "admin@pathaid.example")
    monkeypatch.setenv("PATHAID_ADMIN_PASSWORD_HASH", password_hash("strong admin password 123"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        program = Program(slug="synthetic-award")
        snapshot = SourceSnapshot(
            source_url="https://example.edu/aid",
            final_url="https://example.edu/aid",
            acquisition_method="pasted_text",
            content_hash="a" * 64,
            source_text=SOURCE,
        )
        revision = ProgramRevision(
            program=program,
            status="draft",
            validation_status="valid",
            validation_findings=[],
            name="Synthetic Award",
            description="Synthetic scholarship.",
            categories=["scholarships"],
            coverage={"national": True, "states": [], "institutions": []},
            checklist=[],
            eligibility_tree={"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": {"snapshot_id": "temporary", "excerpt": "Applicants must have a 3.0 GPA."}, "exceptions_complete": True},
            coverage_complete=False,
            application_availability="unknown",
            selection_factors=[],
            unresolved_conditions=[],
            provider_url="https://example.edu/aid",
        )
        revision.sources.append(snapshot)
        db.add(program)
        db.flush()
        revision.eligibility_tree["evidence"]["snapshot_id"] = snapshot.id
        run = IngestionRun(
            idempotency_key="review-run",
            request_fingerprint="b" * 64,
            target_program_id=program.id,
            source_url=snapshot.source_url,
            source_method="pasted_text",
            state="awaiting_review",
            source_snapshot_id=snapshot.id,
            draft_revision_id=revision.id,
            extracted_draft=editable_draft(snapshot.id),
            validation_findings=[],
        )
        db.add(run)
        db.commit()
        identifiers = {"program": program.id, "revision": revision.id, "snapshot": snapshot.id}

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        yield client, engine, identifiers
    app.dependency_overrides.clear()
    engine.dispose()


def editable_draft(snapshot_id, excerpt="Applicants must have a 3.0 GPA."):
    """Return the complete strict extraction shape used for human edits."""

    return {
        "name": "Synthetic Award",
        "description": "Reviewed synthetic scholarship.",
        "categories": ["scholarships"],
        "coverage": {"national": True, "states": [], "institutions": []},
        "checklist": [],
        "eligibility_tree": {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": {"snapshot_id": snapshot_id, "excerpt": excerpt}, "exceptions_complete": True},
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


def authenticate(api):
    """Return the administrator CSRF header."""

    response = api.post("/api/admin/auth/login", json={"email": "admin@pathaid.example", "password": "strong admin password 123"})
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_revision_detail_and_history_are_admin_only(review_client):
    """Protected review data includes source text while public access is denied."""

    api, _, ids = review_client
    assert api.get(f"/api/admin/revisions/{ids['revision']}").status_code == 401
    authenticate(api)
    detail = api.get(f"/api/admin/revisions/{ids['revision']}")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["source_text"] == SOURCE
    history = api.get(f"/api/admin/programs/{ids['program']}/revisions")
    assert history.status_code == 200
    assert history.json()["revisions"][0]["id"] == ids["revision"]


def test_valid_edit_is_revalidated_but_not_attested_complete(review_client):
    """A source-backed edit becomes valid while completeness remains false."""

    api, engine, ids = review_client
    headers = authenticate(api)
    body = {"draft": editable_draft(ids["snapshot"]), "provider_url": "https://example.edu/aid"}
    response = api.patch(f"/api/admin/revisions/{ids['revision']}", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["validation_status"] == "valid"
    assert response.json()["coverage_complete"] is False
    with Session(engine) as db:
        run = db.query(IngestionRun).filter_by(draft_revision_id=ids["revision"]).one()
        assert run.extracted_draft["description"] == "Reviewed synthetic scholarship."


def test_invented_evidence_is_saved_as_invalid_and_cannot_look_valid(review_client):
    """Reviewers can see and correct a semantic edit that fails evidence checks."""

    api, engine, ids = review_client
    headers = authenticate(api)
    body = {
        "draft": editable_draft(ids["snapshot"], "Applicants must have a 3.5 GPA."),
        "provider_url": "https://example.edu/aid",
    }
    response = api.patch(f"/api/admin/revisions/{ids['revision']}", headers=headers, json=body)
    assert response.status_code == 200
    assert response.json()["validation_status"] == "invalid"
    assert response.json()["validation_findings"][0]["code"] == "excerpt_not_found"
    with Session(engine) as db:
        revision = db.get(ProgramRevision, ids["revision"])
        assert revision.eligibility_tree["evidence"]["excerpt"].endswith("3.5 GPA.")


def test_published_revision_is_immutable(review_client):
    """Admin editing cannot modify a revision after publication."""

    api, engine, ids = review_client
    headers = authenticate(api)
    with Session(engine) as db:
        revision = db.get(ProgramRevision, ids["revision"])
        revision.status = "published"
        db.commit()
    body = {"draft": editable_draft(ids["snapshot"]), "provider_url": "https://example.edu/aid"}
    assert api.patch(f"/api/admin/revisions/{ids['revision']}", headers=headers, json=body).status_code == 409


def test_approval_requires_attestations_and_publishes_atomically(review_client):
    """One explicit approval updates revision, run, pointer, and review history."""

    api, engine, ids = review_client
    headers = authenticate(api)
    missing_attestation = api.post(
        f"/api/admin/revisions/{ids['revision']}/approve",
        headers=headers,
        json={"source_accurate": False, "coverage_complete": True},
    )
    assert missing_attestation.status_code == 422
    response = api.post(
        f"/api/admin/revisions/{ids['revision']}/approve",
        headers=headers,
        json={"source_accurate": True, "coverage_complete": True, "notes": "Reviewed against source."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    assert response.json()["coverage_complete"] is True
    # The existing public catalog route now resolves the approved revision.
    assert api.get(f"/api/programs/{ids['program']}").status_code == 200
    with Session(engine) as db:
        program = db.get(Program, ids["program"])
        run = db.query(IngestionRun).filter_by(draft_revision_id=ids["revision"]).one()
        events = db.query(ReviewEvent).filter_by(revision_id=ids["revision"]).all()
        assert program.current_published_revision_id == ids["revision"]
        assert run.state == "published"
        assert len(events) == 1
        assert events[0].decision == "approved"


def test_repeated_approval_cannot_create_duplicate_events(review_client):
    """A second decision returns conflict and preserves one recorded event."""

    api, engine, ids = review_client
    headers = authenticate(api)
    body = {"source_accurate": True, "coverage_complete": True}
    assert api.post(f"/api/admin/revisions/{ids['revision']}/approve", headers=headers, json=body).status_code == 200
    assert api.post(f"/api/admin/revisions/{ids['revision']}/approve", headers=headers, json=body).status_code == 409
    with Session(engine) as db:
        assert db.query(ReviewEvent).filter_by(revision_id=ids["revision"]).count() == 1


def test_incomplete_attestation_requires_retained_unresolved_logic(review_client):
    """A reviewer cannot claim incompleteness without explaining its cause."""

    api, _, ids = review_client
    headers = authenticate(api)
    response = api.post(
        f"/api/admin/revisions/{ids['revision']}/approve",
        headers=headers,
        json={"source_accurate": True, "coverage_complete": False},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "coverage_complete"


def test_incomplete_revision_can_publish_with_explicit_unresolved_condition(review_client):
    """Conservative publication retains ambiguity instead of claiming eligibility."""

    api, engine, ids = review_client
    headers = authenticate(api)
    unresolved = {
        "description": "The provider must interpret academic standing.",
        "evidence": {"snapshot_id": ids["snapshot"], "excerpt": "Applicants must have a 3.0 GPA."},
    }
    with Session(engine) as db:
        run = db.query(IngestionRun).filter_by(draft_revision_id=ids["revision"]).one()
        payload = editable_draft(ids["snapshot"])
        payload["coverage_complete"] = False
        payload["eligibility_tree"] = {
            "type": "unsupported",
            "description": unresolved["description"],
            "evidence": unresolved["evidence"],
        }
        payload["unresolved_conditions"] = [unresolved]
        run.extracted_draft = payload
        revision = db.get(ProgramRevision, ids["revision"])
        revision.eligibility_tree = payload["eligibility_tree"]
        revision.unresolved_conditions = [unresolved]
        revision.validation_status = "valid"
        db.commit()
    response = api.post(
        f"/api/admin/revisions/{ids['revision']}/approve",
        headers=headers,
        json={"source_accurate": True, "coverage_complete": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["coverage_complete"] is False
    assert response.json()["unresolved_conditions"] == [unresolved]


def test_rejection_preserves_public_pointer_and_records_decision(review_client):
    """Rejecting a candidate revision never makes it publicly readable."""

    api, engine, ids = review_client
    headers = authenticate(api)
    response = api.post(
        f"/api/admin/revisions/{ids['revision']}/reject",
        headers=headers,
        json={"notes": "Evidence needs clarification."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert api.get(f"/api/programs/{ids['program']}").status_code == 404
    with Session(engine) as db:
        program = db.get(Program, ids["program"])
        run = db.query(IngestionRun).filter_by(draft_revision_id=ids["revision"]).one()
        event = db.query(ReviewEvent).filter_by(revision_id=ids["revision"]).one()
        assert program.current_published_revision_id is None
        assert run.state == "rejected"
        assert event.decision == "rejected"
        assert event.notes == "Evidence needs clarification."
