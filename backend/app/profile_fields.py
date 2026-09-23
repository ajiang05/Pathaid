"""Profile-field definitions and validation shared by API consumers."""

import math

from fastapi import HTTPException


# These are the assistance filters supported by the first version of Pathaid.
CATEGORIES = {"scholarships", "grants", "food", "emergency", "housing"}

# This registry is the source of truth for profile answers. The frontend will
# eventually use the same metadata to render questions, while the backend uses
# it to reject unknown fields and invalid values.
#
# `sensitive` identifies fields that require extra care in UI and logging.
# `progressive` means the initial intake should ask the question only when a
# candidate program's reviewed eligibility rules actually need the answer.
FIELDS = {
    "school": {"type": "string", "question": "What college do you attend?", "sensitive": False, "progressive": False},
    "state": {"type": "choice", "values": ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"], "question": "What state is your school in?", "sensitive": False, "progressive": False},
    "study_level": {"type": "choice", "values": ["undergraduate", "graduate"], "question": "What is your study level?", "sensitive": False, "progressive": False},
    "enrollment": {"type": "choice", "values": ["full_time", "part_time"], "question": "What is your enrollment status?", "sensitive": False, "progressive": False},
    "assistance_categories": {"type": "multi_choice", "values": sorted(CATEGORIES), "question": "What help are you looking for?", "sensitive": False, "progressive": False},
    "income_range": {"type": "choice", "values": ["under_25k", "25k_50k", "50k_75k", "75k_100k", "over_100k"], "question": "What is your household income range?", "sensitive": True, "progressive": True},
    "pell_eligible": {"type": "boolean", "question": "Are you eligible for a Pell Grant?", "sensitive": True, "progressive": True},
    "student_aid_index": {"type": "integer", "question": "What is your Student Aid Index?", "sensitive": True, "progressive": True},
    "ethnicity": {"type": "string", "question": "How do you describe your ethnicity?", "sensitive": True, "progressive": True},
    "citizenship_status": {"type": "choice", "values": ["us_citizen", "permanent_resident", "international", "other"], "question": "What is your citizenship or immigration status?", "sensitive": True, "progressive": True},
    "major": {"type": "string", "question": "What is your major or field of study?", "sensitive": False, "progressive": True},
    "class_year": {"type": "choice", "values": ["first", "second", "third", "fourth", "fifth_or_later"], "question": "What is your class year?", "sensitive": False, "progressive": True},
    "gpa": {"type": "number", "question": "What is your GPA?", "sensitive": False, "progressive": True},
    "gpa_scale": {"type": "number", "question": "What scale is your GPA on?", "sensitive": False, "progressive": True},
}

# Store common spellings under one canonical institution name so matching does
# not treat them as different schools.
UMASS_ALIASES = {"umass amherst", "university of massachusetts amherst", "u mass amherst", "umass"}


def invalid(field: str) -> None:
    """Raise a value-free error so private answers are never echoed back."""

    raise HTTPException(status_code=422, detail={"field": field, "message": "Invalid answer"})


def validate_profile_patch(patch: dict, current: dict) -> dict:
    """Validate a partial update and return a new complete profile dictionary.

    A value of ``None`` removes an existing answer. The function copies the
    current profile first, so validation never partially mutates stored data.
    """

    if not isinstance(patch, dict):
        invalid("profile")
    updated = current.copy()
    for field, value in patch.items():
        # An allowlist prevents clients from storing arbitrary keys in the JSON
        # profile or bypassing the declared field types.
        if field not in FIELDS:
            invalid(field)
        # Null represents "remove this saved answer" rather than an answer.
        if value is None:
            updated.pop(field, None)
            continue
        spec = FIELDS[field]
        kind = spec["type"]
        # Each branch validates the JSON value against its registry type.
        if kind == "string":
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
                invalid(field)
            value = value.strip()
        elif kind == "choice":
            if not isinstance(value, str) or value not in spec["values"]:
                invalid(field)
        elif kind == "multi_choice":
            if not isinstance(value, list) or not value or len(value) > len(spec["values"]) or any(not isinstance(v, str) or v not in spec["values"] for v in value) or len(set(value)) != len(value):
                invalid(field)
        elif kind == "boolean":
            if not isinstance(value, bool):
                invalid(field)
        elif kind == "integer":
            # `type(value) is int` deliberately rejects booleans because bool
            # is a subclass of int in Python.
            if type(value) is not int or not -1500 <= value <= 999999:
                invalid(field)
        elif kind == "number":
            # Reject NaN and infinity as well as values outside useful bounds.
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                invalid(field)
        # Normalize only known aliases. Other schools remain exactly as the
        # student entered them and do not receive UMass-specific coverage.
        if field == "school" and value.casefold() in UMASS_ALIASES:
            value = "University of Massachusetts Amherst"
        updated[field] = value
    # GPA is meaningful only in relation to its declared scale. This check does
    # not convert between scales or assume that every school uses a 4.0 scale.
    if "gpa" in updated and "gpa_scale" in updated and updated["gpa"] > updated["gpa_scale"]:
        invalid("gpa")
    return updated
