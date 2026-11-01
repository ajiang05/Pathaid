"""Typed single-user profile registry with explicit unknown semantics."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import date
from typing import Any, Mapping


US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]
UNKNOWN_VALUE = {"status": "unknown"}
UMASS_ALIASES = {"umass amherst", "university of massachusetts amherst", "u mass amherst", "umass"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def field(section: str, kind: str, label: str, *, sensitive: bool = False, values: list[str] | None = None, core: bool = False, maximum: int = 120) -> dict[str, Any]:
    """Build consistent public metadata for one saved profile field."""

    result: dict[str, Any] = {
        "section": section,
        "type": kind,
        "label": label,
        "question": label,
        "sensitive": sensitive,
        "optional": not core,
        "allow_unknown": True,
        "maximum": maximum,
    }
    if values is not None:
        result["values"] = values
    return result


FIELDS: dict[str, dict[str, Any]] = {
    # Identity and contact
    "first_name": field("identity", "string", "First name"),
    "last_name": field("identity", "string", "Last name"),
    "email": field("identity", "email", "Email address", sensitive=True),
    "phone": field("identity", "string", "Phone number", sensitive=True, maximum=40),
    "date_of_birth": field("identity", "date", "Date of birth", sensitive=True),
    # School and three distinct location concepts
    "school": field("school", "string", "Current college or university", core=True),
    "school_id": field("school", "string", "Institution identifier"),
    "school_city": field("school", "string", "School city"),
    "school_state": field("school", "choice", "School state", values=US_STATES, core=True),
    "current_city": field("current_residence", "string", "Current city"),
    "current_state": field("current_residence", "choice", "Current residence state", values=US_STATES),
    "current_postal_code": field("current_residence", "string", "Current ZIP code", sensitive=True, maximum=12),
    "permanent_city": field("permanent_residence", "string", "Permanent or home city"),
    "permanent_state": field("permanent_residence", "choice", "Permanent or home state", values=US_STATES),
    "permanent_postal_code": field("permanent_residence", "string", "Permanent or home ZIP code", sensitive=True, maximum=12),
    # Academics
    "study_level": field("academics", "choice", "Study level", values=["undergraduate", "graduate"], core=True),
    "enrollment": field("academics", "choice", "Enrollment status", values=["full_time", "part_time"], core=True),
    "class_year": field("academics", "choice", "Class year", values=["first", "second", "third", "fourth", "fifth_or_later"]),
    "degree_type": field("academics", "choice", "Degree type", values=["associate", "bachelor", "other"]),
    "major": field("academics", "string", "Major or field of study"),
    "minor": field("academics", "string", "Minor"),
    "gpa": field("academics", "number", "GPA"),
    "gpa_scale": field("academics", "number", "GPA scale"),
    "credits_completed": field("academics", "integer", "Credits completed"),
    "expected_graduation": field("academics", "month", "Expected graduation month"),
    # Sensitive and optional scholarship criteria
    "income_range": field("eligibility", "choice", "Household income range", sensitive=True, values=["under_25k", "25k_50k", "50k_75k", "75k_100k", "over_100k"]),
    "pell_eligible": field("eligibility", "boolean", "Pell Grant eligible", sensitive=True),
    "student_aid_index": field("eligibility", "integer", "Student Aid Index", sensitive=True),
    "ethnicity": field("eligibility", "string", "Ethnicity", sensitive=True),
    "race": field("eligibility", "multi_choice", "Race", sensitive=True, values=["american_indian_or_alaska_native", "asian", "black_or_african_american", "middle_eastern_or_north_african", "native_hawaiian_or_pacific_islander", "white", "other"]),
    "gender": field("eligibility", "choice", "Gender", sensitive=True, values=["woman", "man", "nonbinary", "another_identity"]),
    "disability_status": field("eligibility", "boolean", "Person with a disability", sensitive=True),
    "first_generation_student": field("eligibility", "boolean", "First-generation college student", sensitive=True),
    "citizenship_status": field("eligibility", "choice", "Citizenship or residency status", sensitive=True, values=["us_citizen", "permanent_resident", "international", "other"]),
    "veteran_status": field("eligibility", "boolean", "Veteran or active-duty service member", sensitive=True),
}

# Experiences are edited through their own structured collection rather than a
# scalar profile control, but remain a first-class deterministic rule input.
MATCH_FIELDS: dict[str, dict[str, Any]] = {
    **FIELDS,
    "experiences": {
        "section": "experiences",
        "type": "experience_list",
        "label": "Structured experiences",
        "question": "Structured experiences",
        "sensitive": False,
        "optional": True,
        "allow_unknown": False,
    },
}

SECTIONS = [
    {"id": "identity", "label": "Identity and contact"},
    {"id": "school", "label": "Current school"},
    {"id": "current_residence", "label": "Current residence"},
    {"id": "permanent_residence", "label": "Permanent or home residence"},
    {"id": "academics", "label": "Academics"},
    {"id": "eligibility", "label": "Optional eligibility information"},
]
CORE_FIELDS = tuple(name for name, spec in FIELDS.items() if not spec["optional"])


class ProfileValidationError(ValueError):
    """Value-free validation failure safe to return to the local UI."""

    def __init__(self, field_name: str):
        self.field_name = field_name
        super().__init__("Invalid profile answer")


def is_unknown(value: object) -> bool:
    """Recognize only the canonical explicit-unknown object."""

    return isinstance(value, Mapping) and dict(value) == UNKNOWN_VALUE


def _invalid(name: str) -> None:
    raise ProfileValidationError(name)


def _validate_known(name: str, value: object, spec: Mapping[str, Any]) -> object:
    kind = spec["type"]
    if kind in {"string", "email"}:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= spec["maximum"]:
            _invalid(name)
        value = value.strip()
        if kind == "email" and not EMAIL_PATTERN.fullmatch(value):
            _invalid(name)
    elif kind == "choice":
        if not isinstance(value, str) or value not in spec["values"]:
            _invalid(name)
    elif kind == "multi_choice":
        if not isinstance(value, list) or not value or len(value) > len(spec["values"]):
            _invalid(name)
        if any(not isinstance(item, str) or item not in spec["values"] for item in value) or len(set(value)) != len(value):
            _invalid(name)
        value = sorted(value)
    elif kind == "boolean":
        if not isinstance(value, bool):
            _invalid(name)
    elif kind == "integer":
        if type(value) is not int or not -1500 <= value <= 999999:
            _invalid(name)
    elif kind == "number":
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
            _invalid(name)
    elif kind == "date":
        if not isinstance(value, str):
            _invalid(name)
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            _invalid(name)
        if parsed > date.today():
            _invalid(name)
    elif kind == "month":
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            _invalid(name)
    else:  # pragma: no cover - registry authoring failure
        raise RuntimeError(f"Unsupported profile field type: {kind}")
    if name == "school" and isinstance(value, str) and value.casefold() in UMASS_ALIASES:
        value = "University of Massachusetts Amherst"
    return value


def validate_profile_patch(patch: object, current: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a partial patch while preserving absent versus explicit unknown."""

    if not isinstance(patch, dict):
        _invalid("profile")
    updated = deepcopy(dict(current))
    for name, raw_value in patch.items():
        if name not in FIELDS:
            _invalid(name)
        if raw_value is None:
            updated.pop(name, None)
        elif is_unknown(raw_value):
            updated[name] = dict(UNKNOWN_VALUE)
        else:
            updated[name] = _validate_known(name, raw_value, FIELDS[name])
    gpa = updated.get("gpa")
    scale = updated.get("gpa_scale")
    if not is_unknown(gpa) and not is_unknown(scale) and isinstance(gpa, (int, float)) and isinstance(scale, (int, float)) and gpa > scale:
        _invalid("gpa")
    return updated


def completeness(fields: Mapping[str, Any]) -> dict[str, int]:
    """Count known, explicit-unknown, and unanswered fields deterministically."""

    known = sum(name in fields and not is_unknown(fields[name]) for name in FIELDS)
    unknown = sum(name in fields and is_unknown(fields[name]) for name in FIELDS)
    total = len(FIELDS)
    return {
        "known": known,
        "unknown": unknown,
        "unanswered": total - known - unknown,
        "total": total,
        "percent_known": round(known * 100 / total),
    }
