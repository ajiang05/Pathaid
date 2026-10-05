"""Tests for the fixed extraction dataset and metric calculations."""

from app.extraction_benchmark import BENCHMARK_VERSION, evaluate_extractions, load_benchmark
from app.extraction_schemas import ExtractedProgramDraft


def gpa_prediction() -> ExtractedProgramDraft:
    """Return a correct prediction for the benchmark's GPA boundary case."""

    excerpt = "Applicants must have a GPA of at least 3.0 on a 4.0 scale."
    return ExtractedProgramDraft.model_validate(
        {
            "name": "Merit Award",
            "description": "A merit scholarship.",
            "categories": ["scholarships"],
            "coverage": {"national": True, "states": [], "institutions": []},
            "checklist": [],
            "eligibility_tree": {
                "type": "and",
                "children": [
                    {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": {"snapshot_id": "gpa-boundary", "excerpt": excerpt}, "exceptions_complete": True},
                    {"type": "condition", "field": "gpa_scale", "operator": "eq", "value": 4.0, "evidence": {"snapshot_id": "gpa-boundary", "excerpt": excerpt}, "exceptions_complete": True}
                ]
            },
            "coverage_complete": True,
            "award_cycle": None,
            "application_deadline": None,
            "deadline_timezone": None,
            "application_availability": "unknown",
            "assistance_amount": None,
            "selection_factors": [],
            "application_url": None,
            "unresolved_conditions": []
        }
    )


def test_fixed_benchmark_has_ten_valid_manually_labeled_cases():
    """Dataset version, unique cases, and every evidence span are checked."""

    dataset = load_benchmark()

    assert dataset["version"] == BENCHMARK_VERSION
    assert len(dataset["cases"]) == 10
    assert "Manual synthetic labels" in dataset["labeling"]


def test_metrics_report_explicit_denominators_for_partial_predictions():
    """Missing predictions reduce recall and field accuracy without disappearing."""

    dataset = load_benchmark()
    report = evaluate_extractions(dataset, {"gpa-boundary": gpa_prediction()})

    assert report.case_count == 10
    assert report.field_accuracy.numerator == 2
    assert report.field_accuracy.denominator > report.field_accuracy.numerator
    assert report.criterion_precision.numerator == report.criterion_precision.denominator == 2
    assert report.criterion_recall.numerator == 2
    assert report.criterion_recall.denominator > 2
    assert report.unsupported_claim_rate.numerator == 0
    assert report.evidence_fidelity.numerator == report.evidence_fidelity.denominator == 2
