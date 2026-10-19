"""Deterministic evaluation of reviewed eligibility rule trees.

The engine contains no database, HTTP, or model calls. Callers supply a
validated student profile, a reviewed rule tree, and the field registry. This
keeps the same inputs reproducible and makes the eligibility decision auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from numbers import Real
from typing import Any, Mapping


MAX_TREE_DEPTH = 8
MAX_TREE_NODES = 200
COMPARISON_OPERATORS = {"eq", "in", "contains", "gt", "gte", "lt", "lte"}
NUMERIC_OPERATORS = {"gt", "gte", "lt", "lte"}


class RuleValidationError(ValueError):
    """Raised when reviewed rules do not satisfy the evaluator contract."""


class TruthValue(str, Enum):
    """The three possible values produced by every rule-tree node."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class EligibilityLabel(str, Enum):
    """Student-facing labels derived from a root truth value."""

    LIKELY_ELIGIBLE = "Likely eligible"
    LIKELY_INELIGIBLE = "Likely ineligible"
    NEED_MORE_INFORMATION = "Need more information"


@dataclass(frozen=True)
class CriterionResult:
    """An auditable result for one condition, including its source evidence."""

    field: str
    operator: str
    truth: TruthValue
    evidence: Mapping[str, str]
    reason: str
    answerable: bool = True


@dataclass
class NodeResult:
    """Internal recursive result used to combine conditions and groups."""

    truth: TruthValue
    criteria: list[CriterionResult] = field(default_factory=list)
    missing_fields: set[str] = field(default_factory=set)
    unresolved_conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EligibilityResult:
    """Complete public result for one program revision and one profile."""

    revision_id: str
    label: EligibilityLabel
    truth: TruthValue
    criteria: tuple[CriterionResult, ...]
    missing_fields: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]


def _is_number(value: Any) -> bool:
    """Recognize real numbers while rejecting booleans, which subclass int."""

    return isinstance(value, Real) and not isinstance(value, bool)


def _require_keys(node: Mapping[str, Any], required: set[str]) -> None:
    """Fail with a stable message when a rule omits required properties."""

    missing = required.difference(node)
    if missing:
        raise RuleValidationError(f"Rule is missing required keys: {', '.join(sorted(missing))}")


def validate_rule_tree(
    rule: Mapping[str, Any],
    field_registry: Mapping[str, Mapping[str, Any]],
    *,
    max_depth: int = MAX_TREE_DEPTH,
    max_nodes: int = MAX_TREE_NODES,
) -> None:
    """Validate rule structure, operators, fields, evidence, size, and types.

    Rules are plain mappings so they can later be loaded from PostgreSQL JSON.
    Validation happens before evaluation, preventing malformed reviewed data
    from being treated as a student eligibility result.
    """

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
            children = node["children"]
            if not isinstance(children, list) or not children:
                raise RuleValidationError("Rule groups must contain at least one child")
            for child in children:
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
        field_name = node["field"]
        operator = node["operator"]
        if field_name not in field_registry:
            raise RuleValidationError(f"Unknown profile field: {field_name!r}")
        if operator not in COMPARISON_OPERATORS:
            raise RuleValidationError(f"Unknown rule operator: {operator!r}")
        _validate_evidence(node["evidence"])
        _validate_operand(field_registry[field_name], operator, node["value"])
        if "exceptions_complete" in node and not isinstance(node["exceptions_complete"], bool):
            raise RuleValidationError("exceptions_complete must be a boolean")

    visit(rule, 1)


def _validate_evidence(evidence: Any) -> None:
    """Require every condition to identify its snapshot and supporting text."""

    if not isinstance(evidence, Mapping):
        raise RuleValidationError("Rule evidence must be an object")
    for key in ("snapshot_id", "excerpt"):
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            raise RuleValidationError(f"Rule evidence requires {key}")


def _validate_operand(field_spec: Mapping[str, Any], operator: str, operand: Any) -> None:
    """Ensure a rule operand is compatible with its registry field type."""

    field_type = field_spec.get("type")
    if operator in NUMERIC_OPERATORS:
        if field_type not in {"integer", "number"} or not _is_number(operand):
            raise RuleValidationError("Numeric operators require a numeric field and operand")
    elif operator == "in":
        if not isinstance(operand, list) or not operand:
            raise RuleValidationError("The in operator requires a non-empty list")
    elif operator == "contains":
        if field_type != "multi_choice":
            raise RuleValidationError("The contains operator requires a multi-choice field")
    elif operator == "eq":
        if field_type == "boolean" and not isinstance(operand, bool):
            raise RuleValidationError("Boolean equality requires a boolean operand")
        if field_type in {"integer", "number"} and not _is_number(operand):
            raise RuleValidationError("Numeric equality requires a numeric operand")


def evaluate_eligibility(
    *,
    revision_id: str,
    rule: Mapping[str, Any],
    profile: Mapping[str, Any],
    field_registry: Mapping[str, Mapping[str, Any]],
    coverage_complete: bool,
) -> EligibilityResult:
    """Validate and evaluate one published revision against a student profile."""

    if not revision_id:
        raise RuleValidationError("revision_id is required")
    if not isinstance(coverage_complete, bool):
        raise RuleValidationError("coverage_complete must be a boolean")
    validate_rule_tree(rule, field_registry)
    evaluated = _evaluate_node(rule, profile)

    # A true tree may be labeled eligible only when the reviewer attested that
    # all eligibility requirements were represented. A false necessary rule is
    # conclusive even when unrelated coverage remains incomplete.
    if evaluated.truth is TruthValue.TRUE and coverage_complete:
        label = EligibilityLabel.LIKELY_ELIGIBLE
    elif evaluated.truth is TruthValue.FALSE:
        label = EligibilityLabel.LIKELY_INELIGIBLE
    else:
        label = EligibilityLabel.NEED_MORE_INFORMATION

    unresolved = list(evaluated.unresolved_conditions)
    if evaluated.truth is TruthValue.TRUE and not coverage_complete:
        unresolved.append("The reviewed eligibility model is incomplete.")

    return EligibilityResult(
        revision_id=revision_id,
        label=label,
        truth=evaluated.truth,
        criteria=tuple(evaluated.criteria),
        missing_fields=tuple(sorted(evaluated.missing_fields)),
        unresolved_conditions=tuple(unresolved),
    )


def _evaluate_node(node: Mapping[str, Any], profile: Mapping[str, Any]) -> NodeResult:
    """Recursively evaluate a node after the whole tree has been validated."""

    node_type = node["type"]
    if node_type == "condition":
        return _evaluate_condition(node, profile)
    if node_type == "unsupported":
        description = node["description"].strip()
        result = CriterionResult(
            field="",
            operator="unsupported",
            truth=TruthValue.UNKNOWN,
            evidence=node["evidence"],
            reason=f"Provider review is required: {description}",
            answerable=False,
        )
        return NodeResult(TruthValue.UNKNOWN, [result], unresolved_conditions=[description])

    children = [_evaluate_node(child, profile) for child in node["children"]]
    return _combine_group(node_type, children)


def _evaluate_condition(node: Mapping[str, Any], profile: Mapping[str, Any]) -> NodeResult:
    """Evaluate one answerable condition and retain its reviewed evidence."""

    field_name = node["field"]
    if field_name not in profile or profile[field_name] is None:
        criterion = CriterionResult(
            field=field_name,
            operator=node["operator"],
            truth=TruthValue.UNKNOWN,
            evidence=node["evidence"],
            reason=f"An answer for {field_name} is needed.",
        )
        return NodeResult(TruthValue.UNKNOWN, [criterion], {field_name})

    answer = profile[field_name]
    expected = node["value"]
    operator = node["operator"]
    comparisons = {
        "eq": lambda: answer == expected,
        "in": lambda: answer in expected,
        "contains": lambda: isinstance(answer, list) and expected in answer,
        "gt": lambda: _is_number(answer) and answer > expected,
        "gte": lambda: _is_number(answer) and answer >= expected,
        "lt": lambda: _is_number(answer) and answer < expected,
        "lte": lambda: _is_number(answer) and answer <= expected,
    }
    passed = comparisons[operator]()
    truth = TruthValue.TRUE if passed else TruthValue.FALSE
    reason = f"{field_name} satisfies the reviewed requirement." if passed else f"{field_name} does not satisfy the reviewed requirement."

    # A failed condition cannot reject a student when the reviewer recorded
    # that unmodeled exceptions might override it.
    unresolved: list[str] = []
    if not passed and node.get("exceptions_complete", True) is False:
        truth = TruthValue.UNKNOWN
        reason = f"Provider review is required for possible {field_name} exceptions."
        unresolved.append(reason)

    criterion = CriterionResult(field_name, operator, truth, node["evidence"], reason)
    return NodeResult(truth, [criterion], unresolved_conditions=unresolved)


def _combine_group(group_type: str, children: list[NodeResult]) -> NodeResult:
    """Apply three-valued AND/OR logic and retain only actionable questions."""

    truths = [child.truth for child in children]
    if group_type == "and":
        truth = TruthValue.FALSE if TruthValue.FALSE in truths else (TruthValue.TRUE if all(value is TruthValue.TRUE for value in truths) else TruthValue.UNKNOWN)
        # Once one required AND condition is false, missing answers elsewhere
        # cannot change the program-wide result and should not be requested.
        question_relevant = children if truth is not TruthValue.FALSE else []
    else:
        truth = TruthValue.TRUE if TruthValue.TRUE in truths else (TruthValue.FALSE if all(value is TruthValue.FALSE for value in truths) else TruthValue.UNKNOWN)
        # Once one OR alternative is true, no other answer is needed. If every
        # alternative fails, retain all failures so the explanation shows that
        # each was an alternative rather than a separate program requirement.
        question_relevant = [] if truth is TruthValue.TRUE else children

    # Preserve resolved true and false criteria for an auditable explanation.
    # Unknown criteria are included only while they could affect this group;
    # this prevents the UI from presenting irrelevant unanswered alternatives.
    explanation_relevant = [
        child
        for child in children
        if child.truth is not TruthValue.UNKNOWN or child in question_relevant
    ]

    return NodeResult(
        truth=truth,
        criteria=[criterion for child in explanation_relevant for criterion in child.criteria],
        missing_fields={name for child in question_relevant for name in child.missing_fields},
        unresolved_conditions=[message for child in question_relevant for message in child.unresolved_conditions],
    )
