"""Protected administrator APIs for ingestion inspection and review work."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .admin_auth import current_admin, require_admin_csrf
from .database import get_db
from .models import (
    AdminSession,
    DiscoveredCandidate,
    IngestionRun,
    Program,
    ProgramRevision,
    RecommendationAttempt,
    ScheduledScan,
    ScheduledSource,
    SourceSnapshot,
)
from .orchestration import (
    IngestionSubmission,
    OrchestrationError,
    create_ingestion_run,
    create_manual_retry,
)
from .source_acquisition import AcquisitionError, PastedSourceRequest, WebSourceRequest
from .scheduled_discovery import normalize_source_policy


router = APIRouter(prefix="/api/admin", tags=["admin"])


class ScheduledSourceCreate(BaseModel):
    """Configuration for one administrator-approved recurring source."""

    model_config = ConfigDict(extra="forbid")
    canonical_url: str = Field(min_length=1, max_length=2048)
    source_type: Literal["program_page", "discovery_page"]
    target_program_id: str | None = None
    cadence_hours: int = Field(default=24, ge=1, le=24 * 30)
    allowed_path_prefix: str | None = Field(default=None, max_length=2048)
    discovery_link_limit: int = Field(default=20, ge=0, le=100)
    respect_robots: bool = True
    next_scan_at: datetime | None = None

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ScheduledSourceCreate":
        if self.source_type == "discovery_page" and self.target_program_id is not None:
            raise ValueError("discovery pages cannot target one existing program")
        return self


class ScheduledSourcePatch(BaseModel):
    """Mutable scheduling controls; URL and source type remain stable."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    cadence_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    allowed_path_prefix: str | None = Field(default=None, max_length=2048)
    discovery_link_limit: int | None = Field(default=None, ge=0, le=100)
    respect_robots: bool | None = None
    next_scan_at: datetime | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "ScheduledSourcePatch":
        """Keep required database fields from being cleared by PATCH nulls."""

        nullable_reset = {"allowed_path_prefix"}
        invalid = (self.model_fields_set - nullable_reset) & {
            name for name, value in self.__dict__.items() if value is None
        }
        if invalid:
            raise ValueError(f"{sorted(invalid)[0]} cannot be null")
        return self


def _source_response(source: ScheduledSource) -> dict:
    return {
        "id": source.id,
        "canonical_url": source.canonical_url,
        "source_type": source.source_type,
        "target_program_id": source.target_program_id,
        "enabled": source.enabled,
        "cadence_hours": source.cadence_hours,
        "allowed_hostname": source.allowed_hostname,
        "allowed_path_prefix": source.allowed_path_prefix,
        "discovery_link_limit": source.discovery_link_limit,
        "respect_robots": source.respect_robots,
        "next_scan_at": source.next_scan_at,
        "last_attempt_at": source.last_attempt_at,
        "last_success_at": source.last_success_at,
        "last_content_hash": source.last_content_hash,
        "last_error_code": source.last_error_code,
        "consecutive_failures": source.consecutive_failures,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


@router.post("/scheduled-sources", status_code=201)
def create_scheduled_source(
    body: ScheduledSourceCreate,
    admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Register one reviewed source and its exact discovery boundary."""

    try:
        url, hostname, path = normalize_source_policy(body.canonical_url, body.allowed_path_prefix)
    except (ValueError, AcquisitionError) as error:
        # Source validation errors contain only stable messages, never bodies.
        message = getattr(error, "safe_message", str(error))
        raise HTTPException(422, detail=message) from None
    if body.target_program_id and db.get(Program, body.target_program_id) is None:
        raise HTTPException(404, detail="The target program does not exist.")
    if db.scalar(select(ScheduledSource).where(ScheduledSource.canonical_url == url)) is not None:
        raise HTTPException(409, detail="This source is already registered.")
    next_scan = body.next_scan_at or datetime.now(timezone.utc)
    if next_scan.tzinfo is None:
        next_scan = next_scan.replace(tzinfo=timezone.utc)
    source = ScheduledSource(
        canonical_url=url,
        source_type=body.source_type,
        target_program_id=body.target_program_id,
        cadence_hours=body.cadence_hours,
        allowed_hostname=hostname,
        allowed_path_prefix=path,
        discovery_link_limit=body.discovery_link_limit if body.source_type == "discovery_page" else 0,
        respect_robots=body.respect_robots,
        next_scan_at=next_scan,
        created_by=admin.admin_email,
    )
    db.add(source)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="This source is already registered.") from None
    db.refresh(source)
    return _source_response(source)


@router.get("/scheduled-sources")
def list_scheduled_sources(
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """List source configuration and privacy-safe freshness state."""

    return [_source_response(item) for item in db.scalars(select(ScheduledSource).order_by(ScheduledSource.created_at.desc()))]


@router.patch("/scheduled-sources/{source_id}")
def update_scheduled_source(
    source_id: str,
    body: ScheduledSourcePatch,
    _admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Update scheduling controls without silently changing source identity."""

    source = db.get(ScheduledSource, source_id)
    if source is None:
        raise HTTPException(404, detail="Scheduled source not found")
    values = body.model_dump(exclude_unset=True)
    if "allowed_path_prefix" in values:
        _, _, values["allowed_path_prefix"] = normalize_source_policy(source.canonical_url, values["allowed_path_prefix"])
    if source.source_type == "program_page":
        values["discovery_link_limit"] = 0
    for key, value in values.items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return _source_response(source)


@router.post("/scheduled-sources/{source_id}/scan", status_code=202)
def request_source_scan(
    source_id: str,
    _admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Make a source due now; the scheduler retains enqueue authority."""

    source = db.get(ScheduledSource, source_id)
    if source is None:
        raise HTTPException(404, detail="Scheduled source not found")
    pending = db.scalar(
        select(ScheduledScan).where(
            ScheduledScan.source_id == source.id,
            ScheduledScan.outcome.in_(("queued", "running")),
        )
    )
    if pending is not None:
        return {"id": source.id, "status": "already_pending", "next_scan_at": source.next_scan_at}
    now = datetime.now(timezone.utc)
    source.enabled = True
    # Preserve an already-due window so repeated requests have the same
    # source/window idempotency key until the scheduler claims it.
    scheduled = source.next_scan_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled > now:
        source.next_scan_at = now
    db.commit()
    return {"id": source.id, "status": "due", "next_scan_at": source.next_scan_at}


@router.get("/scheduled-scans")
def list_scheduled_scans(
    limit: int = Query(default=50, ge=1, le=100),
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Return scan outcomes and private candidates without source bodies."""

    scans = list(db.scalars(select(ScheduledScan).order_by(ScheduledScan.created_at.desc()).limit(limit)))
    return [{
        "id": scan.id, "source_id": scan.source_id, "window_start": scan.window_start,
        "outcome": scan.outcome, "content_changed": scan.content_changed,
        "content_hash": scan.content_hash, "candidate_count": scan.candidate_count,
        "error_code": scan.error_code, "created_at": scan.created_at, "completed_at": scan.completed_at,
    } for scan in scans]


@router.get("/discovered-candidates")
def list_discovered_candidates(
    limit: int = Query(default=50, ge=1, le=100),
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """List private links found inside approved discovery boundaries."""

    items = db.scalars(select(DiscoveredCandidate).order_by(DiscoveredCandidate.created_at.desc()).limit(limit))
    return [{"id": item.id, "source_id": item.source_id, "first_scan_id": item.first_scan_id,
             "canonical_url": item.canonical_url, "status": item.status, "created_at": item.created_at} for item in items]


@router.get("/operations/summary")
def operations_summary(
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Return aggregate service signals without student or retained source values."""

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    current = datetime.now(timezone.utc)
    recommendation_total = db.scalar(
        select(func.count()).select_from(RecommendationAttempt).where(RecommendationAttempt.created_at >= cutoff)
    )
    recommendation_failures = db.scalar(
        select(func.count()).select_from(RecommendationAttempt).where(
            RecommendationAttempt.created_at >= cutoff,
            RecommendationAttempt.outcome != "success",
        )
    )
    recommendation_latency = db.scalar(
        select(func.avg(RecommendationAttempt.latency_ms)).where(
            RecommendationAttempt.created_at >= cutoff,
            RecommendationAttempt.latency_ms.is_not(None),
        )
    )
    oldest_verification = db.scalar(
        select(func.min(ProgramRevision.verified_at)).where(ProgramRevision.status == "published")
    )
    if oldest_verification is not None and oldest_verification.tzinfo is None:
        oldest_verification = oldest_verification.replace(tzinfo=timezone.utc)
    verification_age_days = (
        (datetime.now(timezone.utc) - oldest_verification).days if oldest_verification is not None else None
    )
    return {
        "window_hours": 24,
        "failed_ingestion_runs": db.scalar(
            select(func.count()).select_from(IngestionRun).where(IngestionRun.state == "failed")
        ),
        "recommendation_attempts": recommendation_total,
        "recommendation_failures": recommendation_failures,
        "recommendation_average_latency_ms": round(float(recommendation_latency)) if recommendation_latency is not None else None,
        "oldest_source_verification": oldest_verification,
        "oldest_source_verification_age_days": verification_age_days,
        "scheduled_scans": db.scalar(
            select(func.count()).select_from(ScheduledScan).where(ScheduledScan.created_at >= cutoff)
        ),
        "scheduled_scan_failures": db.scalar(
            select(func.count()).select_from(ScheduledScan).where(
                ScheduledScan.created_at >= cutoff, ScheduledScan.outcome == "failed"
            )
        ),
        "overdue_sources": db.scalar(
            select(func.count()).select_from(ScheduledSource).where(
                ScheduledSource.enabled.is_(True), ScheduledSource.next_scan_at < current
            )
        ),
        "discovered_candidates": db.scalar(select(func.count()).select_from(DiscoveredCandidate)),
        "scheduled_review_backlog": db.scalar(
            select(func.count()).select_from(IngestionRun).where(
                IngestionRun.scheduled_source_id.is_not(None), IngestionRun.state == "awaiting_review"
            )
        ),
    }


class IngestionRunCreate(BaseModel):
    """Administrator input for one webpage or pasted-text workflow."""

    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2048)
    source_method: Literal["webpage", "pasted_text"]
    source_text: str | None = Field(default=None, max_length=500_000)
    target_program_id: str | None = None

    @model_validator(mode="after")
    def require_matching_source_text(self) -> "IngestionRunCreate":
        """Pasted runs require text while webpage runs cannot smuggle a body."""

        if self.source_method == "pasted_text" and not (self.source_text and self.source_text.strip()):
            raise ValueError("pasted_text requires source_text")
        if self.source_method == "webpage" and self.source_text is not None:
            raise ValueError("webpage cannot include source_text")
        return self


class ManualRetryRequest(BaseModel):
    """A new idempotency key preserves the retry as a linked run."""

    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)


def _run_summary(run: IngestionRun, *, superseded_by_revision_id: str | None = None) -> dict:
    """Serialize diagnostics without returning source or extracted content."""

    return {
        "id": run.id,
        "parent_run_id": run.parent_run_id,
        "target_program_id": run.target_program_id,
        "scheduled_source_id": run.scheduled_source_id,
        "scheduled_scan_id": run.scheduled_scan_id,
        "discovered_candidate_id": run.discovered_candidate_id,
        "draft_revision_id": run.draft_revision_id,
        # A newer pending draft for the same stable program is safer to review.
        # Keep the older workflow visible as history without asking the UI to
        # infer ordering from timestamps.
        "superseded_by_revision_id": superseded_by_revision_id,
        "source_url": run.source_url,
        "source_method": run.source_method,
        "state": run.state,
        "next_attempt_at": run.next_attempt_at,
        "model": run.model,
        "prompt_version": run.prompt_version,
        "schema_version": run.schema_version,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "total_tokens": run.total_tokens,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "error_retryable": run.error_retryable,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "completed_at": run.completed_at,
    }


def _run_detail(db: Session, run: IngestionRun) -> dict:
    """Add retained review content and append-only stage history."""

    snapshot = db.get(SourceSnapshot, run.source_snapshot_id) if run.source_snapshot_id else None
    return {
        **_run_summary(run),
        "source_snapshot": (
            {
                "id": snapshot.id,
                "source_url": snapshot.source_url,
                "final_url": snapshot.final_url,
                "acquisition_method": snapshot.acquisition_method,
                "media_type": snapshot.media_type,
                "acquired_at": snapshot.acquired_at,
                "content_hash": snapshot.content_hash,
                "source_text": snapshot.source_text,
            }
            if snapshot
            else None
        ),
        "extracted_draft": run.extracted_draft,
        "validation_findings": run.validation_findings,
        "provider_request_id": run.provider_request_id,
        "stage_attempts": [
            {
                "id": attempt.id,
                "stage": attempt.stage,
                "attempt_number": attempt.attempt_number,
                "outcome": attempt.outcome,
                "error_code": attempt.error_code,
                "error_message": attempt.error_message,
                "started_at": attempt.started_at,
                "completed_at": attempt.completed_at,
                "latency_ms": attempt.latency_ms,
            }
            for attempt in run.stage_attempts
        ],
    }


@router.post("/ingestion-runs", status_code=201)
def submit_ingestion_run(
    body: IngestionRunCreate,
    _admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Queue an idempotent ingestion run for the separate worker process."""

    source = (
        PastedSourceRequest(body.source_url, body.source_text or "")
        if body.source_method == "pasted_text"
        else WebSourceRequest(body.source_url)
    )
    try:
        run = create_ingestion_run(
            db,
            IngestionSubmission(body.idempotency_key, source, body.target_program_id),
        )
    except OrchestrationError as error:
        status = 409 if error.code == "idempotency_conflict" else 404 if error.code == "program_not_found" else 422
        raise HTTPException(status, detail=error.safe_message) from None
    return _run_summary(run)


@router.get("/ingestion-runs")
def list_ingestion_runs(
    state: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Return recent run summaries, optionally filtered by lifecycle state."""

    query = select(IngestionRun).order_by(IngestionRun.created_at.desc(), IngestionRun.id.desc()).limit(limit)
    if state is not None:
        allowed = {"queued", "acquiring", "extracting", "validating", "awaiting_review", "unchanged", "discovered", "published", "rejected", "failed"}
        if state not in allowed:
            raise HTTPException(422, detail={"field": "state", "message": "Invalid state"})
        query = query.where(IngestionRun.state == state)
    runs = list(db.scalars(query))
    latest_pending_by_program: dict[str, str] = {}
    pending = db.execute(
        select(
            IngestionRun.target_program_id,
            IngestionRun.draft_revision_id,
        )
        .where(
            IngestionRun.state == "awaiting_review",
            IngestionRun.target_program_id.is_not(None),
            IngestionRun.draft_revision_id.is_not(None),
        )
        .order_by(
            IngestionRun.target_program_id,
            IngestionRun.created_at.desc(),
            IngestionRun.id.desc(),
        )
    )
    for program_id, revision_id in pending:
        # Rows are newest-first within each program, so the first one is the
        # only draft that should appear in the default current-review queue.
        latest_pending_by_program.setdefault(program_id, revision_id)

    current_publications = {
        program_id: (revision_id, verified_at)
        for program_id, revision_id, verified_at in db.execute(
            select(
                Program.id,
                Program.current_published_revision_id,
                ProgramRevision.verified_at,
            )
            .join(
                ProgramRevision,
                ProgramRevision.id == Program.current_published_revision_id,
            )
            .where(
                Program.current_published_revision_id.is_not(None),
                ProgramRevision.verified_at.is_not(None),
            )
        )
    }

    def superseding_revision(run: IngestionRun) -> str | None:
        """Return the newer pending or already-published revision, if any."""

        if run.state != "awaiting_review" or run.target_program_id is None:
            return None
        publication = current_publications.get(run.target_program_id)
        if publication and _as_utc(run.created_at) <= _as_utc(publication[1]):
            # A completed human publication decision supersedes proposals that
            # were already waiting when that decision occurred. A later draft
            # remains visible as a legitimate update proposal.
            return publication[0]
        latest_pending = latest_pending_by_program.get(run.target_program_id)
        return latest_pending if latest_pending != run.draft_revision_id else None

    return [
        _run_summary(
            run,
            superseded_by_revision_id=superseding_revision(run),
        )
        for run in runs
    ]


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite-naive and PostgreSQL-aware timestamps for ordering."""

    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.get("/ingestion-runs/{run_id}")
def get_ingestion_run(
    run_id: str,
    _admin: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Return source, extraction, validation, and attempt data for review."""

    run = db.scalar(
        select(IngestionRun)
        .where(IngestionRun.id == run_id)
        .options(selectinload(IngestionRun.stage_attempts))
    )
    if run is None:
        raise HTTPException(404, detail="Ingestion run not found")
    return _run_detail(db, run)


@router.post("/ingestion-runs/{run_id}/retry", status_code=201)
def retry_ingestion_run(
    run_id: str,
    body: ManualRetryRequest,
    _admin: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Create a linked manual retry while preserving the failed run."""

    try:
        retry = create_manual_retry(db, run_id, body.idempotency_key)
    except OrchestrationError as error:
        status = 404 if error.code == "run_not_found" else 409
        raise HTTPException(status, detail=error.safe_message) from None
    return _run_summary(retry)
