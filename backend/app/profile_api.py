"""Unauthenticated loopback API for the singleton local student profile."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import Database
from .matching import ScholarshipCandidate, evaluate_candidates
from .models import (
    AppSetting, LocalProfile, ProfileExperience, SavedScholarship, Scholarship,
    ScholarshipVersion, SkippedScholarship, SourceSnapshot,
)
from .scholarship_activation import material_fingerprint
from .profile_fields import FIELDS, MATCH_FIELDS, SECTIONS, ProfileValidationError, completeness, validate_profile_patch
from .source_registry import deactivate_prior_school_scopes


class ExperienceInput(BaseModel):
    """Validated replacement representation for one structured experience."""

    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    kind: Literal["activity", "employment", "volunteering", "membership", "leadership", "honor"]
    organization: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    start_date: date | None = None
    end_date: date | None = None
    current: bool = False
    hours: float | None = Field(default=None, ge=0, le=1_000_000)
    leadership: bool = False
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(UUID(value))
        except ValueError as error:
            raise ValueError("Invalid experience identifier") from error

    @field_validator("organization", "title", "description")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be empty")
        return cleaned

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        tags = [tag.strip().casefold() for tag in value]
        if any(not tag or len(tag) > 60 for tag in tags) or len(tags) != len(set(tags)):
            raise ValueError("Tags must be unique non-empty values")
        return sorted(tags)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.current and self.end_date is not None:
            raise ValueError("Current experiences cannot have an end date")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Experience end date cannot precede start date")
        return self


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict = Field(default_factory=dict)
    experiences: list[ExperienceInput] | None = Field(default=None, max_length=100)


def _experience_payload(item: ProfileExperience) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "organization": item.organization,
        "title": item.title,
        "description": item.description,
        "start_date": item.start_date.isoformat() if item.start_date else None,
        "end_date": item.end_date.isoformat() if item.end_date else None,
        "current": item.current,
        "hours": item.hours,
        "leadership": item.leadership,
        "tags": item.tags,
    }


def _profile_payload(profile: LocalProfile, *, school_changed: bool = False) -> dict:
    return {
        "fields": profile.data,
        "experiences": [_experience_payload(item) for item in profile.experiences],
        "completeness": completeness(profile.data),
        "school_revision": profile.school_revision,
        "school_changed": school_changed,
    }


def _deadline(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _current_availability(data: dict, *, now: datetime | None = None) -> str:
    """Derive current availability so old open labels expire without Gemini."""

    stated = data["application_availability"]
    if stated != "open":
        return stated
    raw = data.get("application_deadline")
    if not raw:
        return "verified_open"
    moment = now or datetime.now(timezone.utc)
    try:
        zone = ZoneInfo(data["deadline_timezone"]) if data.get("deadline_timezone") else timezone.utc
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    deadline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if "T" not in raw:
        expired = moment.astimezone(zone).date() > deadline.date()
    else:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=zone)
        expired = moment.astimezone(deadline.tzinfo) >= deadline
    return "expired" if expired else "verified_open"


def _match_payload(result, sponsor: str) -> dict:
    data = result.candidate
    return {
        "scholarship_id": data.scholarship_id,
        "name": data.name,
        "sponsor": sponsor,
        "award": getattr(data, "award", None),
        "deadline": data.deadline,
        "match_label": result.eligibility.label.value,
        "key_reasons": [item.reason for item in result.eligibility.criteria],
        "unknown_fields": list(result.eligibility.unknown_fields),
    }


def create_profile_router(database: Database) -> APIRouter:
    """Build profile routes bound to the application-owned local database."""

    router = APIRouter(prefix="/api", tags=["local-profile"])

    def get_db():
        yield from database.session()

    def singleton(db: Session) -> LocalProfile:
        profile = db.get(LocalProfile, 1)
        if profile is None:  # migration invariant, reported without recreation
            raise HTTPException(503, detail="Local profile is unavailable")
        return profile

    @router.get("/profile-fields")
    def profile_fields() -> dict:
        return {"fields": FIELDS, "sections": SECTIONS, "unknown_answer": {"status": "unknown"}}

    @router.get("/profile")
    def get_profile(db: Session = Depends(get_db)) -> dict:
        return _profile_payload(singleton(db))

    @router.patch("/profile")
    def patch_profile(body: ProfilePatch, db: Session = Depends(get_db)) -> dict:
        profile = singleton(db)
        old_school = (profile.data.get("school_id"), profile.data.get("school"))
        try:
            profile.data = validate_profile_patch(body.fields, profile.data)
        except ProfileValidationError as error:
            raise HTTPException(422, detail={"field": error.field_name, "message": "Invalid profile answer"}) from error
        # A free-text school edit is no longer authoritative NCES selection.
        # Keep matching data, but require institution selection again before a
        # new school-owned crawl scope can be proposed.
        if "school" in body.fields and "school_id" not in body.fields and profile.data.get("school") != old_school[1]:
            profile.data = {name: value for name, value in profile.data.items() if name != "school_id"}
        new_school = (profile.data.get("school_id"), profile.data.get("school"))
        school_changed = bool({"school", "school_id"}.intersection(body.fields)) and new_school != old_school
        if school_changed:
            profile.school_revision += 1
            deactivate_prior_school_scopes(db, current_revision=profile.school_revision)
            setting = db.get(AppSetting, "needs_school_source_onboarding")
            if setting is None:
                db.add(AppSetting(key="needs_school_source_onboarding", value="true"))
            else:
                setting.value = "true"
        if body.experiences is not None:
            db.execute(delete(ProfileExperience).where(ProfileExperience.profile_id == 1))
            for position, item in enumerate(body.experiences):
                db.add(ProfileExperience(
                    id=item.id or str(uuid4()),
                    profile_id=1,
                    position=position,
                    kind=item.kind,
                    organization=item.organization,
                    title=item.title,
                    description=item.description,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    current=item.current,
                    hours=item.hours,
                    leadership=item.leadership,
                    tags=item.tags,
                ))
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return _profile_payload(profile, school_changed=school_changed)

    @router.delete("/profile", status_code=204)
    def clear_profile(db: Session = Depends(get_db)) -> None:
        profile = singleton(db)
        profile.data = {}
        profile.school_revision += 1
        db.execute(delete(ProfileExperience).where(ProfileExperience.profile_id == 1))
        setting = db.get(AppSetting, "needs_school_source_onboarding")
        if setting is None:
            db.add(AppSetting(key="needs_school_source_onboarding", value="true"))
        else:
            setting.value = "true"
        db.commit()

    @router.get("/matches")
    def matches(db: Session = Depends(get_db)) -> dict:
        """Evaluate only deterministically activated scholarship versions."""

        profile = singleton(db)
        rows = db.execute(
            select(Scholarship, ScholarshipVersion, SourceSnapshot)
            .join(ScholarshipVersion, ScholarshipVersion.id == Scholarship.active_version_id)
            .join(SourceSnapshot, SourceSnapshot.id == ScholarshipVersion.source_snapshot_id)
            .where(Scholarship.status == "active")
            .order_by(Scholarship.id)
        ).all()
        candidates = []
        sponsors = {}
        awards = {}
        application_urls = {}
        application_processes = {}
        official_rules_urls = {}
        versions = {}
        for scholarship, version, snapshot in rows:
            data = version.data
            availability = _current_availability(data)
            candidate = ScholarshipCandidate(
                scholarship_id=scholarship.id, version_id=version.id, name=data["name"],
                hard_requirements=data["eligibility_tree"], requirements_complete=data["coverage_complete"],
                availability=availability, deadline=_deadline(data.get("application_deadline")),
                source_freshness=snapshot.acquired_at,
                selection_preferences=tuple(data.get("selection_factors", [])),
            )
            candidates.append(candidate)
            sponsors[scholarship.id] = urlsplit(scholarship.source_url).hostname or scholarship.source_url
            awards[scholarship.id] = data.get("assistance_amount")
            application_urls[scholarship.id] = data.get("application_url") or scholarship.source_url
            application_processes[scholarship.id] = data.get("application_process", "separate_application")
            official_rules_urls[scholarship.id] = data.get("official_rules_url")
            versions[scholarship.id] = version
        saved_states = {
            item.scholarship_id: item.status for item in db.scalars(select(SavedScholarship))
        }
        skipped = {
            item.scholarship_id: item.material_fingerprint for item in db.scalars(select(SkippedScholarship))
        }
        profile_inputs = dict(profile.data)
        profile_inputs["experiences"] = [_experience_payload(item) for item in profile.experiences]
        evaluated = evaluate_candidates(candidates, profile_inputs, MATCH_FIELDS)
        results = []
        automatically_considered = []
        sweepstakes = []
        not_matches = []
        for result in evaluated:
            scholarship_id = result.candidate.scholarship_id
            version = versions[scholarship_id]
            current_fingerprint = version.material_fingerprint or material_fingerprint(version.data)
            # A skip applies only while the exact material cycle remains active.
            if skipped.get(scholarship_id) == current_fingerprint:
                continue
            payload = _match_payload(result, sponsors[result.candidate.scholarship_id])
            payload["award"] = awards[result.candidate.scholarship_id]
            payload["application_url"] = application_urls[scholarship_id]
            payload["application_process"] = application_processes[scholarship_id]
            payload["official_rules_url"] = official_rules_urls[scholarship_id]
            payload["saved_status"] = saved_states.get(scholarship_id)
            if result.ranking_factors is not None:
                if application_processes[scholarship_id] == "automatically_considered":
                    automatically_considered.append(payload)
                elif application_processes[scholarship_id] == "sweepstakes":
                    sweepstakes.append(payload)
                else:
                    results.append(payload)
            elif result.eligibility.label.value == "Not a match":
                not_matches.append(payload)
        return {
            "results": results,
            "automatically_considered": automatically_considered,
            "sweepstakes": sweepstakes,
            "not_matches": not_matches,
            "profile_completeness": completeness(profile.data),
            "catalog_status": "ready" if rows else "awaiting_approved_sources",
        }

    return router

