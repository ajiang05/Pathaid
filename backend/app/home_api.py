"""Operational summary for the local single-user home screen."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from .database import Database
from .models import DiscoveryJob, LocalProfile, Scholarship, SourceScope
from .profile_fields import completeness
from .secrets import GEMINI_API_KEY, SecretStore, SecretStoreError


def create_home_router(database: Database, secret_store: SecretStore) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["home"])

    @router.get("/home-summary")
    def home_summary() -> dict:
        now = datetime.now(timezone.utc)
        with database.sessions() as db:
            profile = db.get(LocalProfile, 1)
            source_counts = dict(db.execute(
                select(SourceScope.status, func.count()).group_by(SourceScope.status)
            ).all())
            policy_blocked = db.scalar(select(func.count()).select_from(SourceScope).where(
                SourceScope.policy_status == "blocked"
            )) or 0
            due_sources = db.scalar(select(func.count()).select_from(SourceScope).where(
                SourceScope.status == "active",
                SourceScope.policy_status == "allowed",
                or_(SourceScope.scan_requested_at.is_not(None), SourceScope.next_scan_at <= now),
            )) or 0
            active_scholarships = db.scalar(select(func.count()).select_from(Scholarship).where(
                Scholarship.status == "active"
            )) or 0
            latest_job = db.scalar(select(DiscoveryJob).order_by(
                DiscoveryJob.updated_at.desc(), DiscoveryJob.id
            ).limit(1))
            last_success = db.scalar(select(func.max(SourceScope.last_success_at)))
        alerts = []
        fields = profile.data if profile else {}
        if not fields.get("school_id"):
            alerts.append({"code": "school_missing", "message": "Select your current school to receive school-specific source suggestions.", "href": "/sources"})
        if not source_counts.get("active"):
            alerts.append({"code": "sources_missing", "message": "Confirm at least one official scholarship source.", "href": "/sources"})
        if policy_blocked:
            alerts.append({"code": "policy_blocked", "message": f"{policy_blocked} source(s) are blocked by an automation policy decision.", "href": "/sources"})
        if latest_job and latest_job.status == "failed":
            alerts.append({"code": "scan_failed", "message": "The latest discovery job failed safely; prior verified records were preserved.", "href": "/sources"})
        try:
            gemini_configured = bool(secret_store.get(GEMINI_API_KEY))
        except SecretStoreError:
            gemini_configured = False
        if not gemini_configured:
            alerts.append({"code": "gemini_missing", "message": "Add a Gemini key before changed sources can be extracted.", "href": "/settings"})
        return {
            "profile_completeness": completeness(fields),
            "active_sources": int(source_counts.get("active", 0)),
            "paused_sources": int(source_counts.get("paused", 0)),
            "due_sources": int(due_sources),
            "active_scholarships": int(active_scholarships),
            "last_success_at": last_success,
            "latest_job": None if latest_job is None else {
                "status": latest_job.status,
                "stage": latest_job.stage,
                "error_code": latest_job.last_error_code,
                "updated_at": latest_job.updated_at,
            },
            "alerts": alerts,
        }

    return router
