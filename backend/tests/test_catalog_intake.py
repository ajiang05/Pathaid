"""Tests for the reviewed launch catalog intake boundary."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.catalog_intake import CatalogIntakeManifest, load_manifest, manifest_summary, queue_manifest
from app.database import Base
from app.models import IngestionRun, Program


MANIFEST_PATH = Path(__file__).parents[1] / "data" / "catalog_intake_v1.json"


def test_launch_manifest_meets_size_diversity_and_candidate_boundary():
    """The checked-in intake covers the MVP without claiming human review."""

    manifest = load_manifest(MANIFEST_PATH)
    summary = manifest_summary(manifest)

    assert summary["candidates"] == 12
    assert summary["categories"] == {
        "emergency": 1,
        "food": 1,
        "grants": 3,
        "housing": 1,
        "scholarships": 6,
    }
    assert summary["reviewed"] == 0
    assert summary["published"] == 0
    assert all(entry.intake_status == "candidate" for entry in manifest.entries)


def test_manifest_rejects_duplicate_sources_and_missing_category():
    """A superficially large list cannot pass without unique, balanced sources."""

    raw = load_manifest(MANIFEST_PATH).model_dump(mode="json")
    raw["entries"][1]["source_url"] = raw["entries"][0]["source_url"]
    with pytest.raises(ValidationError, match="source URLs must be unique"):
        CatalogIntakeManifest.model_validate(raw)

    raw = load_manifest(MANIFEST_PATH).model_dump(mode="json")
    raw["entries"][-1]["category"] = "grants"
    with pytest.raises(ValidationError, match="every MVP assistance category"):
        CatalogIntakeManifest.model_validate(raw)


def test_queue_is_idempotent_and_creates_no_published_programs(tmp_path):
    """Intake starts reviewable runs and cannot bypass acquisition or approval."""

    engine = create_engine(f"sqlite:///{tmp_path / 'intake.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            manifest = load_manifest(MANIFEST_PATH)
            assert queue_manifest(db, manifest) == {"created": 12, "existing": 0}
            assert queue_manifest(db, manifest) == {"created": 0, "existing": 12}
            runs = list(db.scalars(select(IngestionRun).order_by(IngestionRun.idempotency_key)))
            assert len(runs) == 12
            assert all(run.state == "queued" and run.source_method == "webpage" for run in runs)
            assert list(db.scalars(select(Program))) == []
    finally:
        engine.dispose()


def test_queue_can_limit_first_live_run_to_one_named_candidate(tmp_path):
    """A live-model smoke test can start one source without launching the batch."""

    engine = create_engine(f"sqlite:///{tmp_path / 'single-intake.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            manifest = load_manifest(MANIFEST_PATH)
            result = queue_manifest(db, manifest, entry_id="gates-scholarship")
            assert result == {"created": 1, "existing": 0}
            runs = list(db.scalars(select(IngestionRun)))
            assert len(runs) == 1
            assert runs[0].idempotency_key == "catalog-intake:1.0.0:gates-scholarship"

            with pytest.raises(ValueError, match="unknown catalog intake entry"):
                queue_manifest(db, manifest, entry_id="not-in-the-manifest")
    finally:
        engine.dispose()
