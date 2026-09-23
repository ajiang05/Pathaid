"""HTTP tests connecting saved profiles, catalog rules, and evaluation."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Program, ProgramRevision


def catalog_revision(program: Program, name: str, rule: dict, *, status: str = "published") -> ProgramRevision:
    """Build a synthetic scholarship revision for endpoint tests."""

    return ProgramRevision(
        program=program,
        status=status,
        name=name,
        description="Synthetic evaluation fixture.",
        categories=["scholarships"],
        coverage={"type": "national"},
        checklist=[],
        eligibility_tree=rule,
        coverage_complete=True,
        application_availability="open",
        selection_factors=[],
        provider_url="https://example.edu/program",
    )


@pytest.fixture
def evaluation_client():
    """Provide an API with two published programs and one hidden draft."""

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        state_program = Program(slug="state-scholarship")
        state_revision = catalog_revision(
            state_program,
            "State Scholarship",
            {"type": "condition", "field": "state", "operator": "eq", "value": "MA", "evidence": {"snapshot_id": "state-source", "excerpt": "Applicant attends school in Massachusetts."}},
        )
        gpa_program = Program(slug="gpa-scholarship")
        gpa_revision = catalog_revision(
            gpa_program,
            "GPA Scholarship",
            {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": {"snapshot_id": "gpa-source", "excerpt": "Applicant has a GPA of at least 3.0."}},
        )
        draft_program = Program(slug="draft-scholarship")
        catalog_revision(
            draft_program,
            "Draft Scholarship",
            {"type": "condition", "field": "state", "operator": "eq", "value": "MA", "evidence": {"snapshot_id": "draft-source", "excerpt": "Synthetic draft evidence."}},
            status="draft",
        )
        db.add_all([state_program, gpa_program, draft_program])
        db.flush()
        state_program.current_published_revision_id = state_revision.id
        gpa_program.current_published_revision_id = gpa_revision.id
        db.commit()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def authenticate(client: TestClient) -> str:
    """Create a student and return the CSRF token used to save a profile."""

    response = client.post("/api/auth/signup", json={"email": "evaluation@example.edu", "password": "strong password 123"})
    assert response.status_code == 201
    return response.json()["csrf_token"]


def test_evaluation_combines_saved_and_temporary_answers_without_saving(evaluation_client):
    """Session answers override evaluation input but never alter the profile."""

    csrf = authenticate(evaluation_client)
    saved = evaluation_client.patch(
        "/api/profile",
        headers={"X-CSRF-Token": csrf},
        json={"fields": {"state": "MA", "assistance_categories": ["scholarships"]}},
    )
    assert saved.status_code == 200

    baseline = evaluation_client.post("/api/evaluate", json={})
    assert baseline.status_code == 200
    by_name = {result["name"]: result for result in baseline.json()["results"]}
    assert by_name["State Scholarship"]["label"] == "Likely eligible"
    assert by_name["GPA Scholarship"]["label"] == "Need more information"
    assert by_name["GPA Scholarship"]["missing_fields"][0]["field"] == "gpa"

    temporary = evaluation_client.post(
        "/api/evaluate",
        json={"answers": {"state": "NY", "gpa": 3.5}, "categories": ["scholarships"]},
    )
    by_name = {result["name"]: result for result in temporary.json()["results"]}
    assert by_name["State Scholarship"]["label"] == "Likely ineligible"
    assert by_name["GPA Scholarship"]["label"] == "Likely eligible"
    assert evaluation_client.get("/api/profile").json()["fields"]["state"] == "MA"


def test_evaluation_requires_authentication_and_valid_categories(evaluation_client):
    """Only signed-in students can evaluate supported assistance categories."""

    assert evaluation_client.post("/api/evaluate", json={"categories": ["scholarships"]}).status_code == 401
    authenticate(evaluation_client)
    assert evaluation_client.post("/api/evaluate", json={"categories": ["invalid"]}).status_code == 422
    assert evaluation_client.post("/api/evaluate", json={"categories": []}).status_code == 422


def test_evaluation_uses_published_candidates_only(evaluation_client):
    """A draft revision cannot appear in student evaluation results."""

    authenticate(evaluation_client)
    response = evaluation_client.post("/api/evaluate", json={"categories": ["scholarships"]})
    names = {result["name"] for result in response.json()["results"]}
    assert names == {"State Scholarship", "GPA Scholarship"}
