"""Schema-level tests for versioned program catalog storage."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Program, ProgramRevision, ReviewEvent, SourceSnapshot


@pytest.fixture
def database():
    """Provide a fresh catalog schema in an in-memory SQLite database."""

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def make_revision(program: Program, *, status: str = "draft", name: str = "Synthetic Scholarship") -> ProgramRevision:
    """Build a complete synthetic revision without claiming a real program."""

    return ProgramRevision(
        program=program,
        status=status,
        name=name,
        description="Synthetic catalog record used only for schema testing.",
        categories=["scholarships"],
        coverage={"type": "national"},
        checklist=[{"label": "Review the official application"}],
        eligibility_tree={
            "type": "condition",
            "field": "state",
            "operator": "eq",
            "value": "MA",
            "evidence": {"snapshot_id": "filled-after-flush", "excerpt": "Synthetic requirement."},
        },
        coverage_complete=True,
        application_availability="unknown",
        selection_factors=[],
        provider_url="https://example.edu/program",
        verified_at=datetime.now(timezone.utc),
    )


def test_catalog_tables_and_indexes_exist(database):
    """The SQLAlchemy metadata creates every table required by Feature 05."""

    schema = inspect(database)
    assert {"programs", "program_revisions", "source_snapshots", "revision_sources", "review_events"}.issubset(schema.get_table_names())
    program_indexes = {index["name"] for index in schema.get_indexes("programs")}
    assert "ix_programs_current_published_revision_id" in program_indexes


def test_revision_preserves_sources_and_review_history(database):
    """A revision retains its source snapshots and explicit review decision."""

    with Session(database) as db:
        program = Program(slug="synthetic-scholarship")
        source = SourceSnapshot(
            source_url="https://example.edu/program",
            acquisition_method="webpage",
            content_hash="a" * 64,
            source_text="Synthetic source text.",
        )
        revision = make_revision(program, status="published")
        revision.sources.append(source)
        revision.review_events.append(ReviewEvent(reviewer="reviewer@example.edu", decision="approved", notes="Synthetic approval."))
        db.add(program)
        db.flush()
        program.current_published_revision_id = revision.id
        db.commit()

        stored = db.scalar(select(Program).where(Program.slug == "synthetic-scholarship"))
        assert stored.current_published_revision_id == revision.id
        assert stored.revisions[0].sources[0].content_hash == "a" * 64
        assert stored.revisions[0].review_events[0].decision == "approved"


def test_program_slug_is_unique(database):
    """Stable program slugs cannot identify two different programs."""

    with Session(database) as db:
        db.add_all([Program(slug="same-slug"), Program(slug="same-slug")])
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize("invalid_status", ["awaiting_review", "deleted", ""])
def test_revision_status_constraint(database, invalid_status):
    """Catalog revisions accept only the documented lifecycle states."""

    with Session(database) as db:
        revision = make_revision(Program(slug=f"status-{invalid_status or 'empty'}"), status=invalid_status)
        db.add(revision)
        with pytest.raises(IntegrityError):
            db.commit()
