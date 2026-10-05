"""Offline metrics for the versioned, manually labeled extraction benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .extraction_schemas import ConditionRule, ExtractedProgramDraft, RuleGroup, RuleNode, UnsupportedRule


BENCHMARK_VERSION = "1.0.0"
BENCHMARK_PATH = Path(__file__).parents[1] / "data" / "extraction_benchmark_v1.json"
FIELD_PATHS = (
    "name",
    "categories",
    "award_cycle",
    "application_deadline",
    "deadline_timezone",
    "application_availability",
    "assistance_amount",
)


@dataclass(frozen=True)
class Metric:
    """A count and explicit denominator suitable for honest reporting."""

    numerator: int
    denominator: int

    @property
    def value(self) -> float:
        """Return a ratio while defining an empty metric as zero."""

        return self.numerator / self.denominator if self.denominator else 0.0


@dataclass(frozen=True)
class ExtractionBenchmarkReport:
    """Required extraction metrics for one fixed dataset version."""

    dataset_version: str
    case_count: int
    field_accuracy: Metric
    criterion_precision: Metric
    criterion_recall: Metric
    unsupported_claim_rate: Metric
    evidence_fidelity: Metric


def load_benchmark(path: Path = BENCHMARK_PATH) -> dict[str, Any]:
    """Load and validate the fixed benchmark without making model calls."""

    dataset = json.loads(path.read_text(encoding="utf-8"))
    if dataset.get("version") != BENCHMARK_VERSION:
        raise ValueError("Unsupported extraction benchmark version")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) < 10:
        raise ValueError("The extraction benchmark requires at least 10 cases")
    ids = [case.get("id") for case in cases]
    if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Extraction benchmark case IDs must be present and unique")
    for case in cases:
        source = case.get("source_text", "")
        for claim in _expected_claims(case):
            if claim[3] not in source:
                raise ValueError(f"Benchmark evidence is absent in case {case['id']}")
    return dataset


def evaluate_extractions(
    dataset: dict[str, Any],
    predictions: dict[str, ExtractedProgramDraft],
) -> ExtractionBenchmarkReport:
    """Compare proposed drafts with manual labels using explicit denominators."""

    field_correct = field_total = 0
    expected_criteria: set[tuple] = set()
    predicted_criteria: set[tuple] = set()
    expected_claims: set[tuple] = set()
    predicted_claims: set[tuple] = set()
    faithful_evidence = evidence_total = 0

    for case in dataset["cases"]:
        case_id = case["id"]
        prediction = predictions.get(case_id)
        if prediction is None:
            field_total += len(case["fields"])
            expected = set(_expected_claims(case, "condition"))
            expected_criteria.update((case_id, *claim) for claim in expected)
            expected_claims.update((case_id, *claim) for claim in _expected_claims(case))
            continue
        for path, expected_value in case["fields"].items():
            field_total += 1
            field_correct += getattr(prediction, path) == expected_value

        expected_case_claims = set(_expected_claims(case))
        predicted_case_claims = set(_predicted_claims(prediction))
        expected_claims.update((case_id, *claim) for claim in expected_case_claims)
        predicted_claims.update((case_id, *claim) for claim in predicted_case_claims)
        expected_criteria.update((case_id, *claim) for claim in expected_case_claims if claim[0] == "condition")
        predicted_criteria.update((case_id, *claim) for claim in predicted_case_claims if claim[0] == "condition")
        for claim in predicted_case_claims:
            evidence_total += 1
            faithful_evidence += claim[3] in case["source_text"]

    correct_criteria = len(expected_criteria & predicted_criteria)
    unsupported_claims = len(predicted_claims - expected_claims)
    return ExtractionBenchmarkReport(
        dataset_version=dataset["version"],
        case_count=len(dataset["cases"]),
        field_accuracy=Metric(field_correct, field_total),
        criterion_precision=Metric(correct_criteria, len(predicted_criteria)),
        criterion_recall=Metric(correct_criteria, len(expected_criteria)),
        unsupported_claim_rate=Metric(unsupported_claims, len(predicted_claims)),
        evidence_fidelity=Metric(faithful_evidence, evidence_total),
    )


def _expected_claims(case: dict[str, Any], kind: str | None = None) -> Iterable[tuple]:
    """Convert manual claim labels into comparable immutable tuples."""

    for claim in case.get("claims", []):
        if kind is None or claim["kind"] == kind:
            yield (claim["kind"], claim["subject"], json.dumps(claim.get("value"), sort_keys=True), claim["evidence"])


def _predicted_claims(draft: ExtractedProgramDraft) -> Iterable[tuple]:
    """Flatten eligibility, preference, and unsupported proposal claims."""

    yield from _rule_claims(draft.eligibility_tree)
    for factor in draft.selection_factors:
        yield ("selection", factor.description, "null", factor.evidence.excerpt)


def _rule_claims(rule: RuleNode) -> Iterable[tuple]:
    """Flatten a recursive rule tree into benchmark claim records."""

    if isinstance(rule, ConditionRule):
        yield ("condition", f"{rule.field}:{rule.operator}", json.dumps(rule.value, sort_keys=True), rule.evidence.excerpt)
    elif isinstance(rule, UnsupportedRule):
        yield ("unsupported", rule.description, "null", rule.evidence.excerpt)
    elif isinstance(rule, RuleGroup):
        for child in rule.children:
            yield from _rule_claims(child)
