"""Standard-library tests for the deterministic eligibility engine."""

import unittest

from app.eligibility import (
    EligibilityLabel,
    RuleValidationError,
    TruthValue,
    evaluate_eligibility,
    validate_rule_tree,
)


# Tests use a small registry so the engine remains independent of FastAPI and
# the database. The production API will pass its full profile-field registry.
FIELD_REGISTRY = {
    "state": {"type": "choice", "values": ["MA", "NY"]},
    "study_level": {"type": "choice", "values": ["undergraduate", "graduate"]},
    "gpa": {"type": "number"},
    "class_year": {"type": "choice", "values": ["first", "second", "third", "fourth"]},
    "assistance_categories": {"type": "multi_choice", "values": ["scholarships", "grants"]},
}


def evidence(number: int = 1) -> dict[str, str]:
    """Create traceable synthetic evidence for a test criterion."""

    return {"snapshot_id": f"snapshot-{number}", "excerpt": f"Synthetic requirement {number}."}


def condition(field: str, operator: str, value, number: int = 1, **extra) -> dict:
    """Build a condition while keeping individual tests easy to read."""

    return {
        "type": "condition",
        "field": field,
        "operator": operator,
        "value": value,
        "evidence": evidence(number),
        **extra,
    }


def evaluate(rule: dict, profile: dict, *, complete: bool = True):
    """Evaluate a synthetic published revision with common test defaults."""

    return evaluate_eligibility(
        revision_id="revision-1",
        rule=rule,
        profile=profile,
        field_registry=FIELD_REGISTRY,
        coverage_complete=complete,
    )


class EligibilityEvaluationTests(unittest.TestCase):
    """Verify three-valued logic, operators, and student-facing outcomes."""

    def test_all_supported_operators(self):
        """Each comparison operator should produce the expected truth value."""

        cases = [
            (condition("state", "eq", "MA"), {"state": "MA"}, TruthValue.TRUE),
            (condition("state", "in", ["MA", "NY"]), {"state": "NY"}, TruthValue.TRUE),
            (condition("assistance_categories", "contains", "scholarships"), {"assistance_categories": ["scholarships"]}, TruthValue.TRUE),
            (condition("gpa", "gt", 3.0), {"gpa": 3.1}, TruthValue.TRUE),
            (condition("gpa", "gte", 3.0), {"gpa": 3.0}, TruthValue.TRUE),
            (condition("gpa", "lt", 3.0), {"gpa": 2.9}, TruthValue.TRUE),
            (condition("gpa", "lte", 3.0), {"gpa": 3.0}, TruthValue.TRUE),
        ]
        for rule, profile, expected in cases:
            with self.subTest(operator=rule["operator"]):
                self.assertIs(evaluate(rule, profile).truth, expected)

    def test_and_or_and_unknown_truth_tables(self):
        """Nested groups follow the specified true, false, and unknown rules."""

        rule = {
            "type": "and",
            "children": [
                condition("state", "eq", "MA", 1),
                {
                    "type": "or",
                    "children": [
                        condition("study_level", "eq", "graduate", 2),
                        condition("gpa", "gte", 3.5, 3),
                    ],
                },
            ],
        }
        self.assertIs(evaluate(rule, {"state": "MA", "study_level": "graduate"}).truth, TruthValue.TRUE)
        self.assertIs(evaluate(rule, {"state": "MA", "study_level": "undergraduate"}).truth, TruthValue.UNKNOWN)
        self.assertIs(evaluate(rule, {"state": "NY"}).truth, TruthValue.FALSE)

    def test_missing_questions_only_when_they_can_change_the_outcome(self):
        """Resolved AND/OR branches must not ask irrelevant follow-up questions."""

        and_rule = {"type": "and", "children": [condition("state", "eq", "MA"), condition("gpa", "gte", 3.0)]}
        self.assertEqual(evaluate(and_rule, {"state": "NY"}).missing_fields, ())

        or_rule = {"type": "or", "children": [condition("state", "eq", "MA"), condition("gpa", "gte", 3.0)]}
        self.assertEqual(evaluate(or_rule, {"state": "MA"}).missing_fields, ())
        self.assertEqual(evaluate(or_rule, {"state": "NY"}).missing_fields, ("gpa",))

    def test_failed_or_condition_is_explained_as_an_alternative(self):
        """Keep a resolved failed alternative without making it disqualifying."""

        rule = {
            "type": "or",
            "children": [
                condition("state", "eq", "MA", 1),
                condition("study_level", "eq", "graduate", 2),
                condition("gpa", "gte", 3.0, 3),
            ],
        }
        result = evaluate(rule, {"state": "NY", "study_level": "graduate"})
        self.assertIs(result.label, EligibilityLabel.LIKELY_ELIGIBLE)
        self.assertEqual(result.missing_fields, ())
        self.assertEqual([criterion.truth for criterion in result.criteria], [TruthValue.FALSE, TruthValue.TRUE])

    def test_incomplete_coverage_and_unmodeled_exceptions_are_unknown(self):
        """The engine stays conservative when reviewed rules are incomplete."""

        passing = condition("state", "eq", "MA")
        result = evaluate(passing, {"state": "MA"}, complete=False)
        self.assertIs(result.label, EligibilityLabel.NEED_MORE_INFORMATION)
        self.assertIn("incomplete", result.unresolved_conditions[0])

        exception_rule = condition("state", "eq", "MA", exceptions_complete=False)
        result = evaluate(exception_rule, {"state": "NY"})
        self.assertIs(result.truth, TruthValue.UNKNOWN)
        self.assertIs(result.label, EligibilityLabel.NEED_MORE_INFORMATION)

    def test_unsupported_condition_requires_provider_review(self):
        """A condition the engine cannot model is unresolved, not false."""

        rule = {
            "type": "unsupported",
            "description": "Student must demonstrate community leadership",
            "evidence": evidence(),
        }
        result = evaluate(rule, {})
        self.assertIs(result.truth, TruthValue.UNKNOWN)
        self.assertEqual(result.missing_fields, ())
        self.assertFalse(result.criteria[0].answerable)

    def test_one_hundred_independently_expected_boundary_profiles(self):
        """Run the required 100-profile suite across a fixed GPA boundary."""

        rule = condition("gpa", "gte", 3.0)
        # Each tuple explicitly records its expected label. Values cover fifty
        # points below the boundary, the exact boundary, and forty-nine above.
        cases = [
            *((round(2.50 + index / 100, 2), EligibilityLabel.LIKELY_INELIGIBLE) for index in range(50)),
            (3.00, EligibilityLabel.LIKELY_ELIGIBLE),
            *((round(3.01 + index / 100, 2), EligibilityLabel.LIKELY_ELIGIBLE) for index in range(49)),
        ]
        self.assertEqual(len(cases), 100)
        for gpa, expected in cases:
            with self.subTest(gpa=gpa):
                self.assertIs(evaluate(rule, {"gpa": gpa}).label, expected)

    def test_same_inputs_produce_equal_results(self):
        """Evaluation is deterministic and does not mutate the supplied profile."""

        rule = condition("state", "eq", "MA")
        profile = {"state": "MA"}
        first = evaluate(rule, profile)
        second = evaluate(rule, profile)
        self.assertEqual(first, second)
        self.assertEqual(profile, {"state": "MA"})


class RuleValidationTests(unittest.TestCase):
    """Reject malformed or unsafe rule trees before evaluating students."""

    def assert_invalid(self, rule: dict, message: str):
        """Assert validation fails and identifies the contract violation."""

        with self.assertRaisesRegex(RuleValidationError, message):
            validate_rule_tree(rule, FIELD_REGISTRY)

    def test_unknown_fields_operators_and_node_types(self):
        self.assert_invalid(condition("unknown", "eq", "x"), "Unknown profile field")
        self.assert_invalid(condition("state", "matches", "MA"), "Unknown rule operator")
        self.assert_invalid({"type": "maybe"}, "Unknown rule node type")

    def test_empty_groups_and_invalid_operands(self):
        self.assert_invalid({"type": "and", "children": []}, "at least one child")
        self.assert_invalid(condition("state", "in", []), "non-empty list")
        self.assert_invalid(condition("state", "gte", 3), "numeric field")
        self.assert_invalid(condition("state", "contains", "MA"), "multi-choice field")

    def test_evidence_is_required(self):
        rule = condition("state", "eq", "MA")
        rule["evidence"] = {"snapshot_id": "snapshot-1"}
        self.assert_invalid(rule, "requires excerpt")

    def test_depth_and_size_limits(self):
        nested = condition("state", "eq", "MA")
        for _ in range(9):
            nested = {"type": "and", "children": [nested]}
        self.assert_invalid(nested, "deeply nested")

        wide = {"type": "or", "children": [condition("state", "eq", "MA", number) for number in range(201)]}
        self.assert_invalid(wide, "too many nodes")


if __name__ == "__main__":
    unittest.main()
