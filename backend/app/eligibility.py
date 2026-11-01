"""Pure deterministic scholarship eligibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from numbers import Real
from typing import Any, Mapping

from .profile_fields import is_unknown


MAX_TREE_DEPTH = 8
MAX_TREE_NODES = 200
COMPARISON_OPERATORS = {
    "eq", "in", "contains", "gt", "gte", "lt", "lte",
    "before", "on_or_before", "after", "on_or_after", "experience_any",
}
NUMERIC_OPERATORS = {"gt", "gte", "lt", "lte"}
DATE_OPERATORS = {"before", "on_or_before", "after", "on_or_after"}


class RuleValidationError(ValueError):
    """Raised when a hard-requirement tree is malformed or unsafe."""


class TruthValue(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    # Compatibility aliases keep retained extraction benchmarks readable.
    TRUE = "pass"
    FALSE = "fail"


class EligibilityLabel(str, Enum):
    STRONG = "Strong match"
    POSSIBLE = "Possible match"
    NOT_MATCH = "Not a match"


@dataclass(frozen=True)
class CriterionResult:
    field: str
    operator: str
    truth: TruthValue
    evidence: Mapping[str, str]
    reason: str
    answerable: bool = True


@dataclass
class NodeResult:
    truth: TruthValue
    criteria: list[CriterionResult] = field(default_factory=list)
    missing_fields: set[str] = field(default_factory=set)
    unknown_fields: set[str] = field(default_factory=set)
    unresolved_conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EligibilityResult:
    scholarship_version_id: str
    label: EligibilityLabel
    truth: TruthValue
    criteria: tuple[CriterionResult, ...]
    missing_fields: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]

    @property
    def revision_id(self) -> str:
        """Compatibility alias for retained offline tooling."""

        return self.scholarship_version_id


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _require_keys(node: Mapping[str, Any], required: set[str]) -> None:
    missing = required.difference(node)
    if missing:
        raise RuleValidationError(f"Rule is missing required keys: {', '.join(sorted(missing))}")


def _validate_evidence(evidence: Any) -> None:
    if not isinstance(evidence, Mapping):
        raise RuleValidationError("Rule evidence must be an object")
    for key in ("snapshot_id", "excerpt"):
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            raise RuleValidationError(f"Rule evidence requires {key}")


def _parse_date_operand(value: Any) -> date:
    if not isinstance(value, str):
        raise RuleValidationError("Date operators require an ISO date operand")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise RuleValidationError("Date operators require an ISO date operand") from error


def _validate_experience_operand(value: Any) -> None:
    if not isinstance(value, Mapping) or not value:
        raise RuleValidationError("experience_any requires a non-empty object")
    allowed = {"kind", "leadership", "organization_contains", "title_contains", "tags_any", "minimum_hours"}
    if set(value).difference(allowed):
        raise RuleValidationError("experience_any contains an unknown criterion")
    if "kind" in value and value["kind"] not in {"activity", "employment", "volunteering", "membership", "leadership", "honor"}:
        raise RuleValidationError("experience_any has an invalid kind")
    if "leadership" in value and not isinstance(value["leadership"], bool):
        raise RuleValidationError("experience_any leadership must be boolean")
    for name in ("organization_contains", "title_contains"):
        if name in value and (not isinstance(value[name], str) or not value[name].strip()):
            raise RuleValidationError(f"experience_any {name} must be text")
    if "tags_any" in value and (not isinstance(value["tags_any"], list) or not value["tags_any"] or any(not isinstance(tag, str) for tag in value["tags_any"])):
        raise RuleValidationError("experience_any tags_any must be a non-empty text list")
    if "minimum_hours" in value and (not _is_number(value["minimum_hours"]) or value["minimum_hours"] < 0):
        raise RuleValidationError("experience_any minimum_hours must be nonnegative")


def _validate_operand(field_spec: Mapping[str, Any], operator: str, operand: Any) -> None:
    field_type = field_spec.get("type")
    allowed_values = field_spec.get("values")
    if operator in NUMERIC_OPERATORS:
        if field_type not in {"integer", "number"} or not _is_number(operand):
            raise RuleValidationError("Numeric operators require a numeric field and operand")
    elif operator in DATE_OPERATORS:
        if field_type not in {"date", "month"}:
            raise RuleValidationError("Date operators require a date or month field")
        _parse_date_operand(f"{operand}-01" if field_type == "month" and isinstance(operand, str) and len(operand) == 7 else operand)
    elif operator == "in":
        if not isinstance(operand, list) or not operand:
            raise RuleValidationError("The in operator requires a non-empty list")
        if field_type == "choice" and allowed_values is not None and any(value not in allowed_values for value in operand):
            raise RuleValidationError("Choice operands must use declared profile values")
    elif operator == "contains":
        if field_type != "multi_choice":
            raise RuleValidationError("The contains operator requires a multi-choice field")
        if allowed_values is not None and operand not in allowed_values:
            raise RuleValidationError("Multi-choice operands must use declared profile values")
    elif operator == "experience_any":
        if field_type != "experience_list":
            raise RuleValidationError("experience_any requires the experiences field")
        _validate_experience_operand(operand)
    elif operator == "eq":
        if field_type == "boolean" and not isinstance(operand, bool):
            raise RuleValidationError("Boolean equality requires a boolean operand")
        if field_type in {"integer", "number"} and not _is_number(operand):
            raise RuleValidationError("Numeric equality requires a numeric operand")
        if field_type == "choice" and allowed_values is not None and operand not in allowed_values:
            raise RuleValidationError("Choice operands must use declared profile values")


def validate_rule_tree(rule: Mapping[str, Any], field_registry: Mapping[str, Mapping[str, Any]], *, max_depth: int = MAX_TREE_DEPTH, max_nodes: int = MAX_TREE_NODES) -> None:
    """Validate hard requirements before any student result is produced."""

    node_count = 0

    def visit(node: Mapping[str, Any], depth: int) -> None:
        nonlocal node_count
        if not isinstance(node, Mapping):
            raise RuleValidationError("Every rule node must be an object")
        node_count += 1
        if node_count > max_nodes:
            raise RuleValidationError("Rule tree contains too many nodes")
        if depth > max_depth:
            raise RuleValidationError("Rule tree is too deeply nested")
        node_type = node.get("type")
        if node_type in {"and", "or"}:
            _require_keys(node, {"children"})
            if not isinstance(node["children"], list) or not node["children"]:
                raise RuleValidationError("Rule groups must contain at least one child")
            for child in node["children"]:
                visit(child, depth + 1)
            return
        if node_type == "unsupported":
            _require_keys(node, {"description", "evidence"})
            _validate_evidence(node["evidence"])
            if not isinstance(node["description"], str) or not node["description"].strip():
                raise RuleValidationError("Unsupported conditions need a description")
            return
        if node_type != "condition":
            raise RuleValidationError(f"Unknown rule node type: {node_type!r}")
        _require_keys(node, {"field", "operator", "value", "evidence"})
        if node["field"] not in field_registry:
            raise RuleValidationError(f"Unknown profile field: {node['field']!r}")
        if node["operator"] not in COMPARISON_OPERATORS:
            raise RuleValidationError(f"Unknown rule operator: {node['operator']!r}")
        _validate_evidence(node["evidence"])
        _validate_operand(field_registry[node["field"]], node["operator"], node["value"])
        if "exceptions_complete" in node and not isinstance(node["exceptions_complete"], bool):
            raise RuleValidationError("exceptions_complete must be a boolean")

    visit(rule, 1)


def evaluate_eligibility(*, revision_id: str, rule: Mapping[str, Any], profile: Mapping[str, Any], field_registry: Mapping[str, Mapping[str, Any]], coverage_complete: bool = True) -> EligibilityResult:
    """Classify strict hard eligibility as Strong, Possible, or Not a match."""

    if not revision_id:
        raise RuleValidationError("revision_id is required")
    if not isinstance(coverage_complete, bool):
        raise RuleValidationError("coverage_complete must be a boolean")
    validate_rule_tree(rule, field_registry)
    evaluated = _evaluate_node(rule, profile)
    unresolved = list(evaluated.unresolved_conditions)
    if evaluated.truth is TruthValue.PASS and not coverage_complete:
        evaluated.truth = TruthValue.UNKNOWN
        unresolved.append("The official eligibility model is incomplete because some requirements could not be represented.")
    if evaluated.truth is TruthValue.FAIL:
        label = EligibilityLabel.NOT_MATCH
    elif evaluated.truth is TruthValue.UNKNOWN:
        label = EligibilityLabel.POSSIBLE
    else:
        label = EligibilityLabel.STRONG
    return EligibilityResult(
        scholarship_version_id=revision_id,
        label=label,
        truth=evaluated.truth,
        criteria=tuple(evaluated.criteria),
        missing_fields=tuple(sorted(evaluated.missing_fields)),
        unknown_fields=tuple(sorted(evaluated.unknown_fields)),
        unresolved_conditions=tuple(unresolved),
    )


def _evaluate_node(node: Mapping[str, Any], profile: Mapping[str, Any]) -> NodeResult:
    node_type = node["type"]
    if node_type == "condition":
        return _evaluate_condition(node, profile)
    if node_type == "unsupported":
        description = node["description"].strip()
        criterion = CriterionResult("", "unsupported", TruthValue.UNKNOWN, node["evidence"], f"Official confirmation is needed: {description}", False)
        return NodeResult(TruthValue.UNKNOWN, [criterion], unresolved_conditions=[description])
    return _combine_group(node_type, [_evaluate_node(child, profile) for child in node["children"]])


def _experience_matches(experience: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    if "kind" in expected and experience.get("kind") != expected["kind"]:
        return False
    if "leadership" in expected and bool(experience.get("leadership")) is not expected["leadership"]:
        return False
    if "organization_contains" in expected and expected["organization_contains"].casefold() not in str(experience.get("organization", "")).casefold():
        return False
    if "title_contains" in expected and expected["title_contains"].casefold() not in str(experience.get("title", "")).casefold():
        return False
    if "tags_any" in expected and not set(expected["tags_any"]).intersection(experience.get("tags", [])):
        return False
    if "minimum_hours" in expected and (not _is_number(experience.get("hours")) or experience["hours"] < expected["minimum_hours"]):
        return False
    return True


def _evaluate_condition(node: Mapping[str, Any], profile: Mapping[str, Any]) -> NodeResult:
    name = node["field"]
    if name not in profile:
        criterion = CriterionResult(name, node["operator"], TruthValue.UNKNOWN, node["evidence"], f"{name} is unanswered in the profile.")
        return NodeResult(TruthValue.UNKNOWN, [criterion], missing_fields={name})
    if is_unknown(profile[name]):
        criterion = CriterionResult(name, node["operator"], TruthValue.UNKNOWN, node["evidence"], f"{name} is explicitly marked unknown.")
        return NodeResult(TruthValue.UNKNOWN, [criterion], unknown_fields={name})
    answer, expected, operator = profile[name], node["value"], node["operator"]
    if operator in DATE_OPERATORS:
        answer_date = _parse_date_operand(f"{answer}-01" if isinstance(answer, str) and len(answer) == 7 else answer)
        expected_date = _parse_date_operand(f"{expected}-01" if isinstance(expected, str) and len(expected) == 7 else expected)
        passed = {
            "before": answer_date < expected_date,
            "on_or_before": answer_date <= expected_date,
            "after": answer_date > expected_date,
            "on_or_after": answer_date >= expected_date,
        }[operator]
    elif operator == "experience_any":
        passed = isinstance(answer, list) and any(isinstance(item, Mapping) and _experience_matches(item, expected) for item in answer)
    else:
        passed = {
            "eq": lambda: answer == expected,
            "in": lambda: answer in expected,
            "contains": lambda: isinstance(answer, list) and expected in answer,
            "gt": lambda: _is_number(answer) and answer > expected,
            "gte": lambda: _is_number(answer) and answer >= expected,
            "lt": lambda: _is_number(answer) and answer < expected,
            "lte": lambda: _is_number(answer) and answer <= expected,
        }[operator]()
    truth = TruthValue.PASS if passed else TruthValue.FAIL
    reason = f"{name} passes this requirement." if passed else f"{name} does not pass this requirement."
    unresolved: list[str] = []
    if not passed and node.get("exceptions_complete", True) is False:
        truth = TruthValue.UNKNOWN
        reason = f"Possible exceptions for {name} require official confirmation."
        unresolved.append(reason)
    return NodeResult(truth, [CriterionResult(name, operator, truth, node["evidence"], reason)], unresolved_conditions=unresolved)


def _combine_group(group_type: str, children: list[NodeResult]) -> NodeResult:
    truths = [child.truth for child in children]
    if group_type == "and":
        truth = TruthValue.FAIL if TruthValue.FAIL in truths else (TruthValue.PASS if all(value is TruthValue.PASS for value in truths) else TruthValue.UNKNOWN)
        question_relevant = children if truth is not TruthValue.FAIL else []
    else:
        truth = TruthValue.PASS if TruthValue.PASS in truths else (TruthValue.FAIL if all(value is TruthValue.FAIL for value in truths) else TruthValue.UNKNOWN)
        question_relevant = [] if truth is TruthValue.PASS else children
    explanation_relevant = [child for child in children if child.truth is not TruthValue.UNKNOWN or child in question_relevant]
    return NodeResult(
        truth=truth,
        criteria=[item for child in explanation_relevant for item in child.criteria],
        missing_fields={item for child in question_relevant for item in child.missing_fields},
        unknown_fields={item for child in question_relevant for item in child.unknown_fields},
        unresolved_conditions=[item for child in explanation_relevant for item in child.unresolved_conditions],
    )
