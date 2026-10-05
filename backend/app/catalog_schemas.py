"""Public response schemas for reviewed program catalog records."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SourceReference(BaseModel):
    """Public provenance for a retained source without exposing its full body."""

    model_config = ConfigDict(extra="forbid")
    id: str
    source_url: str
    acquired_at: datetime
    acquisition_method: str


class ProgramSummary(BaseModel):
    """Fields needed to render and rank a program in a result list."""

    model_config = ConfigDict(extra="forbid")
    id: str
    revision_id: str
    slug: str
    name: str
    description: str
    categories: list[str]
    coverage: dict[str, Any]
    assistance_amount: str | None
    application_deadline: datetime | None
    deadline_timezone: str | None
    application_availability: str
    verified_at: datetime | None


class ProgramDetail(ProgramSummary):
    """Complete reviewed public data for one current program revision."""

    checklist: list[Any]
    eligibility_tree: dict[str, Any]
    coverage_complete: bool
    award_cycle: str | None
    selection_factors: list[Any]
    provider_url: str
    application_url: str | None
    sources: list[SourceReference]
