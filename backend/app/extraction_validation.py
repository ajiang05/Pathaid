"""Deterministic validation for evidence-backed extraction proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Mapping, Protocol

from .eligibility import RuleValidationError, validate_rule_tree
from .extraction_schemas import (
    ConditionRule,
    EvidenceReference,
    ExtractedProgramDraft,
    RuleGroup,
    RuleNode,
    UnsupportedRule,
)
from .profile_fields import FIELDS
from .source_acquisition import AcquisitionError, validate_source_url


class SnapshotForValidation(Protocol):
    """Minimum immutable snapshot data needed by the validator."""

    id: str
    source_text: str


@dataclass(frozen=True)
class ValidationFinding:
    """One safe, addressable problem for the ingestion workflow or reviewer."""

    code: str
    path: str
    message: str
    severity: Literal["error", "warning"]


@dataclass(frozen=True)
class DraftValidationResult:
    """Validation outcome without mutating or publishing the proposed draft."""

    draft: ExtractedProgramDraft
    findings: tuple[ValidationFinding, ...]

    @property
    def is_valid(self) -> bool:
        """Only error findings prevent the proposal from entering review."""

        return not any(finding.severity == "error" for finding in self.findings)


def validate_extracted_draft(
    draft: ExtractedProgramDraft,
    snapshot: SnapshotForValidation,
    field_registry: Mapping[str, Mapping] = FIELDS,
) -> DraftValidationResult:
    """Check rule semantics, evidence provenance, coverage, dates, and URLs."""

    findings: list[ValidationFinding] = []

    # The existing evaluator contract remains the source of truth for allowed
    # fields, operators, and operand types.
    try:
        validate_rule_tree(draft.eligibility_tree.model_dump(mode="python"), field_registry)
    except RuleValidationError as error:
        findings.append(_error("invalid_rule", "eligibility_tree", str(error)))

    for path, evidence in _evidence_references(draft):
        _validate_evidence(evidence, path, snapshot, findings)

    _validate_coverage(draft, field_registry, findings)
    _validate_deadline(draft, findings)
    _validate_application_url(draft, findings)

    if _has_unsupported(draft.eligibility_tree):
        findings.append(
            _warning(
                "unsupported_logic",
                "eligibility_tree",
                "At least one mandatory condition requires human interpretation.",
            )
        )
    if draft.application_deadline and not draft.deadline_timezone:
        findings.append(
            _warning(
                "missing_deadline_timezone",
                "deadline_timezone",
                "The source did not provide a named deadline timezone.",
            )
        )

    return DraftValidationResult(draft=draft, findings=tuple(findings))


def _evidence_references(draft: ExtractedProgramDraft):
    """Yield every evidence object with a stable path for review feedback."""

    yield from _rule_evidence(draft.eligibility_tree, "eligibility_tree")
    for index, item in enumerate(draft.checklist):
        yield f"checklist.{index}.evidence", item.evidence
    for index, item in enumerate(draft.selection_factors):
        yield f"selection_factors.{index}.evidence", item.evidence
    for index, item in enumerate(draft.unresolved_conditions):
        yield f"unresolved_conditions.{index}.evidence", item.evidence


def _rule_evidence(rule: RuleNode, path: str):
    """Walk the recursive eligibility tree and yield leaf evidence."""

    if isinstance(rule, (ConditionRule, UnsupportedRule)):
        yield f"{path}.evidence", rule.evidence
        return
    for index, child in enumerate(rule.children):
        yield from _rule_evidence(child, f"{path}.children.{index}")


def _validate_evidence(
    evidence: EvidenceReference,
    path: str,
    snapshot: SnapshotForValidation,
    findings: list[ValidationFinding],
) -> None:
    """Require evidence to identify and occur verbatim in the input snapshot."""

    if evidence.snapshot_id != snapshot.id:
        findings.append(_error("wrong_snapshot", f"{path}.snapshot_id", "Evidence references a different snapshot."))
    if evidence.excerpt not in snapshot.source_text:
        findings.append(_error("excerpt_not_found", f"{path}.excerpt", "Evidence does not occur in the source snapshot."))


def _validate_coverage(
    draft: ExtractedProgramDraft,
    field_registry: Mapping[str, Mapping],
    findings: list[ValidationFinding],
) -> None:
    """Check that coverage is useful and uses known state identifiers."""

    coverage = draft.coverage
    if not coverage.national and not coverage.states and not coverage.institutions:
        findings.append(_error("missing_coverage", "coverage", "Coverage must identify a national, state, or institution scope."))
    if len(coverage.states) != len(set(coverage.states)):
        findings.append(_error("duplicate_state", "coverage.states", "Coverage states must be unique."))
    if len(coverage.institutions) != len(set(coverage.institutions)):
        findings.append(_error("duplicate_institution", "coverage.institutions", "Coverage institutions must be unique."))
    known_states = set(field_registry.get("state", {}).get("values", []))
    if any(state not in known_states for state in coverage.states):
        findings.append(_error("invalid_state", "coverage.states", "Coverage contains an unsupported state identifier."))
    if any(not institution.strip() for institution in coverage.institutions):
        findings.append(_error("empty_institution", "coverage.institutions", "Coverage institutions cannot be blank."))


def _validate_deadline(draft: ExtractedProgramDraft, findings: list[ValidationFinding]) -> None:
    """Require a machine-readable ISO 8601 deadline when one is extracted."""

    if not draft.application_deadline:
        return
    try:
        datetime.fromisoformat(draft.application_deadline.replace("Z", "+00:00"))
    except ValueError:
        findings.append(_error("invalid_deadline", "application_deadline", "The deadline must be an ISO 8601 date or timestamp."))


def _validate_application_url(draft: ExtractedProgramDraft, findings: list[ValidationFinding]) -> None:
    """Apply the same public HTTP(S) URL policy used during acquisition."""

    if not draft.application_url:
        return
    try:
        validate_source_url(draft.application_url)
    except AcquisitionError:
        findings.append(_error("invalid_application_url", "application_url", "The application URL is not an allowed public URL."))


def _has_unsupported(rule: RuleNode) -> bool:
    """Return whether any mandatory condition needs reviewer interpretation."""

    if isinstance(rule, UnsupportedRule):
        return True
    if isinstance(rule, RuleGroup):
        return any(_has_unsupported(child) for child in rule.children)
    return False


def _error(code: str, path: str, message: str) -> ValidationFinding:
    """Construct a finding that blocks entry into review."""

    return ValidationFinding(code, path, message, "error")


def _warning(code: str, path: str, message: str) -> ValidationFinding:
    """Construct a finding that requires reviewer attention but preserves data."""

    return ValidationFinding(code, path, message, "warning")
