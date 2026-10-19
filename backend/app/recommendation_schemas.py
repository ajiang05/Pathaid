"""Contracts for optional, grounded scholarship recommendation explanations."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    """Identify the evaluated revision and any unsaved follow-up answers."""

    model_config = ConfigDict(extra="forbid")
    revision_id: str = Field(min_length=1, max_length=36)
    answers: dict[str, Any] = Field(default_factory=dict)


class ModelRecommendationSelection(BaseModel):
    """Constrained model output that can only select server-supplied reasons."""

    model_config = ConfigDict(extra="forbid")
    emphasis: Literal["eligibility", "missing_information", "application_readiness"]
    criterion_ids: list[str] = Field(default_factory=list, max_length=3)
    unresolved_ids: list[str] = Field(default_factory=list, max_length=3)


class RecommendationResponse(BaseModel):
    """Safe explanation rendered by the server from reviewed facts."""

    model_config = ConfigDict(extra="forbid")
    program_id: str
    revision_id: str
    eligibility_label: str
    explanation: str
    criterion_ids: list[str]
    unresolved_ids: list[str]
    generated_by: Literal["template", "model_assisted"]
    fallback_reason: str | None = None
