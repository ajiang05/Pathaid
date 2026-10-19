"""Protected draft inspection, editing, and revision-history APIs."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .admin_auth import current_admin, require_admin_csrf
from .database import get_db
from .extraction_schemas import ExtractedProgramDraft
from .extraction_validation import validate_extracted_draft
from .models import AdminSession, IngestionRun, Program, ProgramRevision, ReviewEvent, SourceSnapshot
from .source_acquisition import AcquisitionError, validate_source_url


router = APIRouter(prefix="/api/admin", tags=["admin-review"])


class RevisionUpdate(BaseModel):
    """Complete reviewed proposal replacing the editable draft fields."""

    model_config = ConfigDict(extra="forbid")
    draft: ExtractedProgramDraft
    provider_url: str = Field(min_length=1, max_length=2048)


class ApprovalRequest(BaseModel):
    """Explicit reviewer attestations required before publication."""

    model_config = ConfigDict(extra="forbid")
    source_accurate: bool
    coverage_complete: bool
    notes: str | None = Field(default=None, max_length=2000)


class RejectionRequest(BaseModel):
    """Optional explanation retained with a rejection decision."""

    model_config = ConfigDict(extra="forbid")
    notes: str | None = Field(default=None, max_length=2000)


class ReplacementDraftRequest(BaseModel):
    """Idempotency key for copying a published revision into review."""

    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)


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


@router.post("/programs/{program_id}/drafts", status_code=201)
def create_replacement_draft(
    program_id: str,
    body: ReplacementDraftRequest,
    _admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Copy the current immutable publication into a new editable revision."""

    existing_run = db.scalar(select(IngestionRun).where(IngestionRun.idempotency_key == body.idempotency_key))
    if existing_run is not None:
        if existing_run.target_program_id != program_id or existing_run.draft_revision_id is None:
            raise HTTPException(409, detail="The idempotency key was already used for different input")
        return revision_fields(db.get(ProgramRevision, existing_run.draft_revision_id))

    program = db.scalar(select(Program).where(Program.id == program_id).with_for_update())
    if program is None or program.current_published_revision_id is None:
        raise HTTPException(404, detail="Published program not found")
    published = db.scalar(
        select(ProgramRevision)
        .where(
            ProgramRevision.id == program.current_published_revision_id,
            ProgramRevision.program_id == program.id,
            ProgramRevision.status == "published",
        )
        .options(selectinload(ProgramRevision.sources))
    )
    if published is None or len(published.sources) != 1:
        raise HTTPException(409, detail="The published revision cannot be copied for review")

    source = published.sources[0]
    proposal = _proposal_from_revision(published)
    revision = ProgramRevision(
        program=program,
        status="draft",
        validation_status="valid",
        validation_findings=[],
        name=published.name,
        description=published.description,
        categories=copy.deepcopy(published.categories),
        coverage=copy.deepcopy(published.coverage),
        checklist=copy.deepcopy(published.checklist),
        eligibility_tree=copy.deepcopy(published.eligibility_tree),
        coverage_complete=False,
        award_cycle=published.award_cycle,
        application_deadline=published.application_deadline,
        deadline_timezone=published.deadline_timezone,
        application_availability=published.application_availability,
        assistance_amount=published.assistance_amount,
        selection_factors=copy.deepcopy(published.selection_factors),
        unresolved_conditions=copy.deepcopy(published.unresolved_conditions),
        provider_url=published.provider_url,
        application_url=published.application_url,
    )
    revision.sources.append(source)
    db.add(revision)
    db.flush()
    fingerprint = hashlib.sha256(f"replacement:{program.id}:{published.id}".encode()).hexdigest()
    run = IngestionRun(
        idempotency_key=body.idempotency_key,
        request_fingerprint=fingerprint,
        target_program_id=program.id,
        source_url=source.source_url,
        source_method=source.acquisition_method,
        state="awaiting_review",
        source_snapshot_id=source.id,
        draft_revision_id=revision.id,
        extracted_draft=proposal,
        validation_findings=[],
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="The replacement draft request conflicted with another submission") from None
    return revision_fields(revision)


@router.post("/revisions/{revision_id}/approve")
def approve_revision(
    revision_id: str,
    body: ApprovalRequest,
    admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Atomically publish one currently valid and explicitly attested draft."""

    if body.source_accurate is not True:
        raise HTTPException(422, detail={"field": "source_accurate", "message": "Source accuracy must be attested"})
    revision = db.scalar(
        select(ProgramRevision)
        .where(ProgramRevision.id == revision_id)
        .with_for_update()
        .options(selectinload(ProgramRevision.sources))
    )
    if revision is None:
        raise HTTPException(404, detail="Revision not found")
    if revision.status != "draft":
        raise HTTPException(409, detail="The revision already has a review decision")
    if revision.validation_status != "valid":
        raise HTTPException(409, detail="The draft must pass validation before approval")
    run = db.scalar(select(IngestionRun).where(IngestionRun.draft_revision_id == revision.id).with_for_update())
    if run is None or run.state != "awaiting_review" or len(revision.sources) != 1:
        raise HTTPException(409, detail="The draft is not ready for approval")

    payload = dict(run.extracted_draft or {})
    payload["coverage_complete"] = body.coverage_complete
    try:
        draft = ExtractedProgramDraft.model_validate(payload)
    except ValidationError:
        raise HTTPException(422, detail={"field": "coverage_complete", "message": "Completeness conflicts with unresolved requirements"}) from None
    if body.coverage_complete and (draft.unresolved_conditions or _contains_unsupported(draft.eligibility_tree)):
        raise HTTPException(422, detail={"field": "coverage_complete", "message": "Unresolved requirements prevent complete coverage"})
    validation = validate_extracted_draft(draft, revision.sources[0])
    if not validation.is_valid:
        revision.validation_status = "invalid"
        revision.validation_findings = [asdict(finding) for finding in validation.findings]
        db.commit()
        raise HTTPException(409, detail="The draft failed validation and cannot be published")

    program = db.scalar(select(Program).where(Program.id == revision.program_id).with_for_update())
    if program is None:
        raise HTTPException(409, detail="The draft program no longer exists")
    reviewed_at = datetime.now(timezone.utc)
    revision.coverage_complete = body.coverage_complete
    revision.status = "published"
    revision.verified_at = reviewed_at
    program.current_published_revision_id = revision.id
    run.state = "published"
    run.completed_at = reviewed_at
    db.add(ReviewEvent(revision=revision, reviewer=admin.admin_email, decision="approved", notes=_clean_notes(body.notes)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="The revision already has a review decision") from None
    return revision_fields(revision)


@router.post("/revisions/{revision_id}/reject")
def reject_revision(
    revision_id: str,
    body: RejectionRequest,
    admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Reject a draft atomically without changing the public program pointer."""

    revision = db.scalar(select(ProgramRevision).where(ProgramRevision.id == revision_id).with_for_update())
    if revision is None:
        raise HTTPException(404, detail="Revision not found")
    if revision.status != "draft":
        raise HTTPException(409, detail="The revision already has a review decision")
    run = db.scalar(select(IngestionRun).where(IngestionRun.draft_revision_id == revision.id).with_for_update())
    if run is None or run.state != "awaiting_review":
        raise HTTPException(409, detail="The draft is not awaiting review")
    reviewed_at = datetime.now(timezone.utc)
    revision.status = "rejected"
    run.state = "rejected"
    run.completed_at = reviewed_at
    db.add(ReviewEvent(revision=revision, reviewer=admin.admin_email, decision="rejected", notes=_clean_notes(body.notes)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="The revision already has a review decision") from None
    return revision_fields(revision)


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


def _contains_unsupported(rule) -> bool:
    """Find mandatory requirements that still need provider interpretation."""

    if getattr(rule, "type", None) == "unsupported":
        return True
    return any(_contains_unsupported(child) for child in getattr(rule, "children", []))


def _clean_notes(notes: str | None) -> str | None:
    """Normalize optional review notes without inventing content."""

    cleaned = notes.strip() if notes else ""
    return cleaned or None


def _proposal_from_revision(revision: ProgramRevision) -> dict:
    """Recreate the strict review proposal from immutable published fields."""

    deadline = revision.application_deadline.isoformat() if revision.application_deadline else None
    return {
        "name": revision.name,
        "description": revision.description,
        "categories": copy.deepcopy(revision.categories),
        "coverage": copy.deepcopy(revision.coverage),
        "checklist": copy.deepcopy(revision.checklist),
        "eligibility_tree": copy.deepcopy(revision.eligibility_tree),
        "coverage_complete": revision.coverage_complete,
        "award_cycle": revision.award_cycle,
        "application_deadline": deadline,
        "deadline_timezone": revision.deadline_timezone,
        "application_availability": revision.application_availability,
        "assistance_amount": revision.assistance_amount,
        "selection_factors": copy.deepcopy(revision.selection_factors),
        "application_url": revision.application_url,
        "unresolved_conditions": copy.deepcopy(revision.unresolved_conditions),
    }
