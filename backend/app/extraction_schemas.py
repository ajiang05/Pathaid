"""Strict data contract for AI-generated program requirement drafts.

These models describe untrusted proposals only. Passing this schema does not
activate a scholarship; deterministic validation remains required.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EXTRACTION_SCHEMA_VERSION = "1.1.0"
Category = Literal["scholarships", "grants", "food", "emergency", "housing"]
Operator = Literal["eq", "in", "contains", "gt", "gte", "lt", "lte"]
RuleValue: TypeAlias = str | int | float | bool | list[str]


class StrictModel(BaseModel):
    """Reject fields outside the versioned extraction contract."""

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
    """Complete model output proposed for deterministic validation."""

    name: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1)
    categories: list[Category] = Field(min_length=1)
    coverage: CoverageDraft
    checklist: list[ChecklistItem]
    eligibility_tree: RuleNode
    # This remains an untrusted model claim until deterministic validation.
    coverage_complete: bool
    award_cycle: str | None = Field(max_length=120)
    application_deadline: str | None
    deadline_timezone: str | None = Field(max_length=80)
    application_availability: Literal["open", "closed", "unknown"]
    assistance_amount: str | None = Field(max_length=240)
    selection_factors: list[SelectionFactor]
    application_url: str | None
    # Existing stored 1.0 records safely default at read time. Every new 1.1
    # extraction must explicitly classify its application process.
    application_process: Literal["separate_application", "automatically_considered", "sweepstakes"]
    application_process_evidence: EvidenceReference | None
    official_rules_url: str | None
    official_rules_evidence: EvidenceReference | None
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

    @model_validator(mode="after")
    def require_process_evidence(self) -> "ExtractedProgramDraft":
        """Prevent special result sections from relying on an unsupported label."""

        if self.application_process != "separate_application" and self.application_process_evidence is None:
            raise ValueError("special application process requires evidence")
        if self.application_process == "sweepstakes" and (
            self.official_rules_url is None or self.official_rules_evidence is None
        ):
            raise ValueError("sweepstakes require an official rules URL and evidence")
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
