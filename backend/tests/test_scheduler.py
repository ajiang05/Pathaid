"""Acceptance tests for durable daily scheduling and resumable worker stages."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import func, select

from app.config import Settings
from app.database import Database
from app.extraction import DeterministicExtractionStub, ExtractionError, OllamaExtractionAdapter
from app.extraction_schemas import ExtractedProgramDraft
from app.local_data import upgrade_database
from app.models import (
    AppSetting,
    DiscoveryExtractionArtifact,
    DiscoveryJob,
    Scholarship,
    SourcePageState,
    SourceScanRun,
    SourceScope,
    SourceSnapshot,
)
from app.scheduler import claim_next_job, enqueue_due_sources, local_provider_factory, renew_job_lease, run_claimed_job


NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
SOURCE = "Community Scholars Award. Applicants must have a 3.0 GPA. Submit a transcript."


def draft(snapshot_id="snapshot-1") -> ExtractedProgramDraft:
    return ExtractedProgramDraft.model_validate({
        "name": "Community Scholars Award",
        "description": "A scholarship for current college students.",
        "categories": ["scholarships"],
        "coverage": {"national": True, "states": [], "institutions": []},
        "checklist": [{
            "label": "Submit a transcript", "required": True,
            "evidence": {"snapshot_id": snapshot_id, "excerpt": "Submit a transcript."},
        }],
        "eligibility_tree": {
            "type": "condition", "field": "gpa", "operator": "gte", "value": 3.0,
            "evidence": {"snapshot_id": snapshot_id, "excerpt": "Applicants must have a 3.0 GPA."},
            "exceptions_complete": True,
        },
        "coverage_complete": True, "award_cycle": "2027",
        "application_deadline": "2027-03-01", "deadline_timezone": "America/New_York",
        "application_availability": "open", "assistance_amount": "$2,500",
        "selection_factors": [], "application_url": "https://sponsor.example/apply",
        "application_process": "separate_application", "application_process_evidence": None,
        "official_rules_url": None, "official_rules_evidence": None,
        "unresolved_conditions": [],
    })


def scheduler_database(tmp_path, **scope_changes) -> tuple[Database, Settings]:
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    values = {
        "id": "source-1", "name": "Sponsor", "ownership": "sponsor", "adapter": "generic",
        "canonical_url": "https://sponsor.example/scholarships", "hostname": "sponsor.example",
        "allowed_path_prefix": "/scholarships", "status": "active", "confirmed_at": NOW - timedelta(days=2),
        "max_depth": 1, "page_budget": 10, "requests_per_minute": 10,
        "scan_interval_hours": 24, "policy_status": "allowed", "next_scan_at": NOW - timedelta(days=1),
    }
    values.update(scope_changes)
    database = Database(settings)
    with database.sessions.begin() as db:
        db.add(SourceScope(**values))
    return database, settings


class CountingProvider(DeterministicExtractionStub):
    def __init__(self, outcomes):
        super().__init__(outcomes)
        self.calls = 0

    def extract(self, snapshot):
        self.calls += 1
        return super().extract(snapshot)


class FakeSecrets:
    def __init__(self, gemini_key=None):
        self.gemini_key = gemini_key

    def get(self, _name):
        return self.gemini_key


def test_scheduler_uses_local_ollama_even_when_a_gemini_key_exists():
    local = local_provider_factory(FakeSecrets())()
    with_key = local_provider_factory(FakeSecrets("test-gemini-key"))()
    assert isinstance(local, OllamaExtractionAdapter)
    assert isinstance(with_key, OllamaExtractionAdapter)


def successful_scanner(database: Database, source_id: str):
    """Persist acquisition exactly as a real adapter does, outside scheduler locks."""

    # Prove the scheduler is not holding a write transaction during this
    # external-stage stand-in by committing an unrelated writer first.
    with database.sessions.begin() as db:
        db.add(AppSetting(key="concurrent-writer", value="succeeded"))
    with database.sessions.begin() as db:
        run = SourceScanRun(
            id="run-1", source_scope_id=source_id, status="succeeded", started_at=NOW,
            finished_at=NOW, pages_attempted=1, snapshots_created=1,
            unchanged_pages=0, traversal_truncated=False,
        )
        db.add(run)
        db.flush()
        db.add(SourceSnapshot(
            id="snapshot-1", source_scope_id=source_id, scan_run_id=run.id,
            canonical_url="https://sponsor.example/scholarships/community",
            final_url="https://sponsor.example/scholarships/community", acquired_at=NOW,
            content_hash="a" * 64, media_type="text/html", normalized_text=SOURCE,
            source_byte_count=len(SOURCE), redirect_count=0, depth=1,
        ))
        scope = db.get(SourceScope, source_id)
        scope.last_success_at = NOW
        scope.next_scan_at = NOW + timedelta(hours=24)
        return run


def test_repeated_startup_enqueues_one_daily_catchup_and_excludes_unsafe_sources(tmp_path):
    database, _settings = scheduler_database(tmp_path)
    first = enqueue_due_sources(database, now=NOW)
    second = enqueue_due_sources(database, now=NOW)
    assert len(first) == 1 and second == ()
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(DiscoveryJob)) == 1
    database.close()

    for index, changes in enumerate(({"status": "paused"}, {"policy_status": "blocked"}, {"policy_status": "unknown"})):
        blocked, _settings = scheduler_database(tmp_path / str(index), **changes)
        assert enqueue_due_sources(blocked, now=NOW) == ()
        blocked.close()


def test_claim_is_exclusive_and_an_expired_lease_is_recovered(tmp_path):
    database, _settings = scheduler_database(tmp_path)
    enqueue_due_sources(database, now=NOW)
    first = claim_next_job(database, "worker-a", now=NOW, lease_seconds=30)
    assert first is not None and first.attempt_count == 1
    assert claim_next_job(database, "worker-b", now=NOW) is None
    recovered = claim_next_job(database, "worker-b", now=NOW + timedelta(seconds=31))
    assert recovered.id == first.id and recovered.lease_owner == "worker-b" and recovered.attempt_count == 2
    database.close()


def test_heartbeat_renews_owned_lease_and_attempt_limit_fails_closed(tmp_path):
    database, _settings = scheduler_database(tmp_path)
    job_id = enqueue_due_sources(database, now=NOW)[0]
    claim_next_job(database, "worker-a", now=NOW, lease_seconds=30)
    assert renew_job_lease(database, job_id, "worker-a", now=NOW + timedelta(seconds=20), lease_seconds=30)
    assert claim_next_job(database, "worker-b", now=NOW + timedelta(seconds=31)) is None
    recovered = claim_next_job(database, "worker-b", now=NOW + timedelta(seconds=51), lease_seconds=30)
    assert recovered is not None and recovered.attempt_count == 2
    with database.sessions.begin() as db:
        job = db.get(DiscoveryJob, job_id)
        job.attempt_count = job.max_attempts
        job.lease_expires_at = NOW + timedelta(seconds=52)
    assert claim_next_job(database, "worker-c", now=NOW + timedelta(seconds=53)) is None
    with database.sessions() as db:
        job = db.get(DiscoveryJob, job_id)
        assert job.status == "failed" and job.last_error_code == "worker_lease_expired"
    database.close()


def test_repeated_manual_request_joins_existing_active_job(tmp_path):
    database, _settings = scheduler_database(tmp_path)
    first = enqueue_due_sources(database, now=NOW)
    with database.sessions.begin() as db:
        scope = db.get(SourceScope, "source-1")
        scope.scan_requested_at = NOW + timedelta(minutes=1)
        scope.next_scan_at = scope.scan_requested_at
    second = enqueue_due_sources(database, now=NOW + timedelta(minutes=1))
    assert len(first) == 1 and second == ()
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(DiscoveryJob)) == 1
        assert db.get(SourceScope, "source-1").scan_requested_at is None
    database.close()


def test_manual_retry_resumes_failed_extraction_without_acquisition(tmp_path):
    database, _settings = scheduler_database(tmp_path, next_scan_at=NOW + timedelta(days=1))
    with database.sessions.begin() as db:
        run = SourceScanRun(
            id="completed-run", source_scope_id="source-1", status="succeeded",
            started_at=NOW - timedelta(hours=1), finished_at=NOW - timedelta(hours=1),
            pages_attempted=1, snapshots_created=1, unchanged_pages=0,
            traversal_truncated=False,
        )
        db.add(run)
        db.flush()
        db.add(DiscoveryJob(
            id="failed-extraction", source_scope_id="source-1", trigger="manual",
            window_start=NOW - timedelta(hours=1), status="failed", stage="extraction",
            attempt_count=3, max_attempts=3, available_at=NOW - timedelta(hours=1),
            scan_run_id=run.id, last_error_code="provider_unavailable",
        ))
        scope = db.get(SourceScope, "source-1")
        scope.scan_requested_at = NOW

    job_id = enqueue_due_sources(database, now=NOW)[0]
    with database.sessions() as db:
        retry = db.get(DiscoveryJob, job_id)
        assert retry.stage == "extraction"
        assert retry.scan_run_id == "completed-run"
        assert retry.trigger == "manual"
    database.close()


def test_complete_job_commits_each_stage_and_activates_without_long_write_lock(tmp_path):
    database, _settings = scheduler_database(tmp_path)
    job_id = enqueue_due_sources(database, now=NOW)[0]
    claim_next_job(database, "worker-a", now=NOW)
    provider = CountingProvider({"snapshot-1": draft()})
    status = run_claimed_job(
        database, job_id, "worker-a", scanner=successful_scanner,
        provider_factory=lambda: provider, now=lambda: NOW,
    )
    assert status == "succeeded" and provider.calls == 1
    with database.sessions() as db:
        job = db.get(DiscoveryJob, job_id)
        assert job.status == "succeeded" and job.stage == "complete" and job.scan_run_id == "run-1"
        artifact = db.scalar(select(DiscoveryExtractionArtifact))
        assert artifact.status == "activated"
        assert db.scalar(select(func.count()).select_from(Scholarship)) == 1
        assert db.get(AppSetting, "concurrent-writer").value == "succeeded"
    database.close()


def test_persisted_extraction_resumes_activation_without_repeating_provider(tmp_path):
    database, _settings = scheduler_database(tmp_path, next_scan_at=NOW + timedelta(days=1))
    with database.sessions.begin() as db:
        run = SourceScanRun(
            id="run-1", source_scope_id="source-1", status="succeeded", started_at=NOW,
            finished_at=NOW, pages_attempted=1, snapshots_created=1, unchanged_pages=0,
            traversal_truncated=False,
        )
        db.add(run); db.flush()
        db.add(SourceSnapshot(
            id="snapshot-1", source_scope_id="source-1", scan_run_id="run-1",
            canonical_url="https://sponsor.example/scholarships/community",
            final_url="https://sponsor.example/scholarships/community", acquired_at=NOW,
            content_hash="a" * 64, media_type="text/html", normalized_text=SOURCE,
            source_byte_count=len(SOURCE), redirect_count=0, depth=1,
        )); db.flush()
        job = DiscoveryJob(
            id="job-1", source_scope_id="source-1", trigger="scheduled", window_start=NOW,
            status="queued", stage="extraction", attempt_count=0, max_attempts=3,
            available_at=NOW, scan_run_id="run-1",
        )
        db.add(job); db.flush()
        db.add(DiscoveryExtractionArtifact(
            id="artifact-1", discovery_job_id="job-1", source_snapshot_id="snapshot-1",
            status="extracted", draft=draft().model_dump(mode="json"),
            extraction_model="fixture", prompt_version="2.0.0", schema_version="1.0.0",
        ))
    claim_next_job(database, "worker-a", now=NOW)
    provider = CountingProvider({"snapshot-1": ExtractionError("should_not_run", "Provider repeated")})
    assert run_claimed_job(database, "job-1", "worker-a", provider_factory=lambda: provider, now=lambda: NOW) == "succeeded"
    assert provider.calls == 0
    database.close()


def test_invalid_local_page_is_recorded_without_stopping_remaining_pages(tmp_path):
    database, _settings = scheduler_database(tmp_path, next_scan_at=NOW + timedelta(days=1))
    with database.sessions.begin() as db:
        run = SourceScanRun(
            id="local-run", source_scope_id="source-1", status="succeeded",
            started_at=NOW, finished_at=NOW, pages_attempted=2,
            snapshots_created=2, unchanged_pages=0, traversal_truncated=False,
        )
        db.add(run)
        db.flush()
        for index in (1, 2):
            db.add(SourceSnapshot(
                id=f"snapshot-{index}", source_scope_id="source-1", scan_run_id=run.id,
                canonical_url=f"https://sponsor.example/scholarships/{index}",
                final_url=f"https://sponsor.example/scholarships/{index}", acquired_at=NOW,
                content_hash=str(index) * 64, media_type="text/html", normalized_text=SOURCE,
                source_byte_count=len(SOURCE), redirect_count=0, depth=1,
            ))
        db.add(DiscoveryJob(
            id="local-job", source_scope_id="source-1", trigger="manual", window_start=NOW,
            status="queued", stage="extraction", attempt_count=0, max_attempts=3,
            available_at=NOW, scan_run_id=run.id,
        ))

    claim_next_job(database, "worker-a", now=NOW)
    provider = CountingProvider({
        "snapshot-1": ExtractionError("invalid_output", "Local draft failed validation."),
        "snapshot-2": draft("snapshot-2"),
    })
    assert run_claimed_job(
        database, "local-job", "worker-a", provider_factory=lambda: provider, now=lambda: NOW,
    ) == "succeeded"
    assert provider.calls == 2
    with database.sessions() as db:
        job = db.get(DiscoveryJob, "local-job")
        statuses = dict(db.execute(
            select(DiscoveryExtractionArtifact.source_snapshot_id, DiscoveryExtractionArtifact.status)
            .where(DiscoveryExtractionArtifact.discovery_job_id == "local-job")
        ).all())
        assert job.status == "succeeded" and job.stage == "complete" and job.last_error_code is None
        assert statuses == {"snapshot-1": "validation_failed", "snapshot-2": "activated"}
        assert db.scalar(select(func.count()).select_from(Scholarship)) == 1
    database.close()


def test_unchanged_scan_reuses_retained_snapshot_and_prior_extraction(tmp_path):
    database, _settings = scheduler_database(tmp_path, next_scan_at=NOW + timedelta(days=1))
    with database.sessions.begin() as db:
        original_run = SourceScanRun(
            id="original-run", source_scope_id="source-1", status="succeeded",
            started_at=NOW - timedelta(days=1), finished_at=NOW - timedelta(days=1),
            pages_attempted=1, snapshots_created=1, unchanged_pages=0, traversal_truncated=False,
        )
        db.add(original_run); db.flush()
        db.add(SourceSnapshot(
            id="retained-snapshot", source_scope_id="source-1", scan_run_id=original_run.id,
            canonical_url="https://sponsor.example/scholarships/community",
            final_url="https://sponsor.example/scholarships/community", acquired_at=NOW - timedelta(days=1),
            content_hash="b" * 64, media_type="text/html", normalized_text=SOURCE,
            source_byte_count=len(SOURCE), redirect_count=0, depth=1,
        ))
        db.add(SourcePageState(
            id="page-state", source_scope_id="source-1",
            canonical_url="https://sponsor.example/scholarships/community", status="current",
            first_seen_at=NOW - timedelta(days=1), last_seen_at=NOW,
        ))
        db.add(DiscoveryJob(
            id="prior-job", source_scope_id="source-1", trigger="scheduled",
            window_start=NOW - timedelta(days=1), status="failed", stage="extraction",
            attempt_count=3, max_attempts=3, available_at=NOW - timedelta(days=1),
            scan_run_id=original_run.id, last_error_code="provider_unavailable",
        ))
        db.flush()
        db.add(DiscoveryExtractionArtifact(
            id="prior-artifact", discovery_job_id="prior-job", source_snapshot_id="retained-snapshot",
            status="extracted", draft=draft("retained-snapshot").model_dump(mode="json"),
            extraction_model="fixture", prompt_version="2.0.0", schema_version="1.0.0",
        ))
        db.add(DiscoveryJob(
            id="current-job", source_scope_id="source-1", trigger="manual", window_start=NOW,
            status="queued", stage="acquisition", attempt_count=0, max_attempts=3, available_at=NOW,
        ))

    def unchanged_scanner(database: Database, source_id: str):
        with database.sessions.begin() as db:
            run = SourceScanRun(
                id="unchanged-run", source_scope_id=source_id, status="succeeded",
                started_at=NOW, finished_at=NOW, pages_attempted=1,
                snapshots_created=0, unchanged_pages=1, traversal_truncated=False,
            )
            db.add(run)
            return run

    claim_next_job(database, "worker-a", now=NOW)
    provider = CountingProvider({"retained-snapshot": ExtractionError("should_not_run", "Provider repeated")})
    status = run_claimed_job(
        database, "current-job", "worker-a", scanner=unchanged_scanner,
        provider_factory=lambda: provider, now=lambda: NOW,
    )
    assert status == "succeeded" and provider.calls == 0
    with database.sessions() as db:
        current = db.get(DiscoveryJob, "current-job")
        copied = db.scalar(select(DiscoveryExtractionArtifact).where(
            DiscoveryExtractionArtifact.discovery_job_id == "current-job",
            DiscoveryExtractionArtifact.source_snapshot_id == "retained-snapshot",
        ))
        assert current.stage == "complete" and current.scan_run_id == "unchanged-run"
        assert copied.status == "activated"
        assert db.scalar(select(func.count()).select_from(Scholarship)) == 1
    database.close()


def test_transient_failure_retries_with_backoff_and_permanent_failure_stops(tmp_path):
    database, _settings = scheduler_database(tmp_path)
    job_id = enqueue_due_sources(database, now=NOW)[0]
    claim_next_job(database, "worker-a", now=NOW)
    failed_scan = lambda _database, _source_id: SimpleNamespace(status="failed", error_code="timeout")
    assert run_claimed_job(database, job_id, "worker-a", scanner=failed_scan, provider_factory=lambda: None, now=lambda: NOW) == "retry_wait"
    with database.sessions() as db:
        job = db.get(DiscoveryJob, job_id)
        available = job.available_at.replace(tzinfo=timezone.utc) if job.available_at.tzinfo is None else job.available_at
        assert job.status == "retry_wait" and available > NOW

    second_time = NOW + timedelta(minutes=2)
    claim_next_job(database, "worker-b", now=second_time)
    assert run_claimed_job(database, job_id, "worker-b", scanner=failed_scan, provider_factory=lambda: None, now=lambda: second_time) == "retry_wait"
    third_time = NOW + timedelta(minutes=5)
    claim_next_job(database, "worker-c", now=third_time)
    assert run_claimed_job(database, job_id, "worker-c", scanner=failed_scan, provider_factory=lambda: None, now=lambda: third_time) == "failed"
    with database.sessions() as db:
        job = db.get(DiscoveryJob, job_id)
        assert job.status == "failed" and job.attempt_count == job.max_attempts == 3
    database.close()
