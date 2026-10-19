"""Tests for the lightweight ingestion worker entry point."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.extraction import DeterministicExtractionStub
from app.extraction_schemas import ExtractedProgramDraft
from app.models import IngestionRun, ProgramRevision
from app.orchestration import IngestionSubmission, create_ingestion_run
from app.source_acquisition import PastedSourceRequest
from app.worker import WorkerConfig, process_next_run


NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)
SOURCE = "Applicants must have a 3.0 GPA."


@pytest.fixture
def sessions(tmp_path):
    """Provide a worker-compatible database session factory."""

    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def draft(snapshot_id):
    """Return a valid deterministic model result for the worker."""

    evidence = {"snapshot_id": snapshot_id, "excerpt": SOURCE}
    return ExtractedProgramDraft.model_validate(
        {
            "name": "Worker Award", "description": "Synthetic award.", "categories": ["scholarships"],
            "coverage": {"national": True, "states": [], "institutions": []}, "checklist": [],
            "eligibility_tree": {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": evidence, "exceptions_complete": True},
            "coverage_complete": True, "award_cycle": None, "application_deadline": None, "deadline_timezone": None,
            "application_availability": "unknown", "assistance_amount": None, "selection_factors": [],
            "application_url": None, "unresolved_conditions": [],
        }
    )


def test_acquisition_stage_does_not_construct_model_client(sessions):
    """A missing API key cannot block work that does not need extraction."""

    with sessions() as db:
        run = create_ingestion_run(db, IngestionSubmission("worker-1", PastedSourceRequest("https://example.edu/aid", SOURCE)))
    def forbidden_provider():
        raise AssertionError("provider should not be constructed")

    assert process_next_run(sessions, worker_id="worker", provider_factory=forbidden_provider, clock=lambda: NOW)
    with sessions() as db:
        assert db.get(IngestionRun, run.id).state == "extracting"


def test_three_worker_cycles_reach_admin_review_offline(sessions):
    """Acquisition, extraction, and validation resume across sessions."""

    with sessions() as db:
        run = create_ingestion_run(db, IngestionSubmission("worker-2", PastedSourceRequest("https://example.edu/aid", SOURCE)))
    process_next_run(sessions, worker_id="worker", provider_factory=lambda: None, clock=lambda: NOW)
    with sessions() as db:
        snapshot_id = db.get(IngestionRun, run.id).source_snapshot_id
    provider = DeterministicExtractionStub({snapshot_id: draft(snapshot_id)})
    process_next_run(sessions, worker_id="worker", provider_factory=lambda: provider, clock=lambda: NOW)
    process_next_run(sessions, worker_id="worker", provider_factory=lambda: None, clock=lambda: NOW)
    with sessions() as db:
        stored = db.get(IngestionRun, run.id)
        assert stored.state == "awaiting_review"
        assert stored.draft_revision_id
        assert db.query(ProgramRevision).count() == 1
    assert not process_next_run(sessions, worker_id="worker", provider_factory=lambda: provider, clock=lambda: NOW)
    with sessions() as db:
        assert db.query(ProgramRevision).count() == 1


def test_worker_returns_false_when_no_run_is_due(sessions):
    """Continuous mode can sleep instead of busy-polling an empty queue."""

    assert not process_next_run(sessions, worker_id="worker", provider_factory=lambda: None, clock=lambda: NOW)


def test_attempt_limit_cannot_exceed_three(monkeypatch):
    """Environment configuration preserves the specified retry ceiling."""

    monkeypatch.setenv("PATHAID_INGESTION_MAX_ATTEMPTS", "4")
    with pytest.raises(ValueError, match="cannot exceed 3"):
        WorkerConfig.from_env()
