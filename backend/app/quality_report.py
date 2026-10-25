"""Print reproducible offline quality measurements as machine-readable JSON."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

from .eligibility_benchmark import evaluate_eligibility_benchmark, load_eligibility_benchmark
from .extraction_benchmark import Metric, evaluate_extractions, load_benchmark
from .extraction_schemas import ExtractedProgramDraft


def _metric(metric: Metric) -> dict:
    """Serialize a measurement without dropping its denominator."""

    return {"numerator": metric.numerator, "denominator": metric.denominator, "value": metric.value}


def load_extraction_predictions(path: Path) -> dict[str, ExtractedProgramDraft]:
    """Validate a separately generated, version-matched prediction artifact."""

    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact.get("dataset_version") != load_benchmark()["version"]:
        raise ValueError("Extraction prediction dataset version does not match")
    predictions = artifact.get("predictions")
    if not isinstance(predictions, dict):
        raise ValueError("Extraction predictions must be an object keyed by case ID")
    return {case_id: ExtractedProgramDraft.model_validate(value) for case_id, value in predictions.items()}


def build_offline_report(extraction_predictions: dict[str, ExtractedProgramDraft] | None = None) -> dict:
    """Measure deterministic checks and identify evaluations requiring a live run."""

    eligibility = evaluate_eligibility_benchmark(load_eligibility_benchmark())
    extraction = load_benchmark()
    extraction_field_labels = sum(len(case["fields"]) for case in extraction["cases"])
    extraction_claim_labels = sum(len(case.get("claims", [])) for case in extraction["cases"])
    model_metrics = None
    model_metrics_status = "not measured by offline checks"
    if extraction_predictions is not None:
        measured = evaluate_extractions(extraction, extraction_predictions)
        model_metrics = {
            "field_accuracy": _metric(measured.field_accuracy),
            "criterion_precision": _metric(measured.criterion_precision),
            "criterion_recall": _metric(measured.criterion_recall),
            "unsupported_claim_rate": _metric(measured.unsupported_claim_rate),
            "evidence_fidelity": _metric(measured.evidence_fidelity),
        }
        model_metrics_status = "measured from supplied prediction artifact"
    return {
        "report_type": "offline_deterministic",
        "eligibility": {
            "dataset_version": eligibility.dataset_version,
            "passed": eligibility.passed,
            "total": eligibility.total,
            "accuracy": eligibility.accuracy,
            "failures": [failure.__dict__ for failure in eligibility.failures],
        },
        "extraction_dataset": {
            "dataset_version": extraction["version"],
            "cases": len(extraction["cases"]),
            "field_labels": extraction_field_labels,
            "claim_labels": extraction_claim_labels,
            # Offline CI validates the labels and metric implementation. It
            # does not claim model accuracy without a separately saved run.
            "model_metrics": model_metrics,
            "model_metrics_status": model_metrics_status,
        },
        "frontend": {
            # Browser checks execute in the frontend workflow because they
            # require Node, Chromium, and a running Next.js server. Keep their
            # reproducible command and scope visible without claiming that this
            # Python report executed them.
            "browser_tests": "implemented; run separately",
            "command": "cd frontend && npm run test:e2e",
            "projects": ["desktop-chromium", "mobile-chromium"],
            "accessibility_standard": "WCAG 2.2 AA tags via axe-core",
            "usability_sessions_completed": 0,
            "usability_sessions_required": 5,
        },
    }


def main() -> None:
    """Write stable JSON suitable for CI logs or a saved evaluation artifact."""

    parser = argparse.ArgumentParser(description="Report Pathaid quality measurements")
    parser.add_argument(
        "--extraction-predictions",
        type=Path,
        help="Optional saved prediction artifact from a separately budgeted model run",
    )
    arguments = parser.parse_args()
    predictions = load_extraction_predictions(arguments.extraction_predictions) if arguments.extraction_predictions else None
    print(json.dumps(build_offline_report(predictions), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
