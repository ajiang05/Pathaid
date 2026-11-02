"""Local saved-scholarship and cycle-level skip API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import Database
from .models import SavedScholarship, Scholarship, ScholarshipVersion, SkippedScholarship, SourceSnapshot
from .profile_api import _current_availability
from .scholarship_activation import material_fingerprint


class SavedStateInput(BaseModel):
    """The deliberately small set of visible application states."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["not_started", "in_progress", "already_applied"]


def _active_record(db: Session, scholarship_id: str):
    """Resolve current facts while preserving one stable scholarship ID."""

    record = db.execute(
        select(Scholarship, ScholarshipVersion, SourceSnapshot)
        .join(ScholarshipVersion, ScholarshipVersion.id == Scholarship.active_version_id)
        .join(SourceSnapshot, SourceSnapshot.id == ScholarshipVersion.source_snapshot_id)
        .where(Scholarship.id == scholarship_id)
    ).one_or_none()
    if record is None:
        raise HTTPException(404, detail="Scholarship not found")
    return record


def _saved_payload(saved: SavedScholarship, scholarship: Scholarship, version: ScholarshipVersion, snapshot: SourceSnapshot) -> dict:
    """Return current facts rather than freezing a stale card at save time."""

    data = version.data
    return {
        "scholarship_id": scholarship.id,
        "status": saved.status,
        "name": data["name"],
        "sponsor": data.get("sponsor_name") or scholarship.source_url.split("/", 3)[2],
        "award": data.get("assistance_amount"),
        "deadline": data.get("application_deadline"),
        "application_url": data.get("application_url") or scholarship.source_url,
        "availability": _current_availability(data),
        "source_status": scholarship.status,
        "source_freshness": snapshot.acquired_at,
        "created_at": saved.created_at,
        "updated_at": saved.updated_at,
    }


def create_saved_router(database: Database) -> APIRouter:
    """Build idempotent tracker routes for the singleton local user."""

    router = APIRouter(prefix="/api", tags=["saved-scholarships"])

    def get_db():
        yield from database.session()

    @router.get("/saved-scholarships")
    def list_saved(db: Session = Depends(get_db)) -> dict:
        rows = db.execute(
            select(SavedScholarship, Scholarship, ScholarshipVersion, SourceSnapshot)
            .join(Scholarship, Scholarship.id == SavedScholarship.scholarship_id)
            .join(ScholarshipVersion, ScholarshipVersion.id == Scholarship.active_version_id)
            .join(SourceSnapshot, SourceSnapshot.id == ScholarshipVersion.source_snapshot_id)
            .order_by(SavedScholarship.updated_at.desc(), SavedScholarship.scholarship_id)
        ).all()
        return {"items": [_saved_payload(*row) for row in rows]}

    @router.put("/saved-scholarships/{scholarship_id}")
    def set_saved_state(
        scholarship_id: str,
        body: SavedStateInput,
        db: Session = Depends(get_db),
    ) -> dict:
        scholarship, version, snapshot = _active_record(db, scholarship_id)
        if version.data.get("application_process") == "automatically_considered":
            raise HTTPException(409, detail="Automatically considered scholarships do not have an application status")
        saved = db.get(SavedScholarship, scholarship_id)
        if saved is None:
            saved = SavedScholarship(scholarship_id=scholarship_id, status=body.status)
            db.add(saved)
        else:
            saved.status = body.status
            saved.updated_at = datetime.now(timezone.utc)
        # An explicit save/apply decision overrides a prior cycle-level skip.
        db.execute(delete(SkippedScholarship).where(SkippedScholarship.scholarship_id == scholarship_id))
        db.commit()
        db.refresh(saved)
        return _saved_payload(saved, scholarship, version, snapshot)

    @router.delete("/saved-scholarships/{scholarship_id}", status_code=204)
    def remove_saved(scholarship_id: str, db: Session = Depends(get_db)) -> Response:
        db.execute(delete(SavedScholarship).where(SavedScholarship.scholarship_id == scholarship_id))
        db.commit()
        return Response(status_code=204)

    @router.put("/scholarships/{scholarship_id}/skip")
    def skip_current_cycle(scholarship_id: str, db: Session = Depends(get_db)) -> dict:
        scholarship, version, _snapshot = _active_record(db, scholarship_id)
        fingerprint = version.material_fingerprint or material_fingerprint(version.data)
        skipped = db.get(SkippedScholarship, scholarship_id)
        if skipped is None:
            skipped = SkippedScholarship(
                scholarship_id=scholarship_id,
                material_fingerprint=fingerprint,
            )
            db.add(skipped)
        else:
            skipped.material_fingerprint = fingerprint
            skipped.skipped_at = datetime.now(timezone.utc)
        db.execute(delete(SavedScholarship).where(SavedScholarship.scholarship_id == scholarship.id))
        db.commit()
        return {"scholarship_id": scholarship_id, "status": "skipped_this_cycle"}

    return router
