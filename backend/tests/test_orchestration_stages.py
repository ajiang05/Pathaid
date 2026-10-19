"""Tests for durable acquisition and extraction stage boundaries."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.extraction import DeterministicExtractionStub, ExtractionError
from app.extraction_schemas import ExtractedProgramDraft
from app.models import IngestionRun, IngestionStageAttempt, SourceSnapshot
from app.orchestration import IngestionSubmission, claim_next_run, create_ingestion_run
from app.orchestration_stages import process_acquisition_stage, process_extraction_stage
from app.source_acquisition import PastedSourceRequest


NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)


@pytest.fixture
def sessions(tmp_path):
    """Provide restart-capable sessions over a local file database."""

    engine = create_engine(f"sqlite:///{tmp_path / 'stages.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def extracted(snapshot_id: str) -> ExtractedProgramDraft:
    """Build a proposal whose only evidence occurs in the retained snapshot."""

    evidence = {"snapshot_id": snapshot_id, "excerpt": "Applicants must have a 3.0 GPA."}
    return ExtractedProgramDraft.model_validate(
        {
            "name": "Synthetic Award",
            "description": "Synthetic scholarship.",
            "categories": ["scholarships"],
            "coverage": {"national": True, "states": [], "institutions": []},
            "checklist": [],
            "eligibility_tree": {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": evidence, "exceptions_complete": True},
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


def create_pasted_run(db):
    """Queue a valid source without network access."""

    return create_ingestion_run(
        db,
        IngestionSubmission(
            "stage-test",
            PastedSourceRequest("https://example.edu/aid", "Applicants must have a 3.0 GPA."),
        ),
    )


def test_acquisition_atomically_persists_snapshot_and_transition(sessions):
    """A completed acquisition becomes a reusable extraction prerequisite."""

    with sessions() as db:
        run = create_pasted_run(db)
        lease = claim_next_run(db, "worker", clock=lambda: NOW)
        process_acquisition_stage(db, lease, clock=lambda: NOW)
        db.refresh(run)
        assert run.state == "extracting"
        assert run.lease_token is None
        assert db.get(SourceSnapshot, run.source_snapshot_id).source_text.endswith("3.0 GPA.")
        assert run.stage_attempts[0].outcome == "succeeded"


def test_extraction_persists_output_versions_and_usage(sessions):
    """A restart after extraction can validate without another model call."""

    with sessions() as db:
        run = create_pasted_run(db)
        process_acquisition_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
        lease = claim_next_run(db, "worker", clock=lambda: NOW)
        provider = DeterministicExtractionStub({run.source_snapshot_id: extracted(run.source_snapshot_id)})
        process_extraction_stage(db, lease, provider, clock=lambda: NOW)
        db.refresh(run)
        assert run.state == "validating"
        assert run.extracted_draft["name"] == "Synthetic Award"
        assert run.model == "deterministic-stub"
        assert run.prompt_version and run.schema_version
        assert len(run.stage_attempts) == 2


def test_transient_extraction_failure_uses_bounded_backoff(sessions):
    """Two transient failures retry, while the third terminates the run."""

    with sessions() as db:
        run = create_pasted_run(db)
        process_acquisition_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
        failure = DeterministicExtractionStub({run.source_snapshot_id: ExtractionError("provider_unavailable", "Provider unavailable.", retryable=True)})
        moments = [NOW, NOW + timedelta(seconds=5), NOW + timedelta(seconds=15)]
        for index, moment in enumerate(moments, start=1):
            lease = claim_next_run(db, "worker", clock=lambda moment=moment: moment)
            process_extraction_stage(db, lease, failure, clock=lambda moment=moment: moment)
            db.refresh(run)
            if index < 3:
                assert run.state == "extracting"
                assert run.next_attempt_at is not None
            else:
                assert run.state == "failed"
                assert run.completed_at is not None
        attempts = db.query(IngestionStageAttempt).filter_by(run_id=run.id, stage="extracting").all()
        assert [attempt.outcome for attempt in attempts] == ["retry_scheduled", "retry_scheduled", "failed"]


def test_nonretryable_extraction_failure_stops_immediately(sessions):
    """Refusals and configuration failures wait for administrator action."""

    with sessions() as db:
        run = create_pasted_run(db)
        process_acquisition_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
        provider = DeterministicExtractionStub({run.source_snapshot_id: ExtractionError("model_refusal", "The model declined.")})
        process_extraction_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), provider, clock=lambda: NOW)
        db.refresh(run)
        assert run.state == "failed"
        assert run.error_code == "model_refusal"
        assert len([attempt for attempt in run.stage_attempts if attempt.stage == "extracting"]) == 1
