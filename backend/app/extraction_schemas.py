"""Strict data contract for AI-generated program requirement drafts.

These models describe proposals only. Passing this schema does not approve or
publish a program revision; later validation and human review remain required.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EXTRACTION_SCHEMA_VERSION = "1.0.0"
Category = Literal["scholarships", "grants", "food", "emergency", "housing"]
Operator = Literal["eq", "in", "contains", "gt", "gte", "lt", "lte"]
RuleValue: TypeAlias = str | int | float | bool | list[str]


class StrictModel(BaseModel):
    """Reject fields outside the reviewed extraction contract."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class EvidenceReference(StrictModel):
    """Identify the retained source text supporting one extracted claim."""

    snapshot_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class ConditionRule(StrictModel):
    """A proposed machine-answerable eligibility requirement."""

    type: Literal["condition"]
    field: str = Field(min_length=1)
    operator: Operator
    value: RuleValue
    evidence: EvidenceReference
    # False means the source may describe exceptions that were not represented.
    exceptions_complete: bool


class UnsupportedRule(StrictModel):
    """A mandatory requirement that the current evaluator cannot express."""

    type: Literal["unsupported"]
    description: str = Field(min_length=1)
    evidence: EvidenceReference


class RuleGroup(StrictModel):
    """Combine mandatory eligibility requirements with AND or OR semantics."""

    type: Literal["and", "or"]
    children: list["RuleNode"] = Field(min_length=1)


RuleNode: TypeAlias = Annotated[
    ConditionRule | UnsupportedRule | RuleGroup,
    Field(discriminator="type"),
]


class CoverageDraft(StrictModel):
    """Proposed geographic or institution coverage for catalog filtering."""

    national: bool
    states: list[str]
    institutions: list[str]


class ChecklistItem(StrictModel):
    """A material or action needed to submit an application."""

    label: str = Field(min_length=1)
    required: bool
    evidence: EvidenceReference


class SelectionFactor(StrictModel):
    """A preference that may affect selection but does not determine eligibility."""

    description: str = Field(min_length=1)
    evidence: EvidenceReference


class UnresolvedCondition(StrictModel):
    """Ambiguous or incomplete source language requiring human interpretation."""

    description: str = Field(min_length=1)
    evidence: EvidenceReference


class ExtractedProgramDraft(StrictModel):
    """Complete model output proposed for deterministic validation and review."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    categories: list[Category] = Field(min_length=1)
    coverage: CoverageDraft
    checklist: list[ChecklistItem]
    eligibility_tree: RuleNode
    # This is the model's proposal. Only an administrator can attest completeness.
    coverage_complete: bool
    award_cycle: str | None
    application_deadline: str | None
    deadline_timezone: str | None
    application_availability: Literal["open", "closed", "unknown"]
    assistance_amount: str | None
    selection_factors: list[SelectionFactor]
    application_url: str | None
    unresolved_conditions: list[UnresolvedCondition]

    @field_validator("categories")
    @classmethod
    def unique_categories(cls, categories: list[str]) -> list[str]:
        """Reject duplicate categories instead of silently normalizing output."""

        if len(categories) != len(set(categories)):
            raise ValueError("categories must be unique")
        return categories

    @model_validator(mode="after")
    def explain_incomplete_coverage(self) -> "ExtractedProgramDraft":
        """Require the model to state why its eligibility coverage is incomplete."""

        if not self.coverage_complete and not self.unresolved_conditions and not _has_unsupported(self.eligibility_tree):
            raise ValueError("incomplete coverage requires an unresolved or unsupported condition")
        return self


def _has_unsupported(rule: RuleNode) -> bool:
    """Return whether a proposed rule tree contains an unsupported condition."""

    if isinstance(rule, UnsupportedRule):
        return True
    if isinstance(rule, RuleGroup):
        return any(_has_unsupported(child) for child in rule.children)
    return False


# Resolve the recursive RuleGroup annotation before generating JSON Schema.
RuleGroup.model_rebuild()
ExtractedProgramDraft.model_rebuild()
