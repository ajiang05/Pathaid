"""Narrow authenticated context API for the local Chrome extension."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Database
from .document_vault import DocumentVaultError, decrypt_document
from .models import Document, Essay, LocalProfile, PortalMapping, SavedScholarship, Scholarship, ScholarshipVersion
from .profile_fields import FIELDS, is_unknown
from .source_acquisition import AcquisitionError, validate_source_url


SIGNATURE_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class PortalMappingInput(BaseModel):
    """One value-free correction produced from a reviewed preview."""

    model_config = ConfigDict(extra="forbid")
    field_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile_field: str | None = Field(default=None, min_length=1, max_length=80)


class PortalMappingBatch(BaseModel):
    """Bounded mapping replacement for fields reviewed in one form."""

    model_config = ConfigDict(extra="forbid")
    portal_origin: str = Field(min_length=8, max_length=500)
    scholarship_id: str = Field(min_length=1, max_length=36)
    form_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    mappings: list[PortalMappingInput] = Field(max_length=200)


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


def _matching_contexts(db: Session, origin: str, scholarship_id: str | None):
    """Return active user-started applications on one exact portal origin."""

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
    return matches


def _single_context(db: Session, portal_origin: str, scholarship_id: str | None):
    origin = _public_origin(portal_origin)
    matches = _matching_contexts(db, origin, scholarship_id)
    if len(matches) != 1:
        return origin, matches, None
    return origin, matches, matches[0]


def _automation_blocked(context) -> bool:
    """Read only the deterministically validated active-version policy flag."""

    return context is not None and context[1].data.get("automation_policy", "unknown") == "blocked"


def create_extension_router(database: Database, require_extension, secret_store) -> APIRouter:
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
        origin, matches, context = _single_context(db, portal_origin, scholarship_id)
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
        scholarship, version, application_url = context
        parsed = urlsplit(application_url)
        if _automation_blocked(context):
            return {
                "state": "policy_blocked",
                "scholarship_id": scholarship.id,
                "scholarship_name": version.data["name"],
                "portal_origin": origin,
                "reason": "Official rules prohibit automated application assistance.",
                "automation_policy": "blocked",
            }
        return {
            "state": "supported",
            "scholarship_id": scholarship.id,
            "scholarship_name": version.data["name"],
            "portal_origin": origin,
            "application_url": application_url,
            "adapter": _adapter_for(parsed.hostname or ""),
        }

    @router.put("/applications/{scholarship_id}/prepare")
    def prepare_application(scholarship_id: str, db: Session = Depends(get_db)) -> dict:
        """Start tracking and return only the retained official application URL."""

        row = db.execute(
            select(SavedScholarship, Scholarship, ScholarshipVersion)
            .join(Scholarship, Scholarship.id == SavedScholarship.scholarship_id)
            .join(ScholarshipVersion, ScholarshipVersion.id == Scholarship.active_version_id)
            .where(
                SavedScholarship.scholarship_id == scholarship_id,
                Scholarship.status == "active",
            )
        ).one_or_none()
        if row is None:
            raise HTTPException(404, detail="Saved scholarship is unavailable")
        saved, scholarship, version = row
        application_url = version.data.get("application_url") or scholarship.source_url
        if _url_origin(application_url) is None:
            raise HTTPException(409, detail="Official application URL is unavailable")
        saved.status = "in_progress"
        db.commit()
        return {
            "scholarship_id": scholarship.id,
            "application_url": application_url,
            "automation_policy": version.data.get("automation_policy", "unknown"),
        }

    @router.get("/profile-values")
    def profile_values(
        response: Response,
        portal_origin: str = Query(min_length=8, max_length=500),
        scholarship_id: str = Query(min_length=1, max_length=36),
        db: Session = Depends(get_db),
    ) -> dict:
        _origin, _matches, context = _single_context(db, portal_origin, scholarship_id)
        if context is None or _automation_blocked(context):
            raise HTTPException(409, detail="Scholarship portal context is not uniquely supported")
        profile = db.get(LocalProfile, 1)
        if profile is None:
            raise HTTPException(503, detail="Local profile is unavailable")
        response.headers["Cache-Control"] = "no-store"
        values = []
        for name, spec in FIELDS.items():
            value = profile.data.get(name)
            if value is None or is_unknown(value):
                continue
            values.append({
                "name": name,
                "label": spec["label"],
                "value": value,
                "sensitive": spec["sensitive"],
            })
        return {"scholarship_id": scholarship_id, "fields": values}

    @router.get("/documents")
    def document_metadata(
        response: Response,
        portal_origin: str = Query(min_length=8, max_length=500),
        scholarship_id: str = Query(min_length=1, max_length=36),
        db: Session = Depends(get_db),
    ) -> dict:
        """Return metadata only after the same active application check."""

        _origin, _matches, context = _single_context(db, portal_origin, scholarship_id)
        if context is None or _automation_blocked(context):
            raise HTTPException(409, detail="Scholarship portal context is not uniquely supported")
        rows = db.query(Document).order_by(Document.document_type).all()
        essays = db.query(Essay).order_by(Essay.title, Essay.id).all()
        response.headers["Cache-Control"] = "no-store"
        return {"items": [
            {
                "document_type": row.document_type,
                "original_name": row.original_name,
                "size_bytes": row.size_bytes,
            }
            for row in rows
        ], "essays": [
            {"id": row.id, "title": row.title, "word_count": row.word_count}
            for row in essays
        ]}

    @router.get("/documents/{document_type}/content")
    def document_content(
        document_type: Literal["resume", "transcript"],
        portal_origin: str = Query(min_length=8, max_length=500),
        scholarship_id: str = Query(min_length=1, max_length=36),
        db: Session = Depends(get_db),
    ) -> Response:
        """Decrypt only for an explicit extension attachment request."""

        _origin, _matches, context = _single_context(db, portal_origin, scholarship_id)
        if context is None or _automation_blocked(context):
            raise HTTPException(409, detail="Scholarship portal context is not uniquely supported")
        try:
            metadata, plaintext = decrypt_document(database, secret_store, document_type)
        except DocumentVaultError as error:
            raise HTTPException(409, detail=str(error)) from error
        return Response(
            content=plaintext,
            media_type="application/pdf",
            headers={
                "Cache-Control": "no-store",
                "X-PathAid-Filename": quote(metadata.original_name, safe=""),
            },
        )

    @router.get("/essays/{essay_id}/content")
    def essay_content(
        essay_id: str,
        portal_origin: str = Query(min_length=8, max_length=500),
        scholarship_id: str = Query(min_length=1, max_length=36),
        db: Session = Depends(get_db),
    ) -> Response:
        """Release one chosen student-written essay after an explicit click."""

        _origin, _matches, context = _single_context(db, portal_origin, scholarship_id)
        if context is None or _automation_blocked(context):
            raise HTTPException(409, detail="Scholarship portal context is not uniquely supported")
        essay = db.get(Essay, essay_id)
        if essay is None:
            raise HTTPException(404, detail="Essay not found")
        safe_title = re.sub(r"[^a-zA-Z0-9._ -]+", "", essay.title).strip() or "essay"
        return Response(
            content=essay.text.encode("utf-8"), media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "X-PathAid-Filename": quote(f"{safe_title[:180]}.txt", safe=""),
            },
        )

    @router.get("/mappings")
    def learned_mappings(
        response: Response,
        portal_origin: str = Query(min_length=8, max_length=500),
        scholarship_id: str = Query(min_length=1, max_length=36),
        form_signature: str = Query(min_length=64, max_length=64),
        db: Session = Depends(get_db),
    ) -> dict:
        """Return value-free corrections for one validated portal form shape."""

        origin, _matches, context = _single_context(db, portal_origin, scholarship_id)
        if context is None or _automation_blocked(context):
            raise HTTPException(409, detail="Scholarship portal context is not uniquely supported")
        if not SIGNATURE_PATTERN.fullmatch(form_signature):
            raise HTTPException(422, detail="Invalid form signature")
        rows = db.scalars(
            select(PortalMapping)
            .where(
                PortalMapping.portal_origin == origin,
                PortalMapping.form_signature == form_signature,
            )
            .order_by(PortalMapping.field_signature)
        ).all()
        response.headers["Cache-Control"] = "no-store"
        return {
            "form_signature": form_signature,
            "mappings": [
                {"field_signature": row.field_signature, "profile_field": row.profile_field}
                for row in rows
            ],
        }

    @router.put("/mappings")
    def remember_mappings(payload: PortalMappingBatch, db: Session = Depends(get_db)) -> dict:
        """Upsert reviewed corrections while storing no profile or form values."""

        origin, _matches, context = _single_context(db, payload.portal_origin, payload.scholarship_id)
        if context is None or _automation_blocked(context):
            raise HTTPException(409, detail="Scholarship portal context is not uniquely supported")
        field_signatures = [item.field_signature for item in payload.mappings]
        if len(field_signatures) != len(set(field_signatures)):
            raise HTTPException(422, detail="Duplicate field signature")
        if any(item.profile_field is not None and item.profile_field not in FIELDS for item in payload.mappings):
            raise HTTPException(422, detail="Unknown profile field")
        for item in payload.mappings:
            row = db.scalar(select(PortalMapping).where(
                PortalMapping.portal_origin == origin,
                PortalMapping.form_signature == payload.form_signature,
                PortalMapping.field_signature == item.field_signature,
            ))
            if item.profile_field is None:
                if row is not None:
                    db.delete(row)
            elif row is None:
                db.add(PortalMapping(
                    id=str(uuid4()), portal_origin=origin,
                    form_signature=payload.form_signature,
                    field_signature=item.field_signature,
                    profile_field=item.profile_field,
                ))
            else:
                row.profile_field = item.profile_field
        db.commit()
        return {"saved": len(payload.mappings)}

    return router
