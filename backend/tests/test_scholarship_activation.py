"""Acceptance tests for validation-driven scholarship activation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DatabaseError

from app.config import Settings
from app.database import Database
from app.extraction import ExtractionResult, TokenUsage
from app.extraction_schemas import ExtractedProgramDraft
from app.local_data import upgrade_database
from app.main import create_app
from app.models import (
    ExtractionActivationAttempt,
    Scholarship,
    ScholarshipVersion,
    SourceScanRun,
    SourceScope,
    SourceSnapshot,
)
from app.scholarship_activation import activate_validated_extraction
from conftest import FakeSecretStore


SOURCE = "Community Scholars Award. Applicants must have a 3.0 GPA. Submit a transcript."


def proposal(snapshot_id: str, *, name="Community Scholars Award", excerpt="Applicants must have a 3.0 GPA.") -> dict:
    return {
        "name": name,
        "description": "A scholarship for current college students.",
        "categories": ["scholarships"],
        "coverage": {"national": True, "states": [], "institutions": []},
        "checklist": [{
            "label": "Submit a transcript", "required": True,
            "evidence": {"snapshot_id": snapshot_id, "excerpt": "Submit a transcript."},
        }],
        "eligibility_tree": {
            "type": "condition", "field": "gpa", "operator": "gte", "value": 3.0,
            "evidence": {"snapshot_id": snapshot_id, "excerpt": excerpt}, "exceptions_complete": True,
        },
        "coverage_complete": True,
        "award_cycle": "2027",
        "application_deadline": "2027-03-01T17:00:00-05:00",
        "deadline_timezone": "America/New_York",
        "application_availability": "open",
        "assistance_amount": "$2,500",
        "selection_factors": [],
        "application_url": "https://sponsor.example/apply",
        "unresolved_conditions": [],
    }


def extraction(payload: dict) -> ExtractionResult:
    return ExtractionResult(
        draft=ExtractedProgramDraft.model_validate(payload), model="fixture-model",
        prompt_version="2.0.0", schema_version="1.0.0", request_id="request-1",
        usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
    )


def activation_database(tmp_path) -> tuple[Database, Settings]:
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    database = Database(settings)
    acquired = datetime(2026, 11, 1, tzinfo=timezone.utc)
    with database.sessions.begin() as db:
        db.add(SourceScope(
            id="source-1", name="Sponsor", ownership="sponsor", adapter="generic",
            canonical_url="https://sponsor.example/scholarships", hostname="sponsor.example",
            allowed_path_prefix="/scholarships", status="active", confirmed_at=acquired,
            max_depth=1, page_budget=10, requests_per_minute=10, scan_interval_hours=24,
            policy_status="allowed",
        ))
        db.flush()
        db.add(SourceScanRun(
            id="run-1", source_scope_id="source-1", status="succeeded", started_at=acquired,
            finished_at=acquired, pages_attempted=1, snapshots_created=1,
            unchanged_pages=0, traversal_truncated=False,
        ))
        db.flush()
        db.add(SourceSnapshot(
            id="snapshot-1", source_scope_id="source-1", scan_run_id="run-1",
            canonical_url="https://sponsor.example/scholarships/community", final_url="https://sponsor.example/scholarships/community",
            acquired_at=acquired, content_hash="a" * 64, media_type="text/html",
            normalized_text=SOURCE, source_byte_count=len(SOURCE), redirect_count=0, depth=1,
        ))
    return database, settings


def test_valid_activation_is_idempotent_and_history_is_immutable(tmp_path):
    database, _settings = activation_database(tmp_path)
    moment = datetime(2026, 11, 2, tzinfo=timezone.utc)
    first = activate_validated_extraction(database, "snapshot-1", extraction(proposal("snapshot-1")), now=lambda: moment)
    assert first.status == "activated" and first.version_id is not None
    repeated = activate_validated_extraction(database, "snapshot-1", extraction(proposal("snapshot-1")), now=lambda: moment)
    assert repeated.status == "unchanged" and repeated.version_id == first.version_id
    with database.sessions() as db:
        scholarship = db.get(Scholarship, first.scholarship_id)
        assert scholarship.active_version_id == first.version_id
        assert db.scalar(select(func.count()).select_from(ScholarshipVersion)) == 1
        assert db.scalar(select(func.count()).select_from(ExtractionActivationAttempt)) == 2
    with pytest.raises(DatabaseError):
        with database.sessions.begin() as db:
            db.execute(update(ScholarshipVersion).values(data={"name": "tampered"}))
    database.close()


def test_invalid_refresh_records_findings_and_preserves_prior_active_version(tmp_path):
    database, _settings = activation_database(tmp_path)
    valid = activate_validated_extraction(database, "snapshot-1", extraction(proposal("snapshot-1")))
    invalid_payload = proposal("snapshot-1", excerpt="Applicants must have a 4.0 GPA.")
    failed = activate_validated_extraction(database, "snapshot-1", extraction(invalid_payload))
    assert failed.status == "validation_failed"
    assert {item.code for item in failed.validation.findings} == {"excerpt_not_found"}
    with database.sessions() as db:
        scholarship = db.get(Scholarship, valid.scholarship_id)
        assert scholarship.active_version_id == valid.version_id
        attempt = db.scalar(select(ExtractionActivationAttempt).where(ExtractionActivationAttempt.status == "validation_failed"))
        assert attempt.findings[0]["code"] == "excerpt_not_found"
    database.close()


def test_non_scholarship_category_cannot_activate(tmp_path):
    database, _settings = activation_database(tmp_path)
    payload = proposal("snapshot-1")
    payload["categories"] = ["grants"]
    result = activate_validated_extraction(database, "snapshot-1", extraction(payload))
    assert result.status == "validation_failed"
    assert "unsupported_category" in {item.code for item in result.validation.findings}
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Scholarship)) == 0
    database.close()


def test_activated_version_drives_local_matches_without_publication(tmp_path):
    database, settings = activation_database(tmp_path)
    activated = activate_validated_extraction(database, "snapshot-1", extraction(proposal("snapshot-1")))
    database.close()
    app = create_app(settings, FakeSecretStore())
    with TestClient(app) as client:
        saved = client.patch("/api/profile", json={"fields": {"gpa": 3.5}})
        assert saved.status_code == 200
        response = client.get("/api/matches").json()
        assert response["catalog_status"] == "ready"
        assert len(response["results"]) == 1
        result = response["results"][0]
        assert result["scholarship_id"] == activated.scholarship_id
        assert result["name"] == "Community Scholars Award"
        assert result["award"] == "$2,500"
        assert result["match_label"] == "Strong match"
