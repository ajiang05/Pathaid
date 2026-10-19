"""Versioned offline benchmark for deterministic eligibility decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .eligibility import EligibilityLabel, evaluate_eligibility
from .profile_fields import FIELDS


BENCHMARK_VERSION = "1.0.0"
BENCHMARK_PATH = Path(__file__).parents[1] / "data" / "eligibility_benchmark_v1.json"
EXPECTED_CASE_COUNT = 100


@dataclass(frozen=True)
class EligibilityFailure:
    """One disagreement between a manual label and the deterministic engine."""

    case_id: str
    expected_label: str
    actual_label: str


@dataclass(frozen=True)
class EligibilityBenchmarkReport:
    """Measured correctness with an explicit denominator and failure details."""

    dataset_version: str
    passed: int
    total: int
    failures: tuple[EligibilityFailure, ...]

    @property
    def accuracy(self) -> float:
        """Return the exact fraction of manually labeled cases that passed."""

        return self.passed / self.total if self.total else 0.0


def load_eligibility_benchmark(path: Path = BENCHMARK_PATH) -> dict[str, Any]:
    """Load the fixed dataset and reject incomplete or duplicate manual labels."""

    dataset = json.loads(path.read_text(encoding="utf-8"))
    if dataset.get("version") != BENCHMARK_VERSION:
        raise ValueError("Unsupported eligibility benchmark version")
    suites = dataset.get("suites")
    if not isinstance(suites, list) or not suites:
        raise ValueError("Eligibility benchmark suites are required")

    case_ids: list[str] = []
    valid_labels = {label.value for label in EligibilityLabel}
    for suite in suites:
        if not isinstance(suite.get("id"), str) or not suite["id"]:
            raise ValueError("Eligibility benchmark suite IDs are required")
        if not isinstance(suite.get("rule"), dict):
            raise ValueError(f"Eligibility suite {suite['id']} requires a rule")
        if not isinstance(suite.get("coverage_complete", True), bool):
            raise ValueError(f"Eligibility suite {suite['id']} has invalid coverage completeness")
        for case in suite.get("cases", []):
            if not isinstance(case, list) or len(case) != 3:
                raise ValueError(f"Eligibility suite {suite['id']} contains an invalid case")
            case_id, profile, expected_label = case
            if not isinstance(case_id, str) or not case_id or not isinstance(profile, dict):
                raise ValueError(f"Eligibility suite {suite['id']} contains an invalid case")
            if expected_label not in valid_labels:
                raise ValueError(f"Eligibility case {case_id} has an invalid expected label")
            case_ids.append(case_id)
    if len(case_ids) != EXPECTED_CASE_COUNT:
        raise ValueError(f"Eligibility benchmark requires exactly {EXPECTED_CASE_COUNT} cases")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Eligibility benchmark case IDs must be unique")
    return dataset


def evaluate_eligibility_benchmark(dataset: dict[str, Any]) -> EligibilityBenchmarkReport:
    """Run every explicit profile label through the production eligibility engine."""

    failures: list[EligibilityFailure] = []
    total = 0
    for suite in dataset["suites"]:
        for case_id, profile, expected_label in suite["cases"]:
            total += 1
            result = evaluate_eligibility(
                revision_id=f"benchmark-{suite['id']}",
                rule=suite["rule"],
                profile=profile,
                field_registry=FIELDS,
                coverage_complete=suite.get("coverage_complete", True),
            )
            if result.label.value != expected_label:
                failures.append(EligibilityFailure(case_id, expected_label, result.label.value))
    return EligibilityBenchmarkReport(
        dataset_version=dataset["version"],
        passed=total - len(failures),
        total=total,
        failures=tuple(failures),
    )
