"""Schema tests for durable ingestion runs and stage history."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import IngestionRun, IngestionStageAttempt


@pytest.fixture
def database():
    """Create the complete current schema in memory."""

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def make_run(key: str = "request-1") -> IngestionRun:
    """Build the minimum valid queued workflow record."""

    return IngestionRun(
        idempotency_key=key,
        request_fingerprint="a" * 64,
        source_url="https://example.edu/aid",
        source_method="webpage",
        state="queued",
        validation_findings=[],
    )


def test_ingestion_tables_and_indexes_exist(database):
    """Metadata includes durable runs, attempts, and claim indexes."""

    schema = inspect(database)
    assert {"ingestion_runs", "ingestion_stage_attempts"} <= set(schema.get_table_names())
    indexes = {index["name"] for index in schema.get_indexes("ingestion_runs")}
    assert {"ix_ingestion_runs_idempotency_key", "ix_ingestion_runs_state", "ix_ingestion_runs_lease_expires_at"} <= indexes


def test_run_retains_append_only_stage_history(database):
    """A run owns ordered stage attempts needed to explain retries."""

    started = datetime.now(timezone.utc)
    run = make_run()
    run.stage_attempts.append(IngestionStageAttempt(stage="acquiring", attempt_number=1, outcome="succeeded", started_at=started, completed_at=started, latency_ms=0))
    with Session(database) as db:
        db.add(run)
        db.commit()
        db.refresh(run)
        assert run.stage_attempts[0].attempt_number == 1
        assert run.stage_attempts[0].outcome == "succeeded"


def test_idempotency_key_is_unique(database):
    """The database prevents duplicate workflows during concurrent submission."""

    with Session(database) as db:
        db.add_all([make_run("same-key"), make_run("same-key")])
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize("field,value", [("state", "unknown"), ("source_method", "pdf")])
def test_run_lifecycle_constraints(database, field, value):
    """Only documented states and source methods can be persisted."""

    run = make_run(field)
    setattr(run, field, value)
    with Session(database) as db:
        db.add(run)
        with pytest.raises(IntegrityError):
            db.commit()
