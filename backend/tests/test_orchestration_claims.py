"""Tests for idempotent submission, leases, and manual retries."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import IngestionRun, SourceSnapshot
from app.orchestration import (
    IngestionSubmission,
    OrchestrationError,
    claim_next_run,
    create_ingestion_run,
    create_manual_retry,
    require_lease,
)
from app.source_acquisition import PastedSourceRequest, WebSourceRequest


NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)


@pytest.fixture
def sessions(tmp_path):
    """Use a file database so independent sessions observe claim races."""

    engine = create_engine(f"sqlite:///{tmp_path / 'claims.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def submission(key="key-1", text="Aid details"):
    """Build a pasted-source request with a stable idempotency key."""

    return IngestionSubmission(key, PastedSourceRequest("https://example.edu/aid", text))


def test_duplicate_submission_returns_the_same_run(sessions):
    """Matching idempotency input creates exactly one workflow."""

    with sessions() as db:
        first = create_ingestion_run(db, submission())
        second = create_ingestion_run(db, submission())
        assert first.id == second.id
        assert db.query(IngestionRun).count() == 1


def test_reused_key_with_different_input_is_rejected(sessions):
    """An idempotency key cannot hide a changed source body."""

    with sessions() as db:
        create_ingestion_run(db, submission())
        with pytest.raises(OrchestrationError) as caught:
            create_ingestion_run(db, submission(text="Different details"))
        assert caught.value.code == "idempotency_conflict"


def test_only_one_worker_claims_a_run(sessions):
    """The conditional update prevents a second active lease."""

    with sessions() as db:
        run = create_ingestion_run(db, submission())
    with sessions() as first, sessions() as second:
        lease = claim_next_run(first, "worker-a", clock=lambda: NOW)
        competing = claim_next_run(second, "worker-b", clock=lambda: NOW)
        assert lease.run_id == run.id
        assert competing is None


def test_expired_lease_is_recovered_and_old_token_is_fenced(sessions):
    """A restarted worker can recover work while the stale owner is rejected."""

    with sessions() as db:
        create_ingestion_run(db, submission())
        old = claim_next_run(db, "worker-a", clock=lambda: NOW)
    later = NOW + timedelta(minutes=3)
    with sessions() as db:
        replacement = claim_next_run(db, "worker-b", clock=lambda: later)
        assert replacement.run_id == old.run_id
        with pytest.raises(OrchestrationError, match="no longer owns"):
            require_lease(db, old, clock=lambda: later)


def test_not_yet_due_retry_cannot_be_claimed(sessions):
    """Backoff timestamps prevent tight worker retry loops."""

    with sessions() as db:
        run = create_ingestion_run(db, submission())
        run.state = "extracting"
        run.next_attempt_at = NOW + timedelta(seconds=5)
        db.commit()
        assert claim_next_run(db, "worker", clock=lambda: NOW) is None
        assert claim_next_run(db, "worker", clock=lambda: NOW + timedelta(seconds=5)) is not None


def test_manual_retry_links_history_and_reuses_snapshot(sessions):
    """A failed later stage starts a child run at extraction."""

    with sessions() as db:
        failed = create_ingestion_run(db, IngestionSubmission("old", WebSourceRequest("https://example.edu/aid")))
        snapshot = SourceSnapshot(
            source_url="https://example.edu/aid",
            final_url="https://example.edu/aid",
            acquisition_method="webpage",
            content_hash="a" * 64,
            source_text="Retained source.",
        )
        db.add(snapshot)
        db.flush()
        failed.state = "failed"
        failed.source_snapshot_id = snapshot.id
        db.commit()
        child = create_manual_retry(db, failed.id, "manual-1")
        assert child.parent_run_id == failed.id
        assert child.source_snapshot_id == snapshot.id
        assert child.state == "extracting"


def test_valid_lease_loads_owned_run(sessions):
    """The exact unexpired fencing token authorizes stage updates."""

    with sessions() as db:
        create_ingestion_run(db, submission())
        lease = claim_next_run(db, "worker", clock=lambda: NOW)
        assert require_lease(db, lease, clock=lambda: NOW).state == "acquiring"
