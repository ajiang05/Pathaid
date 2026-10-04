"""Tests for deterministic validation after schema-constrained extraction."""

from dataclasses import dataclass

from app.extraction_schemas import ExtractedProgramDraft
from app.extraction_validation import validate_extracted_draft


SOURCE = (
    "Community Scholars Award. Applicants must have a 3.0 GPA. "
    "Submit a transcript. Preference is given to volunteers."
)


@dataclass(frozen=True)
class Snapshot:
    """Small snapshot stand-in that satisfies the validator protocol."""

    id: str = "snapshot-1"
    source_text: str = SOURCE


def proposal() -> dict:
    """Return one valid proposal with evidence copied exactly from SOURCE."""

    return {
        "name": "Community Scholars Award",
        "description": "A scholarship for college students.",
        "categories": ["scholarships"],
        "coverage": {"national": True, "states": [], "institutions": []},
        "checklist": [
            {
                "label": "Submit a transcript",
                "required": True,
                "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Submit a transcript."},
            }
        ],
        "eligibility_tree": {
            "type": "condition",
            "field": "gpa",
            "operator": "gte",
            "value": 3.0,
            "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Applicants must have a 3.0 GPA."},
            "exceptions_complete": True,
        },
        "coverage_complete": True,
        "award_cycle": "2027",
        "application_deadline": "2027-03-01T17:00:00-05:00",
        "deadline_timezone": "America/New_York",
        "application_availability": "open",
        "assistance_amount": "$2,500",
        "selection_factors": [
            {
                "description": "Preference for volunteers",
                "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Preference is given to volunteers."},
            }
        ],
        "application_url": "https://example.edu/apply",
        "unresolved_conditions": [],
    }


def finding_codes(result) -> set[str]:
    """Return finding codes for concise assertions."""

    return {finding.code for finding in result.findings}


def test_validates_a_supported_evidence_backed_proposal():
    """Known fields, typed operands, and exact excerpts enter review cleanly."""

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(proposal()), Snapshot())

    assert result.is_valid
    assert result.findings == ()


def test_invented_evidence_blocks_the_proposal():
    """A plausible excerpt still fails when it is absent from retained text."""

    data = proposal()
    data["eligibility_tree"]["evidence"]["excerpt"] = "Applicants must have a 3.5 GPA."

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert not result.is_valid
    assert "excerpt_not_found" in finding_codes(result)


def test_evidence_from_another_snapshot_blocks_the_proposal():
    """Matching text cannot be attributed to a different source snapshot."""

    data = proposal()
    data["checklist"][0]["evidence"]["snapshot_id"] = "snapshot-2"

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert not result.is_valid
    assert "wrong_snapshot" in finding_codes(result)


def test_unknown_rule_field_blocks_the_proposal():
    """Only profile fields in the shared registry can become answerable rules."""

    data = proposal()
    data["eligibility_tree"]["field"] = "volunteer_hours"

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert not result.is_valid
    assert "invalid_rule" in finding_codes(result)


def test_invalid_operand_type_blocks_the_proposal():
    """Numeric comparisons cannot carry free-form model text as an operand."""

    data = proposal()
    data["eligibility_tree"]["value"] = "three point zero"

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert not result.is_valid
    assert "invalid_rule" in finding_codes(result)


def test_unsupported_logic_is_preserved_as_a_warning():
    """Ambiguous mandatory logic reaches review without becoming eligibility."""

    data = proposal()
    data["coverage_complete"] = False
    data["eligibility_tree"] = {
        "type": "unsupported",
        "description": "Applicant must demonstrate exceptional promise.",
        "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Community Scholars Award."},
    }

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert result.is_valid
    assert "unsupported_logic" in finding_codes(result)


def test_bad_coverage_deadline_and_url_have_explicit_findings():
    """Catalog fields receive deterministic checks outside the model schema."""

    data = proposal()
    data["coverage"] = {"national": False, "states": ["XX"], "institutions": []}
    data["application_deadline"] = "March someday"
    data["application_url"] = "file:///tmp/apply"

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert not result.is_valid
    assert {"invalid_state", "invalid_deadline", "invalid_application_url"} <= finding_codes(result)


def test_missing_named_timezone_is_visible_to_reviewers():
    """A deadline without source timezone context is retained with a warning."""

    data = proposal()
    data["deadline_timezone"] = None

    result = validate_extracted_draft(ExtractedProgramDraft.model_validate(data), Snapshot())

    assert result.is_valid
    assert "missing_deadline_timezone" in finding_codes(result)
