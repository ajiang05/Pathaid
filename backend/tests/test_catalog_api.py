"""HTTP tests for the public published-program endpoints."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Program, ProgramRevision, SourceSnapshot


@pytest.fixture
def catalog_client():
    """Seed one public revision and one hidden draft for API tests."""

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        public_program = Program(slug="public-scholarship")
        public_revision = ProgramRevision(
            program=public_program,
            status="published",
            name="Public Synthetic Scholarship",
            description="Synthetic published record.",
            categories=["scholarships"],
            coverage={"type": "national"},
            checklist=[{"label": "Read the official instructions"}],
            eligibility_tree={
                "type": "condition",
                "field": "study_level",
                "operator": "eq",
                "value": "undergraduate",
                "evidence": {"snapshot_id": "synthetic", "excerpt": "Synthetic evidence."},
            },
            coverage_complete=True,
            award_cycle="Synthetic cycle",
            application_availability="open",
            assistance_amount="Amount stated by synthetic source",
            selection_factors=["Synthetic selection factor"],
            provider_url="https://example.edu/program",
            application_url="https://example.edu/apply",
            verified_at=datetime.now(timezone.utc),
        )
        source = SourceSnapshot(
            source_url="https://example.edu/program",
            acquisition_method="webpage",
            content_hash="b" * 64,
            source_text="Private retained source body that must not appear in API output.",
        )
        public_revision.sources.append(source)
        hidden_program = Program(slug="hidden-draft")
        hidden_revision = ProgramRevision(
            program=hidden_program,
            status="draft",
            name="Hidden Synthetic Draft",
            description="This record must remain hidden.",
            categories=["grants"],
            coverage={"type": "national"},
            checklist=[],
            eligibility_tree={"type": "unsupported", "description": "Synthetic", "evidence": {"snapshot_id": "x", "excerpt": "Synthetic"}},
            coverage_complete=False,
            application_availability="unknown",
            selection_factors=[],
            provider_url="https://example.edu/hidden",
        )
        db.add_all([public_program, hidden_program])
        db.flush()
        public_program.current_published_revision_id = public_revision.id
        db.commit()
        public_id = public_program.id
        hidden_id = hidden_program.id

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            yield client, public_id, hidden_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_and_category_filter_are_published_only(catalog_client):
    """Lists include matching public data and never include drafts."""

    client, public_id, _ = catalog_client
    response = client.get("/api/programs")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [public_id]
    assert client.get("/api/programs", params={"categories": "grants"}).json() == []
    assert client.get("/api/programs", params={"categories": "invalid"}).status_code == 422


def test_detail_returns_provenance_without_source_body(catalog_client):
    """Details expose reviewed provenance but keep retained source text private."""

    client, public_id, _ = catalog_client
    response = client.get(f"/api/programs/{public_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision_id"]
    assert payload["sources"][0]["source_url"] == "https://example.edu/program"
    assert "source_text" not in payload["sources"][0]
    assert "Private retained source body" not in response.text


def test_detail_hides_drafts_and_unknown_programs(catalog_client):
    """Nonpublic and nonexistent IDs share the same not-found response."""

    client, _, hidden_id = catalog_client
    assert client.get(f"/api/programs/{hidden_id}").status_code == 404
    assert client.get("/api/programs/not-a-program").status_code == 404
