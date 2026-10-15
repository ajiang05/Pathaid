"""Tests for consent-gated, source-backed recommendation explanations."""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Program, ProgramRevision, RecommendationAttempt, SourceSnapshot
from app.recommendations import RecommendationError, RecommendationModelResult, RecommendationUsage
from app.recommendation_schemas import ModelRecommendationSelection


@dataclass
class StubProvider:
    """Capture the privacy-minimized payload and return a selected reason."""

    selection: ModelRecommendationSelection
    payload: dict | None = None

    def select(self, payload):
        self.payload = payload
        return RecommendationModelResult(self.selection, "stub-model", RecommendationUsage(10, 5, 15))


class FailingProvider:
    """Represent a safe provider refusal without external calls."""

    def select(self, payload):
        raise RecommendationError("model_refusal")


@pytest.fixture
def recommendation_client():
    """Provide current and historical published revisions for one scholarship."""

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        program = Program(slug="versioned-scholarship")
        revisions = []
        for suffix, description in (("old", "Historical reviewed scholarship."), ("current", "Current reviewed scholarship.")):
            snapshot = SourceSnapshot(
                id=f"source-{suffix}",
                source_url=f"https://example.edu/{suffix}",
                acquisition_method="webpage",
                content_hash=("a" if suffix == "old" else "b") * 64,
                source_text="Applicants must have a GPA of at least 3.0.",
            )
            revision = ProgramRevision(
                program=program,
                status="published",
                name="Versioned Scholarship",
                description=description,
                categories=["scholarships"],
                coverage={"type": "national"},
                checklist=[{"label": "Submit an essay", "required": True}],
                eligibility_tree={
                    "type": "condition",
                    "field": "gpa",
                    "operator": "gte",
                    "value": 3.0,
                    "evidence": {"snapshot_id": snapshot.id, "excerpt": snapshot.source_text},
                },
                coverage_complete=True,
                application_availability="open",
                assistance_amount="$1,000",
                selection_factors=[{"description": "Essay quality"}],
                provider_url="https://example.edu/scholarship",
            )
            revision.sources.append(snapshot)
            revisions.append(revision)
        db.add(program)
        db.flush()
        program.current_published_revision_id = revisions[1].id
        db.commit()
        program_id = program.id
        old_revision_id = revisions[0].id

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            signup = client.post("/api/auth/signup", json={"email": "recommend@example.edu", "password": "strong password 123"})
            yield client, engine, program_id, old_revision_id, signup.json()["csrf_token"]
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "recommendation_provider"):
            del app.state.recommendation_provider
        engine.dispose()


def enable_ai(client, csrf):
    """Record consent and a saved value that is relevant to the rule."""

    response = client.patch(
        "/api/profile",
        headers={"X-CSRF-Token": csrf},
        json={"fields": {"gpa": 3.5, "school": "Private University"}, "ai_opt_in": True},
    )
    assert response.status_code == 200


def endpoint(program_id):
    """Return the explanation path for one stable program."""

    return f"/api/programs/{program_id}/recommendation-explanation"


def test_opt_out_uses_template_without_calling_provider(recommendation_client):
    """Declining AI preserves deterministic explanations and creates no usage row."""

    client, engine, program_id, revision_id, _ = recommendation_client
    app.state.recommendation_provider = FailingProvider()
    response = client.post(endpoint(program_id), json={"revision_id": revision_id})
    assert response.status_code == 200
    assert response.json()["generated_by"] == "template"
    assert response.json()["fallback_reason"] == "ai_opt_out"
    with Session(engine) as db:
        assert db.scalars(select(RecommendationAttempt)).all() == []


def test_missing_provider_key_uses_template(recommendation_client, monkeypatch):
    """A local or deployed server without model credentials remains usable."""

    client, engine, program_id, revision_id, csrf = recommendation_client
    enable_ai(client, csrf)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(endpoint(program_id), json={"revision_id": revision_id})
    assert response.status_code == 200
    assert response.json()["generated_by"] == "template"
    assert response.json()["fallback_reason"] == "missing_api_key"
    with Session(engine) as db:
        assert db.scalars(select(RecommendationAttempt)).one().outcome == "missing_api_key"


def test_model_receives_only_relevant_profile_data_and_exact_revision(recommendation_client):
    """An old published result stays reproducible and excludes identity and unrelated fields."""

    client, engine, program_id, revision_id, csrf = recommendation_client
    enable_ai(client, csrf)
    provider = StubProvider(ModelRecommendationSelection(emphasis="eligibility", criterion_ids=["criterion-1"]))
    app.state.recommendation_provider = provider

    response = client.post(endpoint(program_id), json={"revision_id": revision_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision_id"] == revision_id
    assert payload["generated_by"] == "model_assisted"
    assert "does not predict selection or an award" in payload["explanation"]
    assert provider.payload["profile"] == {"gpa": 3.5}
    assert "email" not in str(provider.payload).lower()
    assert "Private University" not in str(provider.payload)
    with Session(engine) as db:
        attempt = db.scalars(select(RecommendationAttempt)).one()
        assert attempt.outcome == "success"
        assert attempt.total_tokens == 15
        assert not hasattr(attempt, "prompt")
        assert not hasattr(attempt, "explanation")


def test_unsupported_model_ids_and_refusals_fall_back(recommendation_client):
    """Provider output cannot introduce a requirement that the server did not supply."""

    client, engine, program_id, revision_id, csrf = recommendation_client
    enable_ai(client, csrf)
    app.state.recommendation_provider = StubProvider(
        ModelRecommendationSelection(emphasis="eligibility", criterion_ids=["invented-requirement"])
    )
    invalid = client.post(endpoint(program_id), json={"revision_id": revision_id})
    assert invalid.json()["generated_by"] == "template"
    assert invalid.json()["fallback_reason"] == "unsupported_selection"

    app.state.recommendation_provider = FailingProvider()
    refused = client.post(endpoint(program_id), json={"revision_id": revision_id})
    assert refused.json()["generated_by"] == "template"
    assert refused.json()["fallback_reason"] == "model_refusal"
    with Session(engine) as db:
        assert [item.outcome for item in db.scalars(select(RecommendationAttempt).order_by(RecommendationAttempt.id))] == [
            "unsupported_selection",
            "model_refusal",
        ]


def test_rate_limit_returns_template_and_historical_ownership_is_enforced(recommendation_client, monkeypatch):
    """Bound model attempts and reject revisions belonging to another program."""

    client, _, program_id, revision_id, csrf = recommendation_client
    enable_ai(client, csrf)
    monkeypatch.setenv("PATHAID_RECOMMENDATION_ATTEMPTS_PER_HOUR", "1")
    app.state.recommendation_provider = StubProvider(
        ModelRecommendationSelection(emphasis="application_readiness", criterion_ids=["criterion-1"])
    )
    assert client.post(endpoint(program_id), json={"revision_id": revision_id}).json()["generated_by"] == "model_assisted"
    limited = client.post(endpoint(program_id), json={"revision_id": revision_id})
    assert limited.json()["fallback_reason"] == "rate_limited"
    assert client.post(endpoint("another-program"), json={"revision_id": revision_id}).status_code == 404
