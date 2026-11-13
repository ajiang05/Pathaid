"""Durable daily discovery scheduling and resumable local worker stages."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Callable
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from .database import Database
from .extraction import ExtractionError, ExtractionProvider, ExtractionResult, TokenUsage, configured_extraction_provider
from .extraction_schemas import ExtractedProgramDraft
from .models import DiscoveryExtractionArtifact, DiscoveryJob, SourcePageState, SourceScope, SourceSnapshot
from .scholarship_activation import activate_validated_extraction
from .secrets import SecretStore
from .source_registry import RegistryError
from .source_scanning import execute_registered_scan


TRANSIENT_SCAN_ERRORS = {"timeout", "upstream_unavailable"}
PAGE_EXTRACTION_ERRORS = {"invalid_output", "model_refusal", "source_too_large"}


def _utc(value: datetime) -> datetime:
    """Normalize SQLite-naive and timezone-aware values for comparisons."""

    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _day_window(value: datetime) -> datetime:
    value = _utc(value)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def enqueue_due_sources(
    database: Database,
    *,
    now: datetime | None = None,
    max_attempts: int = 3,
) -> tuple[str, ...]:
    """Create at most one catch-up job per due source and trigger window."""

    moment = _utc(now or datetime.now(timezone.utc))
    queued: list[str] = []
    with database.sessions.begin() as db:
        scopes = db.scalars(
            select(SourceScope).where(
                SourceScope.status == "active",
                SourceScope.policy_status == "allowed",
                or_(
                    and_(SourceScope.next_scan_at.is_not(None), SourceScope.next_scan_at <= moment),
                    SourceScope.scan_requested_at.is_not(None),
                ),
            ).order_by(SourceScope.id)
        ).all()
        for scope in scopes:
            manual = scope.scan_requested_at is not None
            trigger = "manual" if manual else "scheduled"
            window = _utc(scope.scan_requested_at) if manual else _day_window(moment)
            active = db.scalar(select(DiscoveryJob.id).where(
                DiscoveryJob.source_scope_id == scope.id,
                DiscoveryJob.status.in_(("queued", "running", "retry_wait")),
            ).limit(1))
            if active is not None:
                # One source is processed serially. A repeated Scan now request
                # joins the existing work instead of creating a duplicate job.
                if manual:
                    scope.scan_requested_at = None
                continue
            existing = db.scalar(select(DiscoveryJob.id).where(
                DiscoveryJob.source_scope_id == scope.id,
                DiscoveryJob.trigger == trigger,
                DiscoveryJob.window_start == window,
            ))
            if existing is None:
                # A manual retry after Gemini/extraction failed should reuse
                # the successful acquisition. The immutable snapshots and
                # current-page state are already durable, so downloading the
                # same directory again would only waste time and bandwidth.
                resumable = None
                if manual:
                    resumable = db.scalar(
                        select(DiscoveryJob).where(
                            DiscoveryJob.source_scope_id == scope.id,
                            DiscoveryJob.status == "failed",
                            DiscoveryJob.scan_run_id.is_not(None),
                            DiscoveryJob.stage.in_(("extraction", "activation")),
                        ).order_by(DiscoveryJob.created_at.desc(), DiscoveryJob.id.desc()).limit(1)
                    )
                job_id = str(uuid4())
                db.add(DiscoveryJob(
                    id=job_id, source_scope_id=scope.id, trigger=trigger,
                    window_start=window, status="queued",
                    # Activation is deliberately replayed through extraction:
                    # successful artifacts are copied without another Gemini
                    # call, then all copied/new artifacts are activated.
                    stage="extraction" if resumable is not None else "acquisition",
                    attempt_count=0, max_attempts=max_attempts,
                    available_at=moment,
                    scan_run_id=resumable.scan_run_id if resumable is not None else None,
                ))
                queued.append(job_id)
            if manual:
                # The durable job now owns this request; clearing the flag keeps
                # repeated startup from creating a second manual job.
                scope.scan_requested_at = None
    return tuple(queued)


def claim_next_job(
    database: Database,
    worker_id: str,
    *,
    now: datetime | None = None,
    lease_seconds: int = 300,
) -> DiscoveryJob | None:
    """Atomically claim one ready job or reclaim one whose worker lease expired."""

    moment = _utc(now or datetime.now(timezone.utc))
    eligible = or_(
        and_(DiscoveryJob.status.in_(("queued", "retry_wait")), DiscoveryJob.available_at <= moment),
        and_(DiscoveryJob.status == "running", DiscoveryJob.lease_expires_at <= moment, DiscoveryJob.attempt_count < DiscoveryJob.max_attempts),
    )
    while True:
        with database.sessions.begin() as db:
            db.execute(
                update(DiscoveryJob).where(
                    DiscoveryJob.status == "running",
                    DiscoveryJob.lease_expires_at <= moment,
                    DiscoveryJob.attempt_count >= DiscoveryJob.max_attempts,
                ).values(
                    status="failed", last_error_code="worker_lease_expired",
                    lease_owner=None, lease_expires_at=None,
                )
            )
            job = db.scalar(select(DiscoveryJob).where(eligible).order_by(DiscoveryJob.available_at, DiscoveryJob.created_at, DiscoveryJob.id).limit(1))
            if job is None:
                return None
            scope = db.get(SourceScope, job.source_scope_id)
            if scope is None or scope.status != "active" or scope.policy_status != "allowed":
                job.status = "cancelled"
                job.lease_owner = None
                job.lease_expires_at = None
                job.last_error_code = "source_not_schedulable"
                continue
            claimed = db.execute(
                update(DiscoveryJob).where(DiscoveryJob.id == job.id, eligible).values(
                    status="running", attempt_count=DiscoveryJob.attempt_count + 1,
                    lease_owner=worker_id,
                    lease_expires_at=moment + timedelta(seconds=lease_seconds),
                ).execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                continue
            db.expire_all()
            return db.get(DiscoveryJob, job.id)


def renew_job_lease(
    database: Database,
    job_id: str,
    worker_id: str,
    *,
    now: datetime | None = None,
    lease_seconds: int = 300,
) -> bool:
    """Extend only the lease still owned by this running worker."""

    moment = _utc(now or datetime.now(timezone.utc))
    with database.sessions.begin() as db:
        renewed = db.execute(
            update(DiscoveryJob).where(
                DiscoveryJob.id == job_id,
                DiscoveryJob.status == "running",
                DiscoveryJob.lease_owner == worker_id,
            ).values(lease_expires_at=moment + timedelta(seconds=lease_seconds))
        )
        return renewed.rowcount == 1


def _heartbeat_job_lease(
    database: Database,
    job_id: str,
    worker_id: str,
    stop_event: threading.Event,
    *,
    interval_seconds: int = 60,
) -> None:
    """Keep a long network/extraction job owned while its worker is healthy."""

    while not stop_event.wait(interval_seconds):
        try:
            if not renew_job_lease(database, job_id, worker_id):
                return
        except Exception:
            # A transient heartbeat write failure must not kill the worker; the
            # existing lease still permits recovery if the process is unhealthy.
            continue


def _retry_or_fail(database: Database, job_id: str, worker_id: str, code: str, retryable: bool, moment: datetime) -> str:
    with database.sessions.begin() as db:
        job = db.get(DiscoveryJob, job_id)
        if job is None or job.lease_owner != worker_id:
            return "failed"
        can_retry = retryable and job.attempt_count < job.max_attempts
        job.status = "retry_wait" if can_retry else "failed"
        job.available_at = moment + timedelta(minutes=2 ** max(job.attempt_count - 1, 0))
        job.last_error_code = code
        job.lease_owner = None
        job.lease_expires_at = None
        return job.status


def _complete(database: Database, job_id: str, worker_id: str) -> None:
    with database.sessions.begin() as db:
        job = db.get(DiscoveryJob, job_id)
        if job is None or job.lease_owner != worker_id:
            return
        job.status = "succeeded"
        job.stage = "complete"
        job.last_error_code = None
        job.lease_owner = None
        job.lease_expires_at = None


def _provider_snapshot(snapshot: SourceSnapshot):
    return SimpleNamespace(id=snapshot.id, source_url=snapshot.canonical_url, source_text=snapshot.normalized_text)


def _result_from_artifact(artifact: DiscoveryExtractionArtifact) -> ExtractionResult:
    return ExtractionResult(
        draft=ExtractedProgramDraft.model_validate(artifact.draft),
        model=artifact.extraction_model,
        prompt_version=artifact.prompt_version,
        schema_version=artifact.schema_version,
        request_id=artifact.provider_request_id,
        usage=TokenUsage(artifact.input_tokens, artifact.output_tokens, artifact.total_tokens),
    )


def _skip_listing(scope: SourceScope, snapshot: SourceSnapshot) -> bool:
    """Platform roots enumerate programs; only their detail pages are extracted."""

    return scope.adapter in {"academicworks", "kaleidoscope"} and snapshot.depth == 0


def _snapshots_for_extraction(db, job: DiscoveryJob) -> list[SourceSnapshot]:
    """Return the newest retained snapshot for every currently visible page."""

    current_urls = set(db.scalars(
        select(SourcePageState.canonical_url).where(
            SourcePageState.source_scope_id == job.source_scope_id,
            SourcePageState.status == "current",
        )
    ).all())
    if not current_urls:
        # Compatibility for imported/fixture runs created before page-state
        # reconciliation existed.
        return list(db.scalars(
            select(SourceSnapshot)
            .where(SourceSnapshot.scan_run_id == job.scan_run_id)
            .order_by(SourceSnapshot.depth, SourceSnapshot.id)
        ).all())
    candidates = db.scalars(
        select(SourceSnapshot)
        .where(
            SourceSnapshot.source_scope_id == job.source_scope_id,
            SourceSnapshot.canonical_url.in_(current_urls),
        )
        .order_by(SourceSnapshot.acquired_at.desc(), SourceSnapshot.id.desc())
    ).all()
    newest: dict[str, SourceSnapshot] = {}
    for snapshot in candidates:
        newest.setdefault(snapshot.canonical_url, snapshot)
    return sorted(newest.values(), key=lambda item: (item.depth, item.canonical_url, item.id))


def _reusable_artifact(db, job_id: str, snapshot_id: str) -> DiscoveryExtractionArtifact | None:
    """Find a successful prior extraction for the exact immutable snapshot."""

    return db.scalar(
        select(DiscoveryExtractionArtifact).where(
            DiscoveryExtractionArtifact.discovery_job_id != job_id,
            DiscoveryExtractionArtifact.source_snapshot_id == snapshot_id,
            DiscoveryExtractionArtifact.status.in_(("extracted", "activated")),
            DiscoveryExtractionArtifact.draft.is_not(None),
        ).order_by(DiscoveryExtractionArtifact.created_at.desc(), DiscoveryExtractionArtifact.id.desc()).limit(1)
    )


def _run_claimed_job(
    database: Database,
    job_id: str,
    worker_id: str,
    *,
    provider_factory: Callable[[], ExtractionProvider],
    scanner: Callable[[Database, str], object] = execute_registered_scan,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> str:
    """Run committed acquisition, extraction, and activation stages in order."""

    with database.sessions() as db:
        job = db.get(DiscoveryJob, job_id)
        if job is None or job.status != "running" or job.lease_owner != worker_id:
            raise RegistryError("job_not_claimed", "The discovery job is not leased to this worker.")
        source_id, stage = job.source_scope_id, job.stage

    if stage == "acquisition":
        try:
            scan = scanner(database, source_id)
        except RegistryError as error:
            return _retry_or_fail(database, job_id, worker_id, error.code, False, _utc(now()))
        if scan.status != "succeeded":
            code = scan.error_code or "scan_failed"
            return _retry_or_fail(database, job_id, worker_id, code, code in TRANSIENT_SCAN_ERRORS, _utc(now()))
        with database.sessions.begin() as db:
            job = db.get(DiscoveryJob, job_id)
            job.scan_run_id = scan.id
            job.stage = "extraction"
            job.last_error_code = None

    with database.sessions() as db:
        job = db.get(DiscoveryJob, job_id)
        scope = db.get(SourceScope, job.source_scope_id)
        snapshots = _snapshots_for_extraction(db, job)
        artifacts = {item.source_snapshot_id: item for item in db.scalars(
            select(DiscoveryExtractionArtifact).where(DiscoveryExtractionArtifact.discovery_job_id == job_id)
        ).all()}

    if job.stage == "extraction":
        provider: ExtractionProvider | None = None
        for snapshot in snapshots:
            if snapshot.id in artifacts:
                continue
            if _skip_listing(scope, snapshot):
                with database.sessions.begin() as db:
                    db.add(DiscoveryExtractionArtifact(
                        id=str(uuid4()), discovery_job_id=job_id,
                        source_snapshot_id=snapshot.id, status="skipped",
                    ))
                continue
            with database.sessions.begin() as db:
                reusable = _reusable_artifact(db, job_id, snapshot.id)
                if reusable is not None:
                    db.add(DiscoveryExtractionArtifact(
                        id=str(uuid4()), discovery_job_id=job_id,
                        source_snapshot_id=snapshot.id, status=reusable.status,
                        draft=reusable.draft, extraction_model=reusable.extraction_model,
                        prompt_version=reusable.prompt_version, schema_version=reusable.schema_version,
                        provider_request_id=reusable.provider_request_id,
                        input_tokens=reusable.input_tokens, output_tokens=reusable.output_tokens,
                        total_tokens=reusable.total_tokens,
                    ))
                    continue
            try:
                provider = provider or provider_factory()
                result = provider.extract(_provider_snapshot(snapshot))
            except ExtractionError as error:
                if error.code in PAGE_EXTRACTION_ERRORS:
                    with database.sessions.begin() as db:
                        config = getattr(provider, "config", None)
                        db.add(DiscoveryExtractionArtifact(
                            id=str(uuid4()), discovery_job_id=job_id,
                            source_snapshot_id=snapshot.id, status="validation_failed",
                            extraction_model=getattr(config, "model", None),
                        ))
                    continue
                return _retry_or_fail(database, job_id, worker_id, error.code, error.retryable, _utc(now()))
            with database.sessions.begin() as db:
                db.add(DiscoveryExtractionArtifact(
                    id=str(uuid4()), discovery_job_id=job_id,
                    source_snapshot_id=snapshot.id, status="extracted",
                    draft=result.draft.model_dump(mode="json"),
                    extraction_model=result.model, prompt_version=result.prompt_version,
                    schema_version=result.schema_version,
                    provider_request_id=result.request_id,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    total_tokens=result.usage.total_tokens,
                ))
        with database.sessions.begin() as db:
            db.get(DiscoveryJob, job_id).stage = "activation"

    with database.sessions() as db:
        pending = db.scalars(
            select(DiscoveryExtractionArtifact).where(
                DiscoveryExtractionArtifact.discovery_job_id == job_id,
                DiscoveryExtractionArtifact.status == "extracted",
            ).order_by(DiscoveryExtractionArtifact.source_snapshot_id)
        ).all()
    for artifact in pending:
        activation = activate_validated_extraction(
            database, artifact.source_snapshot_id, _result_from_artifact(artifact), now=now,
        )
        with database.sessions.begin() as db:
            stored = db.get(DiscoveryExtractionArtifact, artifact.id)
            stored.status = "validation_failed" if activation.status == "validation_failed" else "activated"
    _complete(database, job_id, worker_id)
    return "succeeded"


def run_claimed_job(
    database: Database,
    job_id: str,
    worker_id: str,
    *,
    provider_factory: Callable[[], ExtractionProvider],
    scanner: Callable[[Database, str], object] = execute_registered_scan,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> str:
    """Run one claimed job while renewing its recoverable worker lease."""

    stop_event = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat_job_lease,
        args=(database, job_id, worker_id, stop_event),
        name=f"pathaid-job-heartbeat-{job_id}", daemon=True,
    )
    heartbeat.start()
    try:
        return _run_claimed_job(
            database, job_id, worker_id,
            provider_factory=provider_factory, scanner=scanner, now=now,
        )
    finally:
        stop_event.set()
        heartbeat.join(timeout=2)


def local_provider_factory(_store: SecretStore) -> Callable[[], ExtractionProvider]:
    """Build local-only Ollama scholarship extraction."""

    def build() -> ExtractionProvider:
        environment = dict(os.environ)
        environment["PATHAID_EXTRACTION_PROVIDER"] = "ollama"
        return configured_extraction_provider(environment)

    return build


def run_scheduler_cycle(
    database: Database,
    *,
    worker_id: str,
    provider_factory: Callable[[], ExtractionProvider],
    now: datetime | None = None,
    max_jobs: int = 25,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> int:
    """Enqueue due work and drain a bounded number of jobs."""

    moment = _utc(now or datetime.now(timezone.utc))
    enqueue_due_sources(database, now=moment)
    processed = 0
    host_last_finished: dict[str, float] = {}
    for _ in range(max_jobs):
        job = claim_next_job(database, worker_id, now=moment)
        if job is None:
            break
        with database.sessions() as db:
            scope = db.get(SourceScope, job.source_scope_id)
            hostname, requests_per_minute = scope.hostname, scope.requests_per_minute
        previous = host_last_finished.get(hostname)
        if previous is not None:
            remaining = (60.0 / requests_per_minute) - (monotonic() - previous)
            if remaining > 0:
                sleeper(remaining)
        run_claimed_job(database, job.id, worker_id, provider_factory=provider_factory)
        host_last_finished[hostname] = monotonic()
        processed += 1
    return processed


class SchedulerThread:
    """Small stoppable background loop used by the local FastAPI process."""

    def __init__(self, database: Database, store: SecretStore, *, interval_seconds: int = 60):
        self.database = database
        self.provider_factory = local_provider_factory(store)
        self.interval_seconds = interval_seconds
        self.worker_id = f"local-{uuid4()}"
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="pathaid-scheduler", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=5)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                run_scheduler_cycle(
                    self.database, worker_id=self.worker_id,
                    provider_factory=self.provider_factory,
                )
            except Exception:
                # The API must remain available if background work fails. Each
                # expected job failure is persisted; this guard covers only an
                # unexpected scheduler-level defect and retries next interval.
                pass
            self.stop_event.wait(self.interval_seconds)
