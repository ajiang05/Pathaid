"""Tests for preserving reviewed catalog records across demo databases."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.catalog_seed import CatalogBundle, export_catalog_bundle, import_catalog_bundle
from app.database import Base
from app.models import Program, ProgramRevision, ReviewEvent, SourceSnapshot, Student


NOW = datetime(2027, 2, 1, 12, tzinfo=timezone.utc)
SOURCE_TEXT = "Applicants must have a GPA of at least 3.0."


def database(tmp_path, name):
    """Create one isolated catalog database."""

    engine = create_engine(f"sqlite:///{tmp_path / name}")
    Base.metadata.create_all(engine)
    return engine


def reviewed_program(db: Session) -> Program:
    """Insert one publication with retained evidence and a real approval record."""

    source = SourceSnapshot(
        id="source-1",
        source_url="https://example.edu/scholarship",
        final_url="https://example.edu/scholarship",
        acquisition_method="webpage",
        media_type="text/html",
        source_byte_count=100,
        redirect_count=0,
        acquired_at=NOW,
        content_hash="a" * 64,
        source_text=SOURCE_TEXT,
    )
    program = Program(id="program-1", slug="reviewed-scholarship", created_at=NOW)
    revision = ProgramRevision(
        id="revision-1",
        program=program,
        status="published",
        validation_status="valid",
        validation_findings=[],
        name="Reviewed Scholarship",
        description="A manually reviewed synthetic fixture.",
        categories=["scholarships"],
        coverage={"national": True, "states": [], "institutions": []},
        checklist=[],
        eligibility_tree={
            "type": "condition",
            "field": "gpa",
            "operator": "gte",
            "value": 3.0,
            "evidence": {"snapshot_id": source.id, "excerpt": SOURCE_TEXT},
        },
        coverage_complete=True,
        application_availability="unknown",
        selection_factors=[],
        unresolved_conditions=[],
        provider_url=source.source_url,
        verified_at=NOW,
        created_at=NOW,
    )
    revision.sources.append(source)
    revision.review_events.append(
        ReviewEvent(
            id="review-1",
            reviewer="reviewer@example.edu",
            decision="approved",
            notes="Reviewed against retained source.",
            created_at=NOW,
        )
    )
    db.add(program)
    db.flush()
    program.current_published_revision_id = revision.id
    db.commit()
    return program


def test_export_import_preserves_approval_and_is_idempotent(tmp_path):
    """Seed import copies review provenance and never creates a second event."""

    source_engine = database(tmp_path, "source.db")
    target_engine = database(tmp_path, "target.db")
    try:
        with Session(source_engine) as db:
            reviewed_program(db)
            bundle = export_catalog_bundle(db)
        assert len(bundle.programs) == 1
        assert bundle.programs[0].revision.review.reviewer == "reviewer@example.edu"

        with Session(target_engine) as db:
            assert import_catalog_bundle(db, bundle) == {"imported": 1, "skipped": 0}
            assert import_catalog_bundle(db, bundle) == {"imported": 0, "skipped": 1}
            program = db.get(Program, "program-1")
            assert program.current_published_revision_id == "revision-1"
            assert db.scalars(select(ReviewEvent)).one().id == "review-1"
            assert db.scalars(select(Student)).all() == []
    finally:
        source_engine.dispose()
        target_engine.dispose()


def test_import_rejects_evidence_not_found_in_retained_source(tmp_path):
    """A seed bundle cannot bypass the catalog's exact-evidence boundary."""

    source_engine = database(tmp_path, "invalid-source.db")
    target_engine = database(tmp_path, "invalid-target.db")
    try:
        with Session(source_engine) as db:
            reviewed_program(db)
            raw = export_catalog_bundle(db).model_dump(mode="json")
        raw["programs"][0]["revision"]["eligibility_tree"]["evidence"]["excerpt"] = "Invented requirement."
        bundle = CatalogBundle.model_validate(raw)
        with Session(target_engine) as db:
            with pytest.raises(ValueError, match="outside its retained source"):
                import_catalog_bundle(db, bundle)
            assert db.scalars(select(Program)).all() == []
    finally:
        source_engine.dispose()
        target_engine.dispose()


def test_export_rejects_a_publication_without_an_approval(tmp_path):
    """Seed export cannot turn a status flag into fabricated human review."""

    engine = database(tmp_path, "unreviewed.db")
    try:
        with Session(engine) as db:
            program = reviewed_program(db)
            db.delete(program.revisions[0].review_events[0])
            db.commit()
            with pytest.raises(ValueError, match="lacks one reviewed"):
                export_catalog_bundle(db)
    finally:
        engine.dispose()
