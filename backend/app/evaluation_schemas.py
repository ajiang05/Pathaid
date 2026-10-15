"""Request and response contracts for source-backed program evaluation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRequest(BaseModel):
    """Temporary answers and assistance filters supplied for one evaluation."""

    model_config = ConfigDict(extra="forbid")
    answers: dict[str, Any] = Field(default_factory=dict)
    categories: list[str] = Field(default_factory=list)


class CriterionResponse(BaseModel):
    """One evaluated requirement and the reviewed evidence supporting it."""

    model_config = ConfigDict(extra="forbid")
    id: str
    field: str
    operator: str
    truth: str
    reason: str
    answerable: bool
    evidence: dict[str, str | None]


class MissingFieldResponse(BaseModel):
    """Question metadata for a missing answer that could change an outcome."""

    model_config = ConfigDict(extra="forbid")
    field: str
    question: str
    answer_type: str
    values: list[Any] | None = None
    sensitive: bool


class ProgramEvaluationResponse(BaseModel):
    """Deterministic result for one exact published program revision."""

    model_config = ConfigDict(extra="forbid")
    program_id: str
    revision_id: str
    name: str
    description: str
    categories: list[str]
    label: str
    truth: str
    criteria: list[CriterionResponse]
    missing_fields: list[MissingFieldResponse]
    unresolved_conditions: list[str]
    application_availability: str
    application_deadline: str | None
    deadline_timezone: str | None
    deadline_verification: str
    deadline_timezone_verification: str
    assistance_amount: str | None
    amount_verification: str
    award_cycle: str | None
    award_cycle_verification: str
    checklist: list[Any]
    checklist_verification: str
    selection_factors: list[Any]
    verified_at: datetime | None
    provider_url: str
    application_url: str | None
    sources: list[dict[str, Any]]
    coverage: dict[str, Any]
    template_explanation: str
    availability_section: str | None = None
    relevance: str | None = None
    ranking_factors: dict[str, str] = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    """All candidate outcomes plus the filters used to select candidates."""

    model_config = ConfigDict(extra="forbid")
    categories: list[str]
    results: list[ProgramEvaluationResponse]
