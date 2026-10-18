"""Export and import reviewed catalog bundles without inventing approvals."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import SessionLocal
from .eligibility import validate_rule_tree
from .models import Program, ProgramRevision, ReviewEvent, SourceSnapshot
from .profile_fields import FIELDS


BUNDLE_VERSION = "1.0.0"


class BundleModel(BaseModel):
    """Reject undocumented fields in a portable catalog artifact."""

    model_config = ConfigDict(extra="forbid")


class BundleSource(BundleModel):
    """One immutable source snapshot, including the evidence-bearing body."""

    id: str
    source_url: str
    final_url: str | None
    acquisition_method: Literal["webpage", "pasted_text"]
    media_type: str | None
    source_byte_count: int | None
    redirect_count: int | None
    acquired_at: datetime
    content_hash: str
    source_text: str


class BundleReview(BundleModel):
    """A real approval copied from the source database."""

    id: str
    reviewer: str
    decision: Literal["approved"]
    notes: str | None
    created_at: datetime


class BundleRevision(BundleModel):
    """The exact published revision selected by one program."""

    id: str
    name: str
    description: str
    categories: list[str]
    coverage: dict[str, Any]
    checklist: list[Any]
    eligibility_tree: dict[str, Any]
    coverage_complete: bool
    award_cycle: str | None
    application_deadline: datetime | None
    deadline_timezone: str | None
    application_availability: Literal["open", "closed", "unknown"]
    assistance_amount: str | None
    selection_factors: list[Any]
    unresolved_conditions: list[Any]
    provider_url: str
    application_url: str | None
    verified_at: datetime
    created_at: datetime
    sources: list[BundleSource] = Field(min_length=1)
    review: BundleReview


class BundleProgram(BundleModel):
    """Stable program identity plus its current reviewed publication."""

    id: str
    slug: str
    created_at: datetime
    revision: BundleRevision


class CatalogBundle(BundleModel):
    """Versioned collection accepted by the explicit seed command."""

    version: Literal["1.0.0"]
    exported_at: datetime
    programs: list[BundleProgram]


def export_catalog_bundle(db: Session) -> CatalogBundle:
    """Export current publications only when each retains one real approval."""

    programs = list(
        db.scalars(
            select(Program)
            .where(Program.current_published_revision_id.is_not(None))
            .options(
                selectinload(Program.revisions).selectinload(ProgramRevision.sources),
                selectinload(Program.revisions).selectinload(ProgramRevision.review_events),
            )
            .order_by(Program.slug)
        ).unique()
    )
    exported: list[BundleProgram] = []
    for program in programs:
        revision = next(
            (item for item in program.revisions if item.id == program.current_published_revision_id),
            None,
        )
        approvals = [event for event in revision.review_events if event.decision == "approved"] if revision else []
        if revision is None or revision.status != "published" or revision.verified_at is None or len(approvals) != 1:
            raise ValueError(f"Program {program.slug} lacks one reviewed current publication")
        exported.append(_bundle_program(program, revision, approvals[0]))
    return CatalogBundle(version=BUNDLE_VERSION, exported_at=datetime.now(timezone.utc), programs=exported)


def import_catalog_bundle(db: Session, bundle: CatalogBundle) -> dict[str, int]:
    """Import reviewed publications atomically and leave existing data unchanged."""

    imported = skipped = 0
    try:
        for item in bundle.programs:
            _validate_bundle_program(item)
            existing_program = db.get(Program, item.id)
            existing_revision = db.get(ProgramRevision, item.revision.id)
            if existing_program is not None or existing_revision is not None:
                if (
                    existing_program is not None
                    and existing_revision is not None
                    and existing_program.slug == item.slug
                    and existing_program.current_published_revision_id == item.revision.id
                    and existing_revision.program_id == item.id
                    and existing_revision.status == "published"
                ):
                    skipped += 1
                    continue
                raise ValueError(f"Catalog bundle conflicts with existing program {item.slug}")

            sources = [_import_source(db, source) for source in item.revision.sources]
            program = Program(id=item.id, slug=item.slug, created_at=item.created_at)
            revision = ProgramRevision(
                id=item.revision.id,
                program=program,
                status="published",
                validation_status="valid",
                validation_findings=[],
                name=item.revision.name,
                description=item.revision.description,
                categories=item.revision.categories,
                coverage=item.revision.coverage,
                checklist=item.revision.checklist,
                eligibility_tree=item.revision.eligibility_tree,
                coverage_complete=item.revision.coverage_complete,
                award_cycle=item.revision.award_cycle,
                application_deadline=item.revision.application_deadline,
                deadline_timezone=item.revision.deadline_timezone,
                application_availability=item.revision.application_availability,
                assistance_amount=item.revision.assistance_amount,
                selection_factors=item.revision.selection_factors,
                unresolved_conditions=item.revision.unresolved_conditions,
                provider_url=item.revision.provider_url,
                application_url=item.revision.application_url,
                verified_at=item.revision.verified_at,
                created_at=item.revision.created_at,
            )
            revision.sources.extend(sources)
            revision.review_events.append(
                ReviewEvent(
                    id=item.revision.review.id,
                    reviewer=item.revision.review.reviewer,
                    decision="approved",
                    notes=item.revision.review.notes,
                    created_at=item.revision.review.created_at,
                )
            )
            db.add(program)
            db.flush()
            program.current_published_revision_id = revision.id
            imported += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"imported": imported, "skipped": skipped}


def _bundle_program(program: Program, revision: ProgramRevision, approval: ReviewEvent) -> BundleProgram:
    """Convert ORM records without exporting drafts, sessions, or student data."""

    return BundleProgram(
        id=program.id,
        slug=program.slug,
        created_at=program.created_at,
        revision=BundleRevision(
            id=revision.id,
            name=revision.name,
            description=revision.description,
            categories=revision.categories,
            coverage=revision.coverage,
            checklist=revision.checklist,
            eligibility_tree=revision.eligibility_tree,
            coverage_complete=revision.coverage_complete,
            award_cycle=revision.award_cycle,
            application_deadline=revision.application_deadline,
            deadline_timezone=revision.deadline_timezone,
            application_availability=revision.application_availability,
            assistance_amount=revision.assistance_amount,
            selection_factors=revision.selection_factors,
            unresolved_conditions=revision.unresolved_conditions,
            provider_url=revision.provider_url,
            application_url=revision.application_url,
            verified_at=revision.verified_at,
            created_at=revision.created_at,
            sources=[BundleSource.model_validate(source, from_attributes=True) for source in revision.sources],
            review=BundleReview.model_validate(approval, from_attributes=True),
        ),
    )


def _validate_bundle_program(item: BundleProgram) -> None:
    """Require valid rules and evidence tied to retained bundle sources."""

    validate_rule_tree(item.revision.eligibility_tree, FIELDS)
    sources = {source.id: source for source in item.revision.sources}
    if len(sources) != len(item.revision.sources):
        raise ValueError(f"Program {item.slug} repeats a source ID")
    for evidence in _evidence_references(
        [item.revision.eligibility_tree, item.revision.checklist, item.revision.selection_factors, item.revision.unresolved_conditions]
    ):
        source = sources.get(evidence.get("snapshot_id"))
        excerpt = evidence.get("excerpt")
        if source is None or not isinstance(excerpt, str) or excerpt not in source.source_text:
            raise ValueError(f"Program {item.slug} contains evidence outside its retained source")


def _evidence_references(value: Any):
    """Yield evidence objects from nested reviewed JSON fields."""

    if isinstance(value, dict):
        evidence = value.get("evidence")
        if isinstance(evidence, dict):
            yield evidence
        for child in value.values():
            yield from _evidence_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _evidence_references(child)


def _import_source(db: Session, source: BundleSource) -> SourceSnapshot:
    """Reuse an identical immutable source or reject an ID collision."""

    existing = db.get(SourceSnapshot, source.id)
    if existing is not None:
        if existing.content_hash != source.content_hash or existing.source_text != source.source_text:
            raise ValueError(f"Source {source.id} conflicts with retained data")
        return existing
    return SourceSnapshot(**source.model_dump())


def main() -> None:
    """Run an explicit reviewed catalog export or idempotent import."""

    parser = argparse.ArgumentParser(description="Manage reviewed Pathaid catalog bundles")
    subcommands = parser.add_subparsers(dest="command", required=True)
    export_parser = subcommands.add_parser("export")
    export_parser.add_argument("path", type=Path)
    import_parser = subcommands.add_parser("import")
    import_parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    with SessionLocal() as db:
        if arguments.command == "export":
            bundle = export_catalog_bundle(db)
            arguments.path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
            print(f"Exported {len(bundle.programs)} reviewed programs.")
        else:
            bundle = CatalogBundle.model_validate_json(arguments.path.read_text(encoding="utf-8"))
            result = import_catalog_bundle(db, bundle)
            print(f"Imported {result['imported']} reviewed programs; skipped {result['skipped']} existing programs.")


if __name__ == "__main__":
    main()
