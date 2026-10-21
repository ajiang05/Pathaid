"""Validate and queue the launch catalog's unreviewed official source manifest."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import IngestionRun
from .orchestration import IngestionSubmission, create_ingestion_run
from .source_acquisition import WebSourceRequest


MANIFEST_VERSION = "1.0.0"
Category = Literal["scholarships", "grants", "food", "emergency", "housing"]
Scope = Literal["national", "state", "institutional"]


class IntakeModel(BaseModel):
    """Reject accidental fields in the review intake artifact."""

    model_config = ConfigDict(extra="forbid")


class IntakeEntry(IntakeModel):
    """One official page proposed for ingestion and human review."""

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=3, max_length=240)
    category: Category
    scope: Scope
    institution: str | None = Field(default=None, max_length=240)
    source_url: str = Field(max_length=2048)
    checked_at: date
    intake_status: Literal["candidate"] = "candidate"
    review_notes: str = Field(min_length=3, max_length=500)

    @field_validator("source_url")
    @classmethod
    def official_https_url(cls, value: str) -> str:
        """Require a direct HTTPS page with no embedded credentials or fragment."""

        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
            raise ValueError("source_url must be a direct public HTTPS URL")
        return value

    @model_validator(mode="after")
    def scope_matches_institution(self) -> "IntakeEntry":
        """Institutional records name their institution; broader records do not."""

        if self.scope == "institutional" and not self.institution:
            raise ValueError("institutional entries require institution")
        if self.scope != "institutional" and self.institution is not None:
            raise ValueError("only institutional entries may set institution")
        return self


class CatalogIntakeManifest(IntakeModel):
    """Versioned candidates that still require acquisition and human approval."""

    version: Literal["1.0.0"]
    prepared_at: date
    entries: list[IntakeEntry] = Field(min_length=10, max_length=20)

    @model_validator(mode="after")
    def launch_coverage(self) -> "CatalogIntakeManifest":
        """Enforce the agreed launch size and diversity before work is queued."""

        ids = [entry.id for entry in self.entries]
        urls = [entry.source_url for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("intake entry IDs must be unique")
        if len(urls) != len(set(urls)):
            raise ValueError("intake source URLs must be unique")
        scholarships = [entry for entry in self.entries if entry.category == "scholarships"]
        if len(scholarships) < 4:
            raise ValueError("launch intake requires at least four scholarships")
        if sum(entry.scope != "institutional" for entry in scholarships) < 2:
            raise ValueError("at least two scholarships must be available beyond one institution")
        represented = {entry.category for entry in self.entries}
        if not {"scholarships", "grants", "food", "emergency", "housing"}.issubset(represented):
            raise ValueError("launch intake must represent every MVP assistance category")
        return self


def load_manifest(path: Path) -> CatalogIntakeManifest:
    """Parse and fully validate one intake manifest."""

    return CatalogIntakeManifest.model_validate_json(path.read_text(encoding="utf-8"))


def manifest_summary(manifest: CatalogIntakeManifest) -> dict[str, object]:
    """Return a stable readiness summary suitable for CI and reviewers."""

    categories = Counter(entry.category for entry in manifest.entries)
    scopes = Counter(entry.scope for entry in manifest.entries)
    return {
        "version": manifest.version,
        "candidates": len(manifest.entries),
        "categories": dict(sorted(categories.items())),
        "scopes": dict(sorted(scopes.items())),
        "reviewed": 0,
        "published": 0,
    }


def queue_manifest(db: Session, manifest: CatalogIntakeManifest) -> dict[str, int]:
    """Idempotently queue candidates; ingestion still cannot publish them."""

    created = existing = 0
    for entry in manifest.entries:
        key = f"catalog-intake:{manifest.version}:{entry.id}"
        before = db.query(IngestionRun).filter_by(idempotency_key=key).first()
        create_ingestion_run(db, IngestionSubmission(key, WebSourceRequest(entry.source_url)))
        if before is None:
            created += 1
        else:
            existing += 1
    return {"created": created, "existing": existing}
def main() -> None:
    """Validate the manifest or explicitly queue it for the ingestion worker."""

    default_path = Path(__file__).parents[1] / "data" / "catalog_intake_v1.json"
    parser = argparse.ArgumentParser(description="Manage launch catalog intake candidates")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "queue"):
        child = subcommands.add_parser(command)
        child.add_argument("path", type=Path, nargs="?", default=default_path)
    arguments = parser.parse_args()
    manifest = load_manifest(arguments.path)
    if arguments.command == "validate":
        summary = manifest_summary(manifest)
        print(f"Validated {summary['candidates']} catalog candidates across {len(summary['categories'])} categories.")
        return
    with SessionLocal() as db:
        result = queue_manifest(db, manifest)
    print(f"Queued {result['created']} candidates; found {result['existing']} existing runs.")


if __name__ == "__main__":
    main()
