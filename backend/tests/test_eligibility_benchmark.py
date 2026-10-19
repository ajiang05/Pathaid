"""Tests for the fixed, independently labeled eligibility benchmark."""

import json

import pytest

from app.eligibility_benchmark import (
    BENCHMARK_VERSION,
    EXPECTED_CASE_COUNT,
    evaluate_eligibility_benchmark,
    load_eligibility_benchmark,
)
from app.quality_report import build_offline_report, load_extraction_predictions


def test_fixed_dataset_has_one_hundred_unique_manual_expectations():
    """The versioned file must retain the required case count and provenance."""

    dataset = load_eligibility_benchmark()
    cases = [case for suite in dataset["suites"] for case in suite["cases"]]
    assert dataset["version"] == BENCHMARK_VERSION
    assert "Manual synthetic expected outcomes" in dataset["labeling"]
    assert len(cases) == EXPECTED_CASE_COUNT
    assert len({case[0] for case in cases}) == EXPECTED_CASE_COUNT


def test_all_manual_eligibility_expectations_pass():
    """Every operator and conservative unknown case must match its manual label."""

    report = evaluate_eligibility_benchmark(load_eligibility_benchmark())
    assert report.total == EXPECTED_CASE_COUNT
    assert report.failures == ()
    assert report.passed == report.total
    assert report.accuracy == 1.0


def test_loader_rejects_missing_cases_and_duplicate_ids(tmp_path):
    """Changing the denominator or duplicating a case cannot silently pass CI."""

    dataset = load_eligibility_benchmark()
    dataset["suites"][0]["cases"].pop()
    short_path = tmp_path / "short.json"
    short_path.write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly 100"):
        load_eligibility_benchmark(short_path)

    dataset = load_eligibility_benchmark()
    dataset["suites"][0]["cases"][1][0] = dataset["suites"][0]["cases"][0][0]
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_eligibility_benchmark(duplicate_path)


def test_offline_report_distinguishes_measurements_from_pending_work():
    """The public report must not turn an offline label check into an AI claim."""

    report = build_offline_report()
    assert report["eligibility"]["passed"] == report["eligibility"]["total"] == 100
    assert report["extraction_dataset"]["cases"] == 10
    assert report["extraction_dataset"]["field_labels"] > 0
    assert report["extraction_dataset"]["claim_labels"] > 0
    assert report["extraction_dataset"]["model_metrics"] is None
    assert report["frontend"]["usability_sessions_completed"] == 0


def test_supplied_extraction_artifact_reports_explicit_denominators(tmp_path):
    """Even an empty saved run produces honest zero scores and denominators."""

    artifact = tmp_path / "predictions.json"
    artifact.write_text(json.dumps({"dataset_version": "1.0.0", "predictions": {}}), encoding="utf-8")
    predictions = load_extraction_predictions(artifact)
    metrics = build_offline_report(predictions)["extraction_dataset"]["model_metrics"]
    assert metrics["field_accuracy"] == {"numerator": 0, "denominator": 28, "value": 0.0}
    assert metrics["criterion_recall"]["denominator"] == 8
    assert metrics["criterion_precision"]["denominator"] == 0


def test_prediction_artifact_must_match_dataset_version(tmp_path):
    """Metrics cannot combine predictions and labels from different versions."""

    artifact = tmp_path / "wrong-version.json"
    artifact.write_text(json.dumps({"dataset_version": "old", "predictions": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        load_extraction_predictions(artifact)
