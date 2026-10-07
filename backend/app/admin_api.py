"""Protected administrator APIs for ingestion inspection and review work."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .admin_auth import current_admin, require_admin_csrf
from .database import get_db
from .models import AdminSession, IngestionRun, SourceSnapshot
from .orchestration import (
    IngestionSubmission,
    OrchestrationError,
    create_ingestion_run,
    create_manual_retry,
)
from .source_acquisition import PastedSourceRequest, WebSourceRequest


router = APIRouter(prefix="/api/admin", tags=["admin"])


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


def _run_summary(run: IngestionRun) -> dict:
    """Serialize diagnostics without returning source or extracted content."""

    return {
        "id": run.id,
        "parent_run_id": run.parent_run_id,
        "target_program_id": run.target_program_id,
        "draft_revision_id": run.draft_revision_id,
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
        allowed = {"queued", "acquiring", "extracting", "validating", "awaiting_review", "published", "rejected", "failed"}
        if state not in allowed:
            raise HTTPException(422, detail={"field": "state", "message": "Invalid state"})
        query = query.where(IngestionRun.state == state)
    return [_run_summary(run) for run in db.scalars(query)]


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
