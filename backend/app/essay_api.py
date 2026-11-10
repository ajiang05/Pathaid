"""Loopback API for the local essay bank and optional Gemini analysis."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .database import Database
from .essay_recommendation import (
    EssayAnalysisProvider, EssayForAnalysis, GeminiEssayAnalysisProvider, local_recommendations,
)
from .models import AppSetting, Essay, EssayUse, Scholarship, ScholarshipVersion
from .secrets import GEMINI_API_KEY, SecretStore, SecretStoreError


FULL_TEXT_SETTING = "essay_full_text_analysis_enabled"
DATA_TIER_SETTING = "gemini_data_tier"
NOTICE_SETTING = "gemini_data_notice_acknowledged"


class EssayInput(BaseModel):
    """Validated student-authored essay fields accepted for create/update."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    original_prompt: str = Field(min_length=1, max_length=10_000)
    text: str = Field(min_length=1, max_length=100_000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    themes: list[str] = Field(default_factory=list, max_length=30)
    written_on: date

    @field_validator("title", "original_prompt", "text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("tags", "themes")
    @classmethod
    def clean_labels(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 80 for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("labels must be unique and no more than 80 characters")
        return cleaned


class EssayUseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scholarship_id: str | None = Field(default=None, max_length=36)
    scholarship_name: str = Field(min_length=1, max_length=240)
    destination_prompt: str = Field(min_length=1, max_length=10_000)


class RecommendationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_prompt: str = Field(min_length=1, max_length=10_000)
    word_limit: int | None = Field(default=None, ge=1, le=100_000)
    scholarship_id: str | None = Field(default=None, max_length=36)
    use_gemini: bool = False


class EssayAnalysisSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_text_analysis_enabled: bool
    data_tier: Literal["unpaid", "paid", "unknown"]
    notice_acknowledged: bool


def create_essay_router(
    database: Database,
    secret_store: SecretStore,
    provider_factory: Callable[[str], EssayAnalysisProvider] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/essays", tags=["essays"])
    provider_factory = provider_factory or (lambda key: GeminiEssayAnalysisProvider(key))

    @router.get("")
    def list_essays() -> dict:
        with database.sessions() as db:
            return {"items": [_essay_payload(row) for row in db.query(Essay).order_by(Essay.updated_at.desc()).all()]}

    @router.post("", status_code=201)
    def create_essay(payload: EssayInput) -> dict:
        row = Essay(id=str(uuid4()), **_essay_values(payload))
        with database.sessions.begin() as db:
            db.add(row)
            db.flush()
            return _essay_payload(row)

    @router.put("/items/{essay_id}")
    def update_essay(essay_id: str, payload: EssayInput) -> dict:
        with database.sessions.begin() as db:
            row = db.get(Essay, essay_id)
            if row is None:
                raise HTTPException(404, detail="Essay not found")
            for key, value in _essay_values(payload).items():
                setattr(row, key, value)
            db.flush()
            return _essay_payload(row)

    @router.delete("/items/{essay_id}", status_code=204)
    def delete_essay(essay_id: str) -> None:
        with database.sessions.begin() as db:
            row = db.get(Essay, essay_id)
            if row is None:
                raise HTTPException(404, detail="Essay not found")
            db.delete(row)

    @router.post("/items/{essay_id}/uses", status_code=201)
    def record_use(essay_id: str, payload: EssayUseInput) -> dict:
        with database.sessions.begin() as db:
            if db.get(Essay, essay_id) is None:
                raise HTTPException(404, detail="Essay not found")
            if payload.scholarship_id and db.get(Scholarship, payload.scholarship_id) is None:
                raise HTTPException(404, detail="Scholarship not found")
            row = EssayUse(
                id=str(uuid4()), essay_id=essay_id, scholarship_id=payload.scholarship_id,
                scholarship_name=payload.scholarship_name.strip(),
                destination_prompt=payload.destination_prompt.strip(), used_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.flush()
            return _use_payload(row)

    @router.get("/analysis-settings")
    def analysis_settings() -> dict:
        with database.sessions() as db:
            result = _analysis_settings(db)
        try:
            result["gemini_key_configured"] = bool(secret_store.get(GEMINI_API_KEY))
        except SecretStoreError:
            result["gemini_key_configured"] = False
        return result

    @router.put("/analysis-settings")
    def update_analysis_settings(payload: EssayAnalysisSettingsInput) -> dict:
        with database.sessions.begin() as db:
            values = {
                FULL_TEXT_SETTING: str(payload.full_text_analysis_enabled).lower(),
                DATA_TIER_SETTING: payload.data_tier,
                NOTICE_SETTING: str(payload.notice_acknowledged).lower(),
            }
            for key, value in values.items():
                row = db.get(AppSetting, key)
                if row is None:
                    db.add(AppSetting(key=key, value=value))
                else:
                    row.value = value
        return analysis_settings()

    @router.post("/recommendations")
    def recommendations(payload: RecommendationInput) -> dict:
        with database.sessions() as db:
            essays = db.query(Essay).order_by(Essay.id).all()
            settings = _analysis_settings(db)
            policy = _scholarship_ai_policy(db, payload.scholarship_id)
            local = local_recommendations(essays, payload.destination_prompt, payload.word_limit)
            provider_essays = [
                EssayForAnalysis(
                    id=row.id, title=row.title, original_prompt=row.original_prompt, text=row.text,
                    tags=tuple(row.tags), themes=tuple(row.themes), word_count=row.word_count,
                ) for row in essays
            ]
        result = {
            "destination_prompt": payload.destination_prompt,
            "word_limit": payload.word_limit,
            "source": "local",
            "ai_policy": policy,
            "items": local,
            "warning": None,
        }
        if not payload.use_gemini:
            return result
        if policy == "blocked":
            result["warning"] = "Official rules prohibit AI assistance; Gemini analysis was not used."
            return result
        if not settings["full_text_analysis_enabled"] or not settings["notice_acknowledged"]:
            result["warning"] = "Enable full-text analysis and acknowledge the Gemini data notice first."
            return result
        if settings["data_tier"] == "unknown":
            result["warning"] = "Select the configured Gemini account tier before sending full essay text."
            return result
        try:
            api_key = secret_store.get(GEMINI_API_KEY)
        except SecretStoreError:
            api_key = None
        if not api_key:
            result["warning"] = "Gemini is not configured; local recommendations are shown."
            return result
        try:
            analysis = provider_factory(api_key).analyze(provider_essays, payload.destination_prompt, payload.word_limit)
        except Exception:
            # Provider errors are deliberately collapsed: raw responses and full
            # essay text must never enter API errors or application logs.
            result["warning"] = "Gemini analysis is unavailable; local recommendations are shown."
            return result
        by_id = {item.essay_id: item for item in analysis.rankings}
        result["source"] = "gemini"
        for item in result["items"]:
            provider_item = by_id.get(item["essay_id"])
            if provider_item:
                item["rationale"] = provider_item.rationale
                item["mismatches"] = [mismatch.model_dump() for mismatch in provider_item.mismatches]
        result["items"].sort(key=lambda item: list(by_id).index(item["essay_id"]) if item["essay_id"] in by_id else len(by_id))
        return result

    return router


def _essay_values(payload: EssayInput) -> dict:
    return {
        "title": payload.title, "original_prompt": payload.original_prompt, "text": payload.text,
        "tags": payload.tags, "themes": payload.themes,
        "word_count": len(payload.text.split()), "written_on": payload.written_on,
    }


def _essay_payload(row: Essay) -> dict:
    return {
        "id": row.id, "title": row.title, "original_prompt": row.original_prompt, "text": row.text,
        "tags": row.tags, "themes": row.themes, "word_count": row.word_count,
        "written_on": row.written_on.isoformat(),
        "uses": [_use_payload(use) for use in row.uses],
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _use_payload(row: EssayUse) -> dict:
    return {
        "id": row.id, "scholarship_id": row.scholarship_id, "scholarship_name": row.scholarship_name,
        "destination_prompt": row.destination_prompt, "used_at": row.used_at.isoformat(),
    }


def _analysis_settings(db) -> dict:
    values = {row.key: row.value for row in db.query(AppSetting).filter(AppSetting.key.in_([
        FULL_TEXT_SETTING, DATA_TIER_SETTING, NOTICE_SETTING,
    ])).all()}
    tier = values.get(DATA_TIER_SETTING, "unknown")
    notices = {
        "unpaid": (
            "Full essay text and the destination prompt are sent to Gemini. Under Google's current "
            "Gemini API terms, unpaid-service content and responses may be used to improve products "
            "and may be reviewed by humans; do not send sensitive or confidential information."
        ),
        "paid": (
            "Full essay text and the destination prompt are sent to Gemini. Under Google's current "
            "Gemini API terms, paid-service prompts and responses are not used to improve its products."
        ),
        "unknown": (
            "Full essay text and the destination prompt are sent to Gemini. Confirm whether the configured "
            "project is on Google's paid or unpaid service before enabling analysis."
        ),
    }
    return {
        "full_text_analysis_enabled": values.get(FULL_TEXT_SETTING) == "true",
        "data_tier": tier,
        "notice_acknowledged": values.get(NOTICE_SETTING) == "true",
        "notice": notices[tier],
    }


def _scholarship_ai_policy(db, scholarship_id: str | None) -> str:
    if not scholarship_id:
        return "unknown"
    scholarship = db.get(Scholarship, scholarship_id)
    if scholarship is None or not scholarship.active_version_id:
        raise HTTPException(404, detail="Scholarship not found")
    version = db.get(ScholarshipVersion, scholarship.active_version_id)
    return str((version.data if version else {}).get("ai_assistance_policy", "unknown"))
