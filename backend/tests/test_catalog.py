"""Tests for the catalog's published-only query boundary."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.catalog import get_published_revision, get_published_revision_by_slug, list_published_revisions
from app.database import Base
from app.models import Program, ProgramRevision


def revision(program: Program, name: str, status: str, categories: list[str]) -> ProgramRevision:
    """Create a complete synthetic revision for catalog query tests."""

    return ProgramRevision(
        program=program,
        status=status,
        name=name,
        description="Synthetic program used only by automated tests.",
        categories=categories,
        coverage={"type": "national"},
        checklist=[],
        eligibility_tree={
            "type": "unsupported",
            "description": "Synthetic provider review",
            "evidence": {"snapshot_id": "synthetic", "excerpt": "Synthetic evidence."},
        },
        coverage_complete=False,
        application_availability="unknown",
        selection_factors=[],
        provider_url="https://example.edu/program",
    )


def setup_catalog() -> tuple[object, dict[str, str]]:
    """Create public, draft-only, rejected, and replacement-draft records."""

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        alpha = Program(slug="alpha")
        alpha_public = revision(alpha, "Alpha Scholarship", "published", ["scholarships"])
        alpha_draft = revision(alpha, "Alpha Scholarship Updated", "draft", ["scholarships"])
        beta = Program(slug="beta")
        beta_draft = revision(beta, "Beta Grant", "draft", ["grants"])
        gamma = Program(slug="gamma")
        gamma_rejected = revision(gamma, "Gamma Support", "rejected", ["emergency"])
        delta = Program(slug="delta")
        delta_public = revision(delta, "Delta Grant", "published", ["grants"])
        db.add_all([alpha, beta, gamma, delta])
        db.flush()
        alpha.current_published_revision_id = alpha_public.id
        delta.current_published_revision_id = delta_public.id
        db.commit()
        ids = {
            "alpha": alpha.id,
            "alpha_public": alpha_public.id,
            "alpha_draft": alpha_draft.id,
            "beta": beta.id,
            "gamma": gamma.id,
            "delta": delta.id,
        }
    return engine, ids


def test_list_returns_only_current_published_revisions():
    """Draft-only and rejected programs never cross the public boundary."""

    engine, ids = setup_catalog()
    with Session(engine) as db:
        results = list_published_revisions(db)
        assert [item.name for item in results] == ["Alpha Scholarship", "Delta Grant"]
        assert results[0].id == ids["alpha_public"]
        assert results[0].id != ids["alpha_draft"]
    engine.dispose()


def test_category_filter_matches_any_requested_category():
    """Category filtering applies only after the publication boundary."""

    engine, _ = setup_catalog()
    with Session(engine) as db:
        assert [item.name for item in list_published_revisions(db, categories=["grants"])] == ["Delta Grant"]
        assert list_published_revisions(db, categories=["housing"]) == []
    engine.dispose()


def test_detail_lookup_hides_nonpublic_programs():
    """ID and slug lookups return None unless a valid published pointer exists."""

    engine, ids = setup_catalog()
    with Session(engine) as db:
        assert get_published_revision(db, ids["alpha"]).name == "Alpha Scholarship"
        assert get_published_revision_by_slug(db, "alpha").name == "Alpha Scholarship"
        assert get_published_revision(db, ids["beta"]) is None
        assert get_published_revision_by_slug(db, "gamma") is None
    engine.dispose()


def test_replacement_draft_does_not_replace_published_revision():
    """Creating a replacement draft leaves the prior public record intact."""

    engine, ids = setup_catalog()
    with Session(engine) as db:
        current = get_published_revision(db, ids["alpha"])
        assert current.id == ids["alpha_public"]
        assert current.name == "Alpha Scholarship"
    engine.dispose()
