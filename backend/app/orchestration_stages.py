"""Resumable acquisition and extraction stages for a leased ingestion run."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .extraction import ExtractionError, ExtractionProvider
from .models import IngestionRun, IngestionStageAttempt, SourceSnapshot
from .orchestration import (
    Clock,
    OrchestrationConfig,
    RunLease,
    release_lease,
    require_lease,
    retry_delay,
    utc_now,
)
from .source_acquisition import (
    AcquisitionConfig,
    AcquisitionError,
    PastedSourceRequest,
    Resolver,
    SingleHopTransport,
    WebSourceRequest,
)
from .source_service import acquire_source, persist_acquired_source


def process_acquisition_stage(
    db: Session,
    lease: RunLease,
    orchestration_config: OrchestrationConfig = OrchestrationConfig(),
    acquisition_config: AcquisitionConfig = AcquisitionConfig(),
    *,
    clock: Clock = utc_now,
    resolver: Resolver | None = None,
    transport: SingleHopTransport | None = None,
) -> None:
    """Acquire a source, then atomically save its snapshot and next state."""

    run = require_lease(db, lease, clock=clock)
    if run.state != "acquiring":
        raise ValueError("The leased run is not in the acquiring stage")
    attempt = _start_attempt(db, run, "acquiring", orchestration_config, clock)
    if attempt is None:
        return
    request = (
        PastedSourceRequest(run.source_url, run.input_source_text or "")
        if run.source_method == "pasted_text"
        else WebSourceRequest(run.source_url)
    )
    try:
        acquired = acquire_source(
            request,
            acquisition_config,
            resolver=resolver,
            transport=transport,
        )
    except AcquisitionError as error:
        _finish_failure(db, run, attempt, error.code, error.safe_message, error.retryable, orchestration_config, clock)
        return
    except Exception:
        _finish_failure(db, run, attempt, "acquisition_error", "Source acquisition failed unexpectedly.", False, orchestration_config, clock)
        return

    # Recheck the fencing token after network work. An expired worker cannot
    # persist an orphaned result over a replacement worker's progress.
    run = require_lease(db, lease, clock=clock)
    snapshot = persist_acquired_source(db, acquired, commit=False)
    run.source_snapshot_id = snapshot.id
    run.state = "extracting"
    _finish_success(db, run, attempt, clock)


def process_extraction_stage(
    db: Session,
    lease: RunLease,
    provider: ExtractionProvider,
    config: OrchestrationConfig = OrchestrationConfig(),
    *,
    clock: Clock = utc_now,
) -> None:
    """Extract a structured proposal and persist reproducibility metadata."""

    run = require_lease(db, lease, clock=clock)
    if run.state != "extracting":
        raise ValueError("The leased run is not in the extracting stage")
    snapshot = db.get(SourceSnapshot, run.source_snapshot_id)
    if snapshot is None:
        _fail_without_attempt(db, run, "missing_snapshot", "The acquired source snapshot is unavailable.", clock)
        return
    attempt = _start_attempt(db, run, "extracting", config, clock)
    if attempt is None:
        return
    try:
        result = provider.extract(snapshot)
    except ExtractionError as error:
        _finish_failure(db, run, attempt, error.code, error.safe_message, error.retryable, config, clock)
        return
    except Exception:
        _finish_failure(db, run, attempt, "extraction_error", "Requirement extraction failed unexpectedly.", False, config, clock)
        return

    run = require_lease(db, lease, clock=clock)
    run.extracted_draft = result.draft.model_dump(mode="json")
    run.model = result.model
    run.prompt_version = result.prompt_version
    run.schema_version = result.schema_version
    run.provider_request_id = result.request_id
    run.input_tokens = result.usage.input_tokens
    run.output_tokens = result.usage.output_tokens
    run.total_tokens = result.usage.total_tokens
    run.state = "validating"
    _finish_success(db, run, attempt, clock)


def _start_attempt(
    db: Session,
    run: IngestionRun,
    stage: str,
    config: OrchestrationConfig,
    clock: Clock,
) -> IngestionStageAttempt | None:
    """Close interrupted history and append one bounded running attempt."""

    current = clock()
    running = list(
        db.scalars(
            select(IngestionStageAttempt).where(
                IngestionStageAttempt.run_id == run.id,
                IngestionStageAttempt.stage == stage,
                IngestionStageAttempt.outcome == "running",
            )
        )
    )
    for previous in running:
        previous.outcome = "failed"
        previous.error_code = "worker_interrupted"
        previous.error_message = "The worker lease expired before the stage completed."
        previous.completed_at = current
        previous.latency_ms = _elapsed_ms(previous.started_at, current)
    completed = db.scalar(
        select(func.count()).select_from(IngestionStageAttempt).where(
            IngestionStageAttempt.run_id == run.id,
            IngestionStageAttempt.stage == stage,
        )
    )
    if completed >= config.maximum_stage_attempts:
        _fail_without_attempt(db, run, "attempts_exhausted", "The stage exhausted its automatic attempts.", clock)
        return None
    attempt = IngestionStageAttempt(
        run_id=run.id,
        stage=stage,
        attempt_number=completed + 1,
        outcome="running",
        started_at=current,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def _finish_success(db: Session, run: IngestionRun, attempt: IngestionStageAttempt, clock: Clock) -> None:
    """Commit a successful stage transition and its history atomically."""

    current = clock()
    attempt.outcome = "succeeded"
    attempt.completed_at = current
    attempt.latency_ms = _elapsed_ms(attempt.started_at, current)
    _clear_error(run)
    release_lease(run)
    run.updated_at = current
    db.commit()


def _finish_failure(
    db: Session,
    run: IngestionRun,
    attempt: IngestionStageAttempt,
    code: str,
    message: str,
    retryable: bool,
    config: OrchestrationConfig,
    clock: Clock,
) -> None:
    """Schedule bounded retry or terminate without retaining raw exceptions."""

    current = clock()
    attempt.completed_at = current
    attempt.latency_ms = _elapsed_ms(attempt.started_at, current)
    attempt.error_code = code
    attempt.error_message = message
    run.error_code = code
    run.error_message = message
    run.error_retryable = retryable
    if retryable and attempt.attempt_number < config.maximum_stage_attempts:
        attempt.outcome = "retry_scheduled"
        run.next_attempt_at = current + retry_delay(config, attempt.attempt_number)
    else:
        attempt.outcome = "failed"
        run.state = "failed"
        run.completed_at = current
    release_lease(run)
    run.updated_at = current
    db.commit()


def _fail_without_attempt(db: Session, run: IngestionRun, code: str, message: str, clock: Clock) -> None:
    """Terminate a run when its persisted stage prerequisites are broken."""

    current = clock()
    run.state = "failed"
    run.error_code = code
    run.error_message = message
    run.error_retryable = False
    run.completed_at = current
    run.updated_at = current
    release_lease(run)
    db.commit()


def _clear_error(run: IngestionRun) -> None:
    """Remove the prior transient error after a successful retry."""

    run.error_code = None
    run.error_message = None
    run.error_retryable = None
    run.next_attempt_at = None


def _elapsed_ms(started: datetime, completed: datetime) -> int:
    """Calculate nonnegative latency across SQLite and timezone-aware stores."""

    if started.tzinfo is None and completed.tzinfo is not None:
        started = started.replace(tzinfo=completed.tzinfo)
    return max(0, round((completed - started).total_seconds() * 1000))
