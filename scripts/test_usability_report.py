"""Tests for objective usability release-gate calculations."""

from copy import deepcopy
import unittest

from usability_report import EvidenceError, evaluate_evidence


def passing_payload() -> dict:
    sessions = []
    for number in range(1, 6):
        sessions.append(
            {
                "participant_code": f"P{number:02d}",
                "date": f"2026-11-{number:02d}",
                "device_browser": "Laptop / Chromium",
                "tasks_completed": list(range(1, 9)),
                "first_useful_result_seconds": 180 + number,
                "eligibility_understood": True,
                "privacy_understood": True,
                "help_given": "None",
                "keyboard_only_check": number == 1,
                "assistive_technology": None,
                "finding_ids": ["F-01"] if number <= 2 else [],
            }
        )
    return {
        "schema_version": "1.0",
        "sessions": sessions,
        "findings": [
            {
                "id": "F-01",
                "description": "A recurring synthetic finding.",
                "severity": "medium",
                "status": "resolved",
                "resolution": "A tested correction was made.",
                "verification": "Both affected tasks were repeated successfully.",
            }
        ],
    }


class UsabilityReportTests(unittest.TestCase):
    def test_passing_evidence_meets_every_gate(self):
        report = evaluate_evidence(passing_payload())
        self.assertTrue(report["release_ready"])
        self.assertEqual(report["sessions_completed"], 5)
        self.assertEqual(report["core_journeys_completed"], 5)

    def test_open_recurring_finding_blocks_release(self):
        payload = passing_payload()
        payload["findings"][0]["status"] = "open"
        report = evaluate_evidence(payload)
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["unresolved_recurring_findings"], ["F-01"])

    def test_four_complete_core_journeys_are_sufficient(self):
        payload = passing_payload()
        payload["sessions"][4]["tasks_completed"] = [1, 2, 3]
        report = evaluate_evidence(payload)
        self.assertTrue(report["gates"]["core_journey"])
        self.assertEqual(report["core_journeys_completed"], 4)

    def test_incomplete_or_identifying_record_is_rejected(self):
        payload = passing_payload()
        payload["sessions"] = payload["sessions"][:4]
        with self.assertRaises(EvidenceError):
            evaluate_evidence(payload)

        payload = passing_payload()
        payload["sessions"][0]["email"] = "must-not-be-recorded@example.com"
        with self.assertRaises(EvidenceError):
            evaluate_evidence(payload)

        payload = passing_payload()
        payload["sessions"][0]["participant_code"] = "Student Name"
        with self.assertRaises(EvidenceError):
            evaluate_evidence(payload)

    def test_slow_median_and_missing_comprehension_fail_their_gates(self):
        payload = deepcopy(passing_payload())
        for session in payload["sessions"]:
            session["first_useful_result_seconds"] = 300
        payload["sessions"][0]["eligibility_understood"] = False
        payload["sessions"][1]["privacy_understood"] = False
        report = evaluate_evidence(payload)
        self.assertFalse(report["gates"]["time_to_first_result"])
        self.assertFalse(report["gates"]["eligibility_comprehension"])
        self.assertFalse(report["gates"]["privacy_comprehension"])


if __name__ == "__main__":
    unittest.main()
