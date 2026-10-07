"""Protected draft inspection, editing, and revision-history APIs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .admin_auth import current_admin, require_admin_csrf
from .database import get_db
from .extraction_schemas import ExtractedProgramDraft
from .extraction_validation import validate_extracted_draft
from .models import AdminSession, IngestionRun, Program, ProgramRevision, SourceSnapshot
from .source_acquisition import AcquisitionError, validate_source_url


router = APIRouter(prefix="/api/admin", tags=["admin-review"])


class RevisionUpdate(BaseModel):
    """Complete reviewed proposal replacing the editable draft fields."""

    model_config = ConfigDict(extra="forbid")
    draft: ExtractedProgramDraft
    provider_url: str = Field(min_length=1, max_length=2048)


def revision_fields(revision: ProgramRevision) -> dict:
    """Serialize catalog fields without implying they are already approved."""

    return {
        "id": revision.id,
        "program_id": revision.program_id,
        "status": revision.status,
        "validation_status": revision.validation_status,
        "validation_findings": revision.validation_findings,
        "name": revision.name,
        "description": revision.description,
        "categories": revision.categories,
        "coverage": revision.coverage,
        "checklist": revision.checklist,
        "eligibility_tree": revision.eligibility_tree,
        "coverage_complete": revision.coverage_complete,
        "award_cycle": revision.award_cycle,
        "application_deadline": revision.application_deadline,
        "deadline_timezone": revision.deadline_timezone,
        "application_availability": revision.application_availability,
        "assistance_amount": revision.assistance_amount,
        "selection_factors": revision.selection_factors,
        "unresolved_conditions": revision.unresolved_conditions,
        "provider_url": revision.provider_url,
        "application_url": revision.application_url,
        "verified_at": revision.verified_at,
        "created_at": revision.created_at,
    }


def get_review_run(db: Session, revision_id: str) -> IngestionRun | None:
    """Find the workflow whose validated output created this revision."""

    return db.scalar(
        select(IngestionRun)
        .where(IngestionRun.draft_revision_id == revision_id)
        .order_by(IngestionRun.created_at.desc())
    )


@router.get("/revisions/{revision_id}")
def get_admin_revision(
    revision_id: str,
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Return draft fields beside retained sources and workflow findings."""

    revision = db.scalar(
        select(ProgramRevision)
        .where(ProgramRevision.id == revision_id)
        .options(selectinload(ProgramRevision.sources), selectinload(ProgramRevision.review_events))
    )
    if revision is None:
        raise HTTPException(404, detail="Revision not found")
    run = get_review_run(db, revision.id)
    return {
        "revision": revision_fields(revision),
        "proposed_draft": run.extracted_draft if run else None,
        "ingestion_run_id": run.id if run else None,
        "sources": [
            {
                "id": source.id,
                "source_url": source.source_url,
                "final_url": source.final_url,
                "acquisition_method": source.acquisition_method,
                "acquired_at": source.acquired_at,
                "content_hash": source.content_hash,
                "source_text": source.source_text,
            }
            for source in revision.sources
        ],
        "review_events": [
            {
                "id": event.id,
                "reviewer": event.reviewer,
                "decision": event.decision,
                "notes": event.notes,
                "created_at": event.created_at,
            }
            for event in revision.review_events
        ],
    }


@router.patch("/revisions/{revision_id}")
def edit_admin_revision(
    revision_id: str,
    body: RevisionUpdate,
    _admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Replace editable draft fields and rerun deterministic validation."""

    revision = db.scalar(
        select(ProgramRevision)
        .where(ProgramRevision.id == revision_id)
        .options(selectinload(ProgramRevision.sources))
    )
    if revision is None:
        raise HTTPException(404, detail="Revision not found")
    if revision.status != "draft":
        raise HTTPException(409, detail="Only draft revisions can be edited")
    run = get_review_run(db, revision.id)
    if run is None or run.state != "awaiting_review":
        raise HTTPException(409, detail="The revision is not awaiting administrator review")
    if len(revision.sources) != 1:
        raise HTTPException(409, detail="The draft must have exactly one retained source")
    try:
        provider_url = validate_source_url(body.provider_url).url
        deadline = _deadline(body.draft.application_deadline, body.draft.deadline_timezone)
    except (AcquisitionError, ValueError, ZoneInfoNotFoundError):
        raise HTTPException(422, detail={"field": "draft", "message": "Invalid reviewed value"}) from None

    # Save the human's edits even when evidence validation fails, allowing the
    # next edit to correct highlighted findings. Structural Pydantic failures
    # are rejected before this endpoint runs.
    _apply_draft(revision, body.draft, provider_url, deadline)
    validation = validate_extracted_draft(body.draft, revision.sources[0])
    findings = [asdict(finding) for finding in validation.findings]
    revision.validation_status = "valid" if validation.is_valid else "invalid"
    revision.validation_findings = findings
    run.extracted_draft = body.draft.model_dump(mode="json")
    run.validation_findings = findings
    db.commit()
    return revision_fields(revision)


@router.get("/programs/{program_id}/revisions")
def list_program_revisions(
    program_id: str,
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Return protected revision history for one stable program identity."""

    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(404, detail="Program not found")
    revisions = list(
        db.scalars(
            select(ProgramRevision)
            .where(ProgramRevision.program_id == program_id)
            .order_by(ProgramRevision.created_at.desc(), ProgramRevision.id.desc())
        )
    )
    return {
        "program_id": program.id,
        "slug": program.slug,
        "current_published_revision_id": program.current_published_revision_id,
        "revisions": [revision_fields(revision) for revision in revisions],
    }


def _apply_draft(
    revision: ProgramRevision,
    draft: ExtractedProgramDraft,
    provider_url: str,
    deadline: datetime | None,
) -> None:
    """Copy validated wire fields while reserving completeness for approval."""

    revision.name = draft.name
    revision.description = draft.description
    revision.categories = list(draft.categories)
    revision.coverage = draft.coverage.model_dump(mode="json")
    revision.checklist = [item.model_dump(mode="json") for item in draft.checklist]
    revision.eligibility_tree = draft.eligibility_tree.model_dump(mode="json")
    revision.coverage_complete = False
    revision.award_cycle = draft.award_cycle
    revision.application_deadline = deadline
    revision.deadline_timezone = draft.deadline_timezone
    revision.application_availability = draft.application_availability
    revision.assistance_amount = draft.assistance_amount
    revision.selection_factors = [item.model_dump(mode="json") for item in draft.selection_factors]
    revision.unresolved_conditions = [item.model_dump(mode="json") for item in draft.unresolved_conditions]
    revision.provider_url = provider_url
    revision.application_url = draft.application_url


def _deadline(value: str | None, timezone_name: str | None) -> datetime | None:
    """Parse reviewed ISO data and attach its stated named timezone if needed."""

    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None and timezone_name:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed
