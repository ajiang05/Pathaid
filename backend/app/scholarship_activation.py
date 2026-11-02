"""Deterministic activation of validated extraction results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Callable
from uuid import uuid4

from sqlalchemy import select

from .database import Database
from .extraction import ExtractionResult
from .extraction_validation import DraftValidationResult, validate_extracted_draft
from .models import ExtractionActivationAttempt, Scholarship, ScholarshipVersion, SourceSnapshot
from .source_registry import RegistryError


@dataclass(frozen=True)
class ActivationResult:
    """Safe activation outcome returned to local orchestration."""

    status: str
    scholarship_id: str | None
    version_id: str | None
    validation: DraftValidationResult


def _finding_payload(validation: DraftValidationResult) -> list[dict[str, str]]:
    return [
        {"code": item.code, "path": item.path, "message": item.message, "severity": item.severity}
        for item in validation.findings
    ]


def _draft_payload(result: ExtractionResult) -> dict:
    return result.draft.model_dump(mode="json")


def _draft_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def activate_validated_extraction(
    database: Database,
    source_snapshot_id: str,
    extraction: ExtractionResult,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> ActivationResult:
    """Validate one extraction and atomically advance only a valid version."""

    with database.sessions() as db:
        snapshot = db.get(SourceSnapshot, source_snapshot_id)
        if snapshot is None:
            raise RegistryError("snapshot_not_found", "Source snapshot not found.")
        snapshot_input = SimpleNamespace(id=snapshot.id, source_text=snapshot.normalized_text)
        source_url = snapshot.canonical_url

    attempted_at = now()
    validation = validate_extracted_draft(extraction.draft, snapshot_input, as_of=attempted_at)
    draft = _draft_payload(extraction)
    findings = _finding_payload(validation)

    with database.sessions.begin() as db:
        scholarship = db.scalar(select(Scholarship).where(Scholarship.source_url == source_url))
        if not validation.is_valid:
            db.add(ExtractionActivationAttempt(
                id=str(uuid4()), source_snapshot_id=source_snapshot_id,
                scholarship_id=scholarship.id if scholarship else None,
                activated_version_id=None, status="validation_failed", draft=draft,
                findings=findings, extraction_model=extraction.model,
                prompt_version=extraction.prompt_version, schema_version=extraction.schema_version,
                attempted_at=attempted_at,
            ))
            return ActivationResult("validation_failed", scholarship.id if scholarship else None, None, validation)

        if scholarship is None:
            scholarship = Scholarship(id=str(uuid4()), source_url=source_url, active_version_id=None, status="active")
            db.add(scholarship)
            db.flush()

        digest = _draft_hash(draft)
        version = db.scalar(
            select(ScholarshipVersion).where(
                ScholarshipVersion.scholarship_id == scholarship.id,
                ScholarshipVersion.source_snapshot_id == source_snapshot_id,
                ScholarshipVersion.draft_hash == digest,
            )
        )
        status = "unchanged" if version is not None else "activated"
        if version is None:
            version = ScholarshipVersion(
                id=str(uuid4()), scholarship_id=scholarship.id,
                source_snapshot_id=source_snapshot_id, draft_hash=digest,
                data=draft, validation_findings=findings,
                extraction_model=extraction.model, prompt_version=extraction.prompt_version,
                schema_version=extraction.schema_version,
                provider_request_id=extraction.request_id,
                input_tokens=extraction.usage.input_tokens,
                output_tokens=extraction.usage.output_tokens,
                total_tokens=extraction.usage.total_tokens,
                activated_at=attempted_at,
            )
            db.add(version)
            db.flush()

        # Pointer advancement and immutable inserts share one transaction, so
        # readers never observe a partially activated scholarship.
        scholarship.active_version_id = version.id
        scholarship.status = "active"
        db.add(ExtractionActivationAttempt(
            id=str(uuid4()), source_snapshot_id=source_snapshot_id,
            scholarship_id=scholarship.id, activated_version_id=version.id,
            status=status, draft=draft, findings=findings,
            extraction_model=extraction.model, prompt_version=extraction.prompt_version,
            schema_version=extraction.schema_version, attempted_at=attempted_at,
        ))
        return ActivationResult(status, scholarship.id, version.id, validation)
