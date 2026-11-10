"""API tests for essay CRUD, local fallback, and AI policy boundaries."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.essay_recommendation import EssayAnalysisResponse
from app.local_data import upgrade_database
from app.main import create_app
from app.models import Scholarship, ScholarshipVersion, SourceScanRun, SourceScope, SourceSnapshot
from app.secrets import GEMINI_API_KEY
from conftest import FakeSecretStore


ESSAY = {
    "title": "Community leadership",
    "original_prompt": "Describe your community service.",
    "text": "I organized a neighborhood food drive and learned to listen first.",
    "tags": ["service", "leadership"],
    "themes": ["community"],
    "written_on": "2026-10-01",
}


class RecordingProvider:
    def __init__(self, *, fail: bool = False):
        self.calls = []
        self.fail = fail

    def analyze(self, essays, destination_prompt, word_limit):
        self.calls.append((essays, destination_prompt, word_limit))
        if self.fail:
            raise RuntimeError("raw provider response must stay private")
        return EssayAnalysisResponse.model_validate({
            "rankings": [{
                "essay_id": essays[0].id,
                "rationale": "The existing service example addresses the prompt.",
                "mismatches": [{
                    "section_reference": "Closing paragraph",
                    "reason": "It focuses on a different future goal.",
                }],
            }]
        })


def configured_app(tmp_path, provider=None):
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    secrets = FakeSecretStore({GEMINI_API_KEY: "test-key"})
    if provider is None:
        app = create_app(settings, secrets)
    else:
        app = create_app(settings, secrets, lambda _key: provider)
    return app


def add_scholarship(app, policy: str) -> str:
    now = datetime(2026, 11, 2, tzinfo=timezone.utc)
    with app.state.database.sessions.begin() as db:
        db.add(SourceScope(
            id="scope", name="Sponsor", ownership="sponsor", adapter="generic",
            canonical_url="https://sponsor.example/scholarships", hostname="sponsor.example",
            allowed_path_prefix="/scholarships", status="paused", max_depth=1,
            page_budget=10, requests_per_minute=10, scan_interval_hours=24, policy_status="allowed",
        ))
        db.flush()
        db.add(SourceScanRun(
            id="run", source_scope_id="scope", status="succeeded", started_at=now, finished_at=now,
            pages_attempted=1, snapshots_created=1, unchanged_pages=0, traversal_truncated=False,
        ))
        db.flush()
        db.add(SourceSnapshot(
            id="snapshot", source_scope_id="scope", scan_run_id="run",
            canonical_url="https://sponsor.example/scholarships/1",
            final_url="https://sponsor.example/scholarships/1", acquired_at=now,
            content_hash="a" * 64, media_type="text/html", normalized_text="source",
            source_byte_count=6, redirect_count=0, depth=1,
        ))
        db.flush()
        scholarship = Scholarship(
            id="scholarship", source_url="https://sponsor.example/scholarships/1",
            active_version_id="version", status="active",
        )
        db.add(scholarship)
        db.flush()
        db.add(ScholarshipVersion(
            id="version", scholarship_id="scholarship", source_snapshot_id="snapshot",
            draft_hash="b" * 64, data={"name": "Award", "ai_assistance_policy": policy},
            validation_findings=[], extraction_model="fixture", prompt_version="fixture",
            schema_version="fixture", activated_at=now,
        ))
    return "scholarship"


def enable_analysis(client):
    response = client.put("/api/essays/analysis-settings", json={
        "full_text_analysis_enabled": True,
        "data_tier": "unpaid",
        "notice_acknowledged": True,
    })
    assert response.status_code == 200


def test_essay_crud_computes_word_count_and_records_use(tmp_path):
    app = configured_app(tmp_path)
    with TestClient(app) as client:
        created = client.post("/api/essays", json=ESSAY)
        assert created.status_code == 201
        essay_id = created.json()["id"]
        assert created.json()["word_count"] == 11
        assert client.get("/api/essays").json()["items"][0]["text"] == ESSAY["text"]

        use = client.post(f"/api/essays/items/{essay_id}/uses", json={
            "scholarship_name": "Community Award",
            "destination_prompt": "How did you serve your community?",
        })
        assert use.status_code == 201
        assert client.get("/api/essays").json()["items"][0]["uses"][0]["scholarship_name"] == "Community Award"

        updated = client.put(f"/api/essays/items/{essay_id}", json={**ESSAY, "title": "Updated title"})
        assert updated.json()["title"] == "Updated title"
        assert client.delete(f"/api/essays/items/{essay_id}").status_code == 204
        assert client.get("/api/essays").json() == {"items": []}


def test_ai_policy_block_prevents_provider_call(tmp_path):
    provider = RecordingProvider()
    app = configured_app(tmp_path, provider)
    scholarship_id = add_scholarship(app, "blocked")
    with TestClient(app) as client:
        client.post("/api/essays", json=ESSAY)
        enable_analysis(client)
        result = client.post("/api/essays/recommendations", json={
            "destination_prompt": "Describe service.", "scholarship_id": scholarship_id,
            "use_gemini": True,
        }).json()
    assert result["source"] == "local"
    assert result["ai_policy"] == "blocked"
    assert provider.calls == []


def test_explicit_configuration_allows_gemini_analysis(tmp_path):
    provider = RecordingProvider()
    app = configured_app(tmp_path, provider)
    with TestClient(app) as client:
        client.post("/api/essays", json=ESSAY)
        enable_analysis(client)
        result = client.post("/api/essays/recommendations", json={
            "destination_prompt": "Describe service.", "word_limit": 500, "use_gemini": True,
        }).json()
    assert result["source"] == "gemini"
    assert result["items"][0]["mismatches"][0]["section_reference"] == "Closing paragraph"
    assert len(provider.calls) == 1


def test_provider_failure_returns_local_result(tmp_path):
    provider = RecordingProvider(fail=True)
    app = configured_app(tmp_path, provider)
    with TestClient(app) as client:
        client.post("/api/essays", json=ESSAY)
        enable_analysis(client)
        response = client.post("/api/essays/recommendations", json={
            "destination_prompt": "Describe leadership.", "use_gemini": True,
        })
    assert response.status_code == 200
    assert response.json()["source"] == "local"
    assert "local recommendations" in response.json()["warning"]


def test_unknown_data_tier_prevents_provider_call(tmp_path):
    provider = RecordingProvider()
    app = configured_app(tmp_path, provider)
    with TestClient(app) as client:
        client.post("/api/essays", json=ESSAY)
        client.put("/api/essays/analysis-settings", json={
            "full_text_analysis_enabled": True, "data_tier": "unknown",
            "notice_acknowledged": True,
        })
        result = client.post("/api/essays/recommendations", json={
            "destination_prompt": "Describe service.", "use_gemini": True,
        }).json()
    assert result["source"] == "local"
    assert "Select the configured Gemini account tier" in result["warning"]
    assert provider.calls == []
