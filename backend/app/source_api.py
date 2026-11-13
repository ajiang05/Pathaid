"""Accountless loopback API for institutions, source scopes, and URL leads."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Database
from .models import AppSetting, DiscoveryExtractionArtifact, DiscoveryJob, Institution, LocalProfile, ManualLead, SourcePolicyAssessment, SourceScanRun, SourceScope
from .lead_verification import verify_manual_lead
from .source_registry import (
    RegistryError,
    confirm_scope,
    create_manual_lead,
    create_scope_proposal,
    deactivate_prior_school_scopes,
    pause_scope,
    request_scan,
    record_source_policy,
    resume_scope,
    search_institutions,
    update_scope,
)


class ScopeProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=240)
    ownership: Literal["school", "sponsor"]
    adapter: Literal["generic", "academicworks", "kaleidoscope"] = "generic"
    canonical_url: str = Field(min_length=1, max_length=2_000)
    allowed_path_prefix: str = Field(min_length=1, max_length=1_000)
    institution_unit_id: str | None = Field(default=None, max_length=12)
    max_depth: int = Field(default=1, ge=0, le=2)
    page_budget: int = Field(default=25, ge=1, le=100)
    requests_per_minute: int = Field(default=10, ge=1, le=60)
    scan_interval_hours: int = Field(default=24, ge=6, le=720)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A name is required")
        return value.strip()


class LeadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    url: str = Field(min_length=1, max_length=2_000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A title is required")
        return value.strip()


class LeadVerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    official_url: str = Field(min_length=1, max_length=2_000)


class SourcePolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["allowed", "blocked"]
    evidence_url: str | None = Field(default=None, max_length=2_000)
    evidence_excerpt: str | None = Field(default=None, max_length=2_000)


def _institution_payload(item: Institution) -> dict:
    return {
        "unit_id": item.unit_id, "name": item.name, "aliases": item.aliases,
        "city": item.city, "state": item.state, "website_url": item.website_url,
        "source": "NCES IPEDS", "source_year": item.source_year,
    }


def _school_source_suggestions(item: Institution) -> list[dict]:
    """Return inert same-host guesses that still require explicit confirmation."""

    if not item.website_url:
        return []
    parsed = urlsplit(item.website_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return []
    origin = f"https://{parsed.hostname}"
    return [
        {
            "name": f"{item.name} financial aid scholarships",
            "canonical_url": f"{origin}/financialaid/scholarships",
            "allowed_path_prefix": "/financialaid",
            "adapter": "generic",
        },
        {
            "name": f"{item.name} scholarship directory",
            "canonical_url": f"{origin}/scholarships",
            "allowed_path_prefix": "/scholarships",
            "adapter": "generic",
        },
    ]


def _scope_payload(item: SourceScope, db: Session | None = None) -> dict:
    payload = {
        "id": item.id, "name": item.name, "ownership": item.ownership, "adapter": item.adapter,
        "canonical_url": item.canonical_url, "hostname": item.hostname,
        "allowed_path_prefix": item.allowed_path_prefix, "institution_unit_id": item.institution_unit_id,
        "school_revision": item.school_revision, "status": item.status, "confirmed_at": item.confirmed_at,
        "max_depth": item.max_depth, "page_budget": item.page_budget,
        "requests_per_minute": item.requests_per_minute, "scan_interval_hours": item.scan_interval_hours,
        "policy_status": item.policy_status, "policy_checked_at": item.policy_checked_at,
        "last_attempt_at": item.last_attempt_at, "last_success_at": item.last_success_at,
        "last_content_change_at": item.last_content_change_at, "next_scan_at": item.next_scan_at,
        "scan_requested_at": item.scan_requested_at, "last_error_code": item.last_error_code,
    }
    if db is None:
        payload["scan_progress"] = None
        return payload
    job = db.scalar(
        select(DiscoveryJob)
        .where(DiscoveryJob.source_scope_id == item.id)
        .order_by(DiscoveryJob.created_at.desc(), DiscoveryJob.id.desc())
        .limit(1)
    )
    run = db.scalar(
        select(SourceScanRun)
        .where(SourceScanRun.source_scope_id == item.id)
        .order_by(SourceScanRun.started_at.desc(), SourceScanRun.id.desc())
        .limit(1)
    )
    artifact_counts = {}
    if job is not None:
        artifact_counts = dict(db.execute(
            select(DiscoveryExtractionArtifact.status, func.count())
            .where(DiscoveryExtractionArtifact.discovery_job_id == job.id)
            .group_by(DiscoveryExtractionArtifact.status)
        ).all())
    extraction_processed = sum(artifact_counts.values())
    extraction_succeeded = artifact_counts.get("extracted", 0) + artifact_counts.get("activated", 0)
    extraction_failed = artifact_counts.get("validation_failed", 0)
    extraction_skipped = artifact_counts.get("skipped", 0)
    payload["scan_progress"] = None if job is None and run is None else {
        "status": job.status if job is not None else run.status,
        "stage": job.stage if job is not None else "acquisition",
        "attempt": job.attempt_count if job is not None else 1,
        "max_attempts": job.max_attempts if job is not None else 1,
        "error_code": (job.last_error_code if job is not None else None) or (run.error_code if run is not None else None),
        "pages_attempted": run.pages_attempted if run is not None else 0,
        "snapshots_created": run.snapshots_created if run is not None else 0,
        "extraction_processed": extraction_processed,
        "extraction_succeeded": extraction_succeeded,
        "extraction_failed": extraction_failed,
        "extraction_skipped": extraction_skipped,
        "extraction_remaining": max((run.pages_attempted if run is not None else 0) - extraction_processed, 0),
        "started_at": run.started_at if run is not None else None,
        "finished_at": run.finished_at if run is not None else None,
        "updated_at": job.updated_at if job is not None else run.finished_at or run.started_at,
    }
    return payload


def _lead_payload(item: ManualLead) -> dict:
    return {
        "id": item.id, "title": item.title, "canonical_url": item.canonical_url,
        "hostname": item.hostname, "status": item.status, "official_url": item.official_url,
        "official_hostname": item.official_hostname, "last_attempt_at": item.last_attempt_at,
        "verified_at": item.verified_at, "last_error_code": item.last_error_code,
    }


def _policy_payload(item: SourcePolicyAssessment) -> dict:
    return {
        "id": item.id, "source_scope_id": item.source_scope_id, "outcome": item.outcome,
        "evidence_url": item.evidence_url, "evidence_excerpt": item.evidence_excerpt,
        "checked_at": item.checked_at,
    }


def create_source_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["source-registry"])

    def get_db():
        yield from database.session()

    def source_or_404(source_id: str, db: Session) -> SourceScope:
        item = db.get(SourceScope, source_id)
        if item is None:
            raise HTTPException(404, detail="Source not found")
        return item

    def registry_error(error: RegistryError) -> HTTPException:
        return HTTPException(422, detail={"code": error.code, "message": error.safe_message})

    @router.get("/institutions")
    def institutions(q: str = Query(min_length=2, max_length=100), db: Session = Depends(get_db)) -> list[dict]:
        return [_institution_payload(item) for item in search_institutions(db, q)]

    @router.post("/institutions/{unit_id}/select")
    def select_institution(unit_id: str, db: Session = Depends(get_db)) -> dict:
        institution = db.get(Institution, unit_id)
        profile = db.get(LocalProfile, 1)
        if institution is None:
            raise HTTPException(404, detail="Institution not found")
        if profile is None:
            raise HTTPException(503, detail="Local profile is unavailable")
        previous = profile.data.get("school_id")
        changed = previous != institution.unit_id
        fields = dict(profile.data)
        fields.update({"school_id": institution.unit_id, "school": institution.name, "school_city": institution.city, "school_state": institution.state})
        profile.data = fields
        if changed:
            profile.school_revision += 1
            deactivate_prior_school_scopes(db, current_revision=profile.school_revision)
            setting = db.get(AppSetting, "needs_school_source_onboarding")
            if setting is None:
                db.add(AppSetting(key="needs_school_source_onboarding", value="true"))
            else:
                setting.value = "true"
        db.commit()
        return {
            "institution": _institution_payload(institution),
            "school_revision": profile.school_revision,
            "changed": changed,
            "source_suggestions": _school_source_suggestions(institution),
        }

    @router.get("/sources")
    def list_sources(db: Session = Depends(get_db)) -> list[dict]:
        items = db.scalars(select(SourceScope).order_by(SourceScope.name, SourceScope.id)).all()
        return [_scope_payload(item, db) for item in items]

    @router.post("/sources", status_code=201)
    def propose_source(body: ScopeProposalInput, db: Session = Depends(get_db)) -> dict:
        try:
            item = create_scope_proposal(db, **body.model_dump())
            db.add(item)
            db.commit()
        except RegistryError as error:
            db.rollback()
            raise registry_error(error) from error
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, detail="That host and path are already registered") from error
        return _scope_payload(item, db)

    @router.patch("/sources/{source_id}")
    def edit_source(source_id: str, body: ScopeProposalInput, db: Session = Depends(get_db)) -> dict:
        item = source_or_404(source_id, db)
        try:
            update_scope(db, item, **body.model_dump())
            db.commit()
        except RegistryError as error:
            db.rollback()
            raise registry_error(error) from error
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, detail="That host and path are already registered") from error
        return _scope_payload(item, db)

    @router.post("/sources/{source_id}/confirm")
    def confirm(source_id: str, db: Session = Depends(get_db)) -> dict:
        item = source_or_404(source_id, db)
        try:
            confirm_scope(item)
        except RegistryError as error:
            raise registry_error(error) from error
        db.commit()
        return _scope_payload(item, db)

    @router.post("/sources/{source_id}/pause")
    def pause(source_id: str, db: Session = Depends(get_db)) -> dict:
        item = source_or_404(source_id, db)
        try:
            pause_scope(item)
        except RegistryError as error:
            raise registry_error(error) from error
        db.commit()
        return _scope_payload(item, db)

    @router.post("/sources/{source_id}/resume")
    def resume(source_id: str, db: Session = Depends(get_db)) -> dict:
        item = source_or_404(source_id, db)
        try:
            resume_scope(item)
        except RegistryError as error:
            raise registry_error(error) from error
        db.commit()
        return _scope_payload(item, db)

    @router.post("/sources/{source_id}/scan-now")
    def scan_now(source_id: str, db: Session = Depends(get_db)) -> dict:
        item = source_or_404(source_id, db)
        try:
            request_scan(item)
        except RegistryError as error:
            raise registry_error(error) from error
        db.commit()
        return _scope_payload(item, db)

    @router.get("/sources/{source_id}/policies")
    def policy_history(source_id: str, db: Session = Depends(get_db)) -> list[dict]:
        source_or_404(source_id, db)
        items = db.scalars(
            select(SourcePolicyAssessment)
            .where(SourcePolicyAssessment.source_scope_id == source_id)
            .order_by(SourcePolicyAssessment.checked_at.desc(), SourcePolicyAssessment.id.desc())
        ).all()
        return [_policy_payload(item) for item in items]

    @router.post("/sources/{source_id}/policy")
    def review_policy(source_id: str, body: SourcePolicyInput, db: Session = Depends(get_db)) -> dict:
        item = source_or_404(source_id, db)
        try:
            record_source_policy(db, item, **body.model_dump())
        except RegistryError as error:
            db.rollback()
            raise registry_error(error) from error
        db.commit()
        return _scope_payload(item, db)

    @router.get("/leads")
    def list_leads(db: Session = Depends(get_db)) -> list[dict]:
        items = db.scalars(select(ManualLead).order_by(ManualLead.title, ManualLead.id)).all()
        return [_lead_payload(item) for item in items]

    @router.post("/leads", status_code=201)
    def add_lead(body: LeadInput, db: Session = Depends(get_db)) -> dict:
        try:
            item = create_manual_lead(db, title=body.title, url=body.url)
            db.add(item)
            db.commit()
        except RegistryError as error:
            db.rollback()
            raise registry_error(error) from error
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, detail="That lead URL is already saved") from error
        return _lead_payload(item)

    @router.post("/leads/{lead_id}/verify")
    def verify_lead(lead_id: str, body: LeadVerificationInput) -> dict:
        # Network acquisition is handled outside a request transaction so a
        # slow sponsor cannot hold a SQLite write lock.
        try:
            item = verify_manual_lead(database, lead_id, body.official_url)
        except RegistryError as error:
            raise registry_error(error) from error
        return _lead_payload(item)

    return router
