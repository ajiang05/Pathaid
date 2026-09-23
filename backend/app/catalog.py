"""Published-only query operations for the reviewed program catalog."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from .models import Program, ProgramRevision


def _published_revision_query() -> Select:
    """Build the shared query that enforces the publication boundary."""

    # Both checks matter: the program must point at this exact revision, and
    # the revision itself must be marked published. A draft or rejected record
    # cannot become public merely because a pointer was set incorrectly.
    return (
        select(ProgramRevision)
        .join(
            Program,
            (Program.id == ProgramRevision.program_id)
            & (Program.current_published_revision_id == ProgramRevision.id),
        )
        .where(ProgramRevision.status == "published")
        .options(selectinload(ProgramRevision.sources), selectinload(ProgramRevision.program))
    )


def list_published_revisions(
    db: Session,
    *,
    categories: Iterable[str] | None = None,
) -> list[ProgramRevision]:
    """Return public revisions, optionally matching any requested category."""

    revisions = list(db.scalars(_published_revision_query()).unique())
    requested = set(categories or ())
    if requested:
        # The MVP catalog contains only 10–20 records. Filtering its reviewed
        # JSON categories in Python stays portable across SQLite tests and
        # PostgreSQL deployment without hiding database-specific behavior.
        revisions = [revision for revision in revisions if requested.intersection(revision.categories)]
    return sorted(revisions, key=lambda revision: (revision.name.casefold(), revision.id))


def get_published_revision(db: Session, program_id: str) -> ProgramRevision | None:
    """Return one program's current public revision or None."""

    return db.scalar(_published_revision_query().where(Program.id == program_id))


def get_published_revision_by_slug(db: Session, slug: str) -> ProgramRevision | None:
    """Resolve a public revision through its stable human-readable slug."""

    return db.scalar(_published_revision_query().where(Program.slug == slug))
