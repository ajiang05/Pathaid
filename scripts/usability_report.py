#!/usr/bin/env python3
"""Evaluate anonymized PathAid usability evidence against MVP release gates."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import statistics
import sys
from typing import Any


REQUIRED_TASKS = set(range(2, 8))
SEVERITIES = {"low", "medium", "high", "critical"}
SESSION_FIELDS = {
    "participant_code",
    "date",
    "device_browser",
    "tasks_completed",
    "first_useful_result_seconds",
    "eligibility_understood",
    "privacy_understood",
    "help_given",
    "keyboard_only_check",
    "assistive_technology",
    "finding_ids",
}
FINDING_FIELDS = {"id", "description", "severity", "status", "resolution", "verification"}


class EvidenceError(ValueError):
    """The session file is incomplete or does not match the evidence schema."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def nonempty_string(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def validate_session(raw: Any, index: int) -> dict[str, Any]:
    """Validate one anonymous observed-session record without accepting PII."""

    require(isinstance(raw, dict), f"session {index} must be an object")
    require(not (set(raw) - SESSION_FIELDS), f"session {index} contains undeclared fields")
    code = nonempty_string(raw.get("participant_code"), f"session {index}.participant_code")
    require(code.startswith("P") and code[1:].isdigit(), f"session {index} must use an anonymous code such as P01")
    session_date = nonempty_string(raw.get("date"), f"session {index}.date")
    try:
        date.fromisoformat(session_date)
    except ValueError as error:
        raise EvidenceError(f"session {index}.date must be YYYY-MM-DD") from error
    nonempty_string(raw.get("device_browser"), f"session {index}.device_browser")

    tasks = raw.get("tasks_completed")
    require(
        isinstance(tasks, list)
        and all(type(task) is int and 1 <= task <= 8 for task in tasks)
        and len(tasks) == len(set(tasks)),
        f"session {index}.tasks_completed must contain unique task numbers 1-8",
    )
    seconds = raw.get("first_useful_result_seconds")
    require(
        type(seconds) is int and 1 <= seconds <= 7200,
        f"session {index}.first_useful_result_seconds must be 1-7200",
    )
    for field in ("eligibility_understood", "privacy_understood", "keyboard_only_check"):
        require(type(raw.get(field)) is bool, f"session {index}.{field} must be boolean")
    nonempty_string(raw.get("help_given"), f"session {index}.help_given")

    assistive = raw.get("assistive_technology")
    require(
        assistive is None or (isinstance(assistive, str) and bool(assistive.strip())),
        f"session {index}.assistive_technology must be null or a non-empty string",
    )
    findings = raw.get("finding_ids")
    require(
        isinstance(findings, list)
        and all(isinstance(item, str) and item.strip() for item in findings)
        and len(findings) == len(set(findings)),
        f"session {index}.finding_ids must contain unique finding IDs",
    )
    return raw


def validate_finding(raw: Any, index: int) -> dict[str, Any]:
    """Validate one issue and its release-resolution evidence."""

    require(isinstance(raw, dict), f"finding {index} must be an object")
    require(not (set(raw) - FINDING_FIELDS), f"finding {index} contains undeclared fields")
    nonempty_string(raw.get("id"), f"finding {index}.id")
    nonempty_string(raw.get("description"), f"finding {index}.description")
    require(raw.get("severity") in SEVERITIES, f"finding {index}.severity is invalid")
    require(raw.get("status") in {"open", "resolved"}, f"finding {index}.status is invalid")
    if raw["status"] == "resolved":
        nonempty_string(raw.get("resolution"), f"finding {index}.resolution")
        nonempty_string(raw.get("verification"), f"finding {index}.verification")
    return raw


def evaluate_evidence(payload: Any) -> dict[str, Any]:
    """Return transparent metrics and a release-gate decision."""

    require(isinstance(payload, dict), "evidence root must be an object")
    require(not (set(payload) - {"schema_version", "sessions", "findings"}), "evidence root contains undeclared fields")
    require(payload.get("schema_version") == "1.0", "schema_version must be 1.0")
    sessions_raw = payload.get("sessions")
    findings_raw = payload.get("findings")
    require(isinstance(sessions_raw, list), "sessions must be a list")
    require(isinstance(findings_raw, list), "findings must be a list")
    require(len(sessions_raw) == 5, "exactly five observed sessions are required")

    sessions = [validate_session(item, index) for index, item in enumerate(sessions_raw, 1)]
    findings = [validate_finding(item, index) for index, item in enumerate(findings_raw, 1)]
    codes = [item["participant_code"] for item in sessions]
    require(len(codes) == len(set(codes)), "participant codes must be unique")
    finding_by_id = {item["id"]: item for item in findings}
    require(len(finding_by_id) == len(findings), "finding IDs must be unique")

    occurrence_count = {finding_id: 0 for finding_id in finding_by_id}
    for session in sessions:
        unknown = set(session["finding_ids"]) - set(finding_by_id)
        require(not unknown, f"session {session['participant_code']} references unknown findings")
        for finding_id in session["finding_ids"]:
            occurrence_count[finding_id] += 1

    core_completed = sum(REQUIRED_TASKS.issubset(set(item["tasks_completed"])) for item in sessions)
    median_seconds = statistics.median(item["first_useful_result_seconds"] for item in sessions)
    recurring = [finding_id for finding_id, count in occurrence_count.items() if count >= 2]
    unresolved_recurring = [
        finding_id for finding_id in recurring if finding_by_id[finding_id]["status"] != "resolved"
    ]
    gates = {
        "core_journey": core_completed >= 4,
        "eligibility_comprehension": all(item["eligibility_understood"] for item in sessions),
        "time_to_first_result": median_seconds < 300,
        "privacy_comprehension": all(item["privacy_understood"] for item in sessions),
        "keyboard_accessibility": any(item["keyboard_only_check"] for item in sessions),
        "recurring_findings_resolved": not unresolved_recurring,
    }
    return {
        "sessions_completed": len(sessions),
        "core_journeys_completed": core_completed,
        "median_first_useful_result_seconds": median_seconds,
        "recurring_findings": recurring,
        "unresolved_recurring_findings": unresolved_recurring,
        "gates": gates,
        "release_ready": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("docs/usability_sessions.json"),
        help="Path to the anonymized session evidence JSON",
    )
    args = parser.parse_args()
    try:
        payload = json.loads(args.path.read_text())
        report = evaluate_evidence(payload)
    except (OSError, json.JSONDecodeError, EvidenceError) as error:
        print(json.dumps({"release_ready": False, "error": str(error)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
