"""Tests for the strict extraction output contract."""

import pytest
from pydantic import ValidationError

from app.extraction_schemas import ExtractedProgramDraft


def valid_draft() -> dict:
    """Return a minimal valid proposal that individual tests can modify."""

    evidence = {"snapshot_id": "snapshot-1", "excerpt": "Applicants must have a 3.0 GPA."}
    return {
        "name": "Community Scholars Award",
        "description": "A scholarship for eligible college students.",
        "categories": ["scholarships"],
        "coverage": {"national": True, "states": [], "institutions": []},
        "checklist": [{"label": "Submit a transcript", "required": True, "evidence": evidence}],
        "eligibility_tree": {
            "type": "condition",
            "field": "gpa",
            "operator": "gte",
            "value": 3.0,
            "evidence": evidence,
            "exceptions_complete": True,
        },
        "coverage_complete": True,
        "award_cycle": "2027",
        "application_deadline": "2027-03-01T17:00:00-05:00",
        "deadline_timezone": "America/New_York",
        "application_availability": "open",
        "assistance_amount": "$2,500",
        "selection_factors": [],
        "application_url": "https://example.edu/apply",
        "unresolved_conditions": [],
    }


def test_schema_accepts_a_complete_evidence_backed_draft():
    """The contract preserves typed rules and source evidence."""

    draft = ExtractedProgramDraft.model_validate(valid_draft())

    assert draft.eligibility_tree.field == "gpa"
    assert draft.eligibility_tree.evidence.snapshot_id == "snapshot-1"


@pytest.mark.parametrize("field", ["invented", "provider_url", "student_profile"])
def test_schema_rejects_unapproved_top_level_fields(field: str):
    """Model output cannot expand its own authority or include student data."""

    proposal = valid_draft()
    proposal[field] = "not allowed"

    with pytest.raises(ValidationError):
        ExtractedProgramDraft.model_validate(proposal)


def test_schema_keeps_selection_preferences_outside_eligibility_rules():
    """Selection preferences have their own evidence-backed collection."""

    proposal = valid_draft()
    proposal["selection_factors"] = [
        {
            "description": "Preference is given to students with community service.",
            "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Preference is given to volunteers."},
        }
    ]

    draft = ExtractedProgramDraft.model_validate(proposal)

    assert len(draft.selection_factors) == 1
    assert draft.eligibility_tree.field == "gpa"


def test_incomplete_coverage_requires_an_explanation():
    """An incomplete proposal cannot conceal missing or ambiguous requirements."""

    proposal = valid_draft()
    proposal["coverage_complete"] = False

    with pytest.raises(ValidationError, match="incomplete coverage"):
        ExtractedProgramDraft.model_validate(proposal)


def test_unsupported_requirement_explains_incomplete_coverage():
    """Unsupported source logic remains explicit for reviewer handling."""

    proposal = valid_draft()
    proposal["coverage_complete"] = False
    proposal["eligibility_tree"] = {
        "type": "unsupported",
        "description": "Applicant must demonstrate exceptional promise.",
        "evidence": {"snapshot_id": "snapshot-1", "excerpt": "demonstrate exceptional promise"},
    }

    draft = ExtractedProgramDraft.model_validate(proposal)

    assert draft.eligibility_tree.type == "unsupported"


def test_generated_json_schema_is_recursive_and_closed():
    """The schema supplied to Structured Outputs forbids additional properties."""

    schema = ExtractedProgramDraft.model_json_schema()

    assert schema["additionalProperties"] is False
    assert "RuleGroup" in schema["$defs"]
