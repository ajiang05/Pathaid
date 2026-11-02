"""Narrow authenticated context API for the local Chrome extension."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Database
from .models import SavedScholarship, Scholarship, ScholarshipVersion
from .source_acquisition import AcquisitionError, validate_source_url


def _public_origin(value: str) -> str:
    """Require a canonical public origin with no path, query, or credentials."""

    try:
        validated = validate_source_url(value)
    except AcquisitionError as error:
        raise HTTPException(422, detail="Invalid portal origin") from error
    parsed = urlsplit(validated.url)
    if parsed.path != "/" or parsed.query:
        raise HTTPException(422, detail="Portal origin cannot contain a path or query")
    return f"{parsed.scheme}://{parsed.netloc}"


def _url_origin(value: str) -> str | None:
    try:
        validated = validate_source_url(value)
    except AcquisitionError:
        return None
    parsed = urlsplit(validated.url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _adapter_for(hostname: str) -> str:
    host = hostname.casefold()
    if host == "academicworks.com" or host.endswith(".academicworks.com"):
        return "academicworks"
    if host == "mykaleidoscope.com" or host.endswith(".mykaleidoscope.com"):
        return "kaleidoscope"
    return "generic"


def create_extension_router(database: Database, require_extension) -> APIRouter:
    """Resolve only user-started applications whose official origin matches."""

    router = APIRouter(
        prefix="/api/extension",
        tags=["extension"],
        dependencies=[Depends(require_extension)],
    )

    def get_db():
        yield from database.session()

    @router.get("/context")
    def portal_context(
        portal_origin: str = Query(min_length=8, max_length=500),
        scholarship_id: str | None = Query(default=None, min_length=1, max_length=36),
        db: Session = Depends(get_db),
    ) -> dict:
        origin = _public_origin(portal_origin)
        rows = db.execute(
            select(SavedScholarship, Scholarship, ScholarshipVersion)
            .join(Scholarship, Scholarship.id == SavedScholarship.scholarship_id)
            .join(ScholarshipVersion, ScholarshipVersion.id == Scholarship.active_version_id)
            .where(SavedScholarship.status == "in_progress", Scholarship.status == "active")
            .order_by(Scholarship.id)
        ).all()
        matches = []
        for _saved, scholarship, version in rows:
            if scholarship_id is not None and scholarship.id != scholarship_id:
                continue
            application_url = version.data.get("application_url") or scholarship.source_url
            if _url_origin(application_url) == origin:
                matches.append((scholarship, version, application_url))
        if not matches:
            return {
                "state": "unsupported",
                "reason": "This portal is not linked to an In progress scholarship.",
            }
        if len(matches) > 1:
            return {
                "state": "ambiguous",
                "reason": "More than one In progress scholarship uses this portal.",
            }
        scholarship, version, application_url = matches[0]
        parsed = urlsplit(application_url)
        return {
            "state": "supported",
            "scholarship_id": scholarship.id,
            "scholarship_name": version.data["name"],
            "portal_origin": origin,
            "application_url": application_url,
            "adapter": _adapter_for(parsed.hostname or ""),
        }

    return router
