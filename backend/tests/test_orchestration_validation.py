"""End-to-end offline tests for validation and reviewable draft creation."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.extraction import DeterministicExtractionStub
from app.extraction_schemas import ExtractedProgramDraft
from app.models import IngestionRun, Program, ProgramRevision, SourceSnapshot
from app.orchestration import IngestionSubmission, claim_next_run, create_ingestion_run
from app.orchestration_stages import process_acquisition_stage, process_extraction_stage, process_validation_stage
from app.source_acquisition import PastedSourceRequest


NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)
SOURCE = "Synthetic Award. Applicants must have a 3.0 GPA. Preference is given to volunteers."


@pytest.fixture
def sessions(tmp_path):
    """Provide durable sessions for the complete offline workflow."""

    engine = create_engine(f"sqlite:///{tmp_path / 'validation.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def proposal(snapshot_id: str, *, excerpt="Applicants must have a 3.0 GPA.") -> ExtractedProgramDraft:
    """Build a reviewable proposal with mandatory and selection evidence."""

    return ExtractedProgramDraft.model_validate(
        {
            "name": "Synthetic Award",
            "description": "Synthetic scholarship.",
            "categories": ["scholarships"],
            "coverage": {"national": True, "states": [], "institutions": []},
            "checklist": [],
            "eligibility_tree": {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": {"snapshot_id": snapshot_id, "excerpt": excerpt}, "exceptions_complete": True},
            "coverage_complete": True,
            "award_cycle": "2027",
            "application_deadline": "2027-03-01T17:00:00-05:00",
            "deadline_timezone": "America/New_York",
            "application_availability": "open",
            "assistance_amount": "$2,500",
            "selection_factors": [{"description": "Preference is given to volunteers.", "evidence": {"snapshot_id": snapshot_id, "excerpt": "Preference is given to volunteers."}}],
            "application_url": "https://example.edu/apply",
            "unresolved_conditions": [],
        }
    )


def advance_to_validation(db, *, draft_factory=proposal, target_program_id=None):
    """Run deterministic acquisition and extraction for a test proposal."""

    run = create_ingestion_run(
        db,
        IngestionSubmission(
            f"run-{db.query(IngestionRun).count()}",
            PastedSourceRequest("https://example.edu/aid", SOURCE),
            target_program_id,
        ),
    )
    process_acquisition_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
    provider = DeterministicExtractionStub({run.source_snapshot_id: draft_factory(run.source_snapshot_id)})
    process_extraction_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), provider, clock=lambda: NOW)
    return run


def test_validated_output_creates_an_unpublished_reviewable_revision(sessions):
    """Success links source and draft without granting publishing authority."""

    with sessions() as db:
        run = advance_to_validation(db)
        process_validation_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
        db.refresh(run)
        revision = db.get(ProgramRevision, run.draft_revision_id)
        assert run.state == "awaiting_review"
        assert revision.status == "draft"
        assert revision.coverage_complete is False
        assert revision.sources[0].id == run.source_snapshot_id
        assert revision.selection_factors[0]["description"].startswith("Preference")
        assert revision.program.current_published_revision_id is None


def test_invented_evidence_fails_without_creating_a_draft(sessions):
    """A schema-valid hallucinated excerpt cannot enter admin review."""

    with sessions() as db:
        run = advance_to_validation(db, draft_factory=lambda snapshot_id: proposal(snapshot_id, excerpt="Applicants must have a 3.5 GPA."))
        process_validation_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
        db.refresh(run)
        assert run.state == "failed"
        assert run.error_code == "invalid_draft"
        assert run.draft_revision_id is None
        assert run.validation_findings[0]["code"] == "excerpt_not_found"


def test_update_run_uses_existing_program_without_changing_public_pointer(sessions):
    """A replacement draft leaves the currently published revision untouched."""

    with sessions() as db:
        program = Program(slug="existing")
        published = ProgramRevision(
            program=program,
            status="published",
            name="Existing Award",
            description="Existing reviewed revision.",
            categories=["scholarships"],
            coverage={"national": True, "states": [], "institutions": []},
            checklist=[],
            eligibility_tree={"type": "unsupported", "description": "Provider review", "evidence": {"snapshot_id": "old", "excerpt": "old"}},
            coverage_complete=False,
            application_availability="unknown",
            selection_factors=[],
            unresolved_conditions=[],
            provider_url="https://example.edu/old",
        )
        db.add(program)
        db.flush()
        db.flush()
        program.current_published_revision_id = published.id
        db.commit()
        original_id = published.id

        run = advance_to_validation(db, target_program_id=program.id)
        process_validation_stage(db, claim_next_run(db, "worker", clock=lambda: NOW), clock=lambda: NOW)
        db.refresh(program)
        assert program.current_published_revision_id == original_id
        assert db.get(ProgramRevision, run.draft_revision_id).program_id == program.id
        assert len(db.scalars(select(ProgramRevision).where(ProgramRevision.program_id == program.id)).all()) == 2
