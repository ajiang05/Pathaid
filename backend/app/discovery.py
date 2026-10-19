"""Deterministic coverage filtering and ordering for student discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


ELIGIBILITY_ORDER = {
    "Likely eligible": 0,
    "Need more information": 1,
    "Likely ineligible": 2,
}
AVAILABILITY_ORDER = {"open": 0, "unknown": 1, "closed": 2}
AVAILABILITY_SECTIONS = {
    "open": "Open opportunities",
    "unknown": "Confirm availability",
    "closed": "Closed opportunities",
}


@dataclass(frozen=True)
class CoverageResult:
    """Whether reviewed coverage applies and how specifically it matches."""

    applicable: bool
    relevance: str
    relevance_score: int


@dataclass(frozen=True)
class RankingRecord:
    """Minimum reviewed and evaluated data required for deterministic ranking."""

    program_id: str
    name: str
    eligibility_label: str
    application_availability: str
    application_deadline: datetime | None
    coverage: Mapping[str, Any]


@dataclass(frozen=True)
class RankedRecord:
    """A candidate plus the factors that explain its final position."""

    record: RankingRecord
    section: str
    relevance: str
    ranking_factors: Mapping[str, str]


def match_coverage(coverage: Mapping[str, Any], profile: Mapping[str, Any]) -> CoverageResult:
    """Compare explicit profile answers with reviewed catalog coverage.

    Institution and state lists are alternatives: matching either makes the
    resource applicable. Missing student answers keep coverage unresolved and
    included, while an explicit mismatch excludes a non-national resource.
    """

    institutions = coverage.get("institutions", [])
    states = coverage.get("states", [])
    national = coverage.get("type") == "national" or coverage.get("national") is True
    school = profile.get("school")
    state = profile.get("state")

    if school and isinstance(institutions, list):
        normalized_school = school.casefold()
        if any(isinstance(item, str) and item.casefold() == normalized_school for item in institutions):
            return CoverageResult(True, "institution", 3)
    if state and isinstance(states, list) and state in states:
        return CoverageResult(True, "state", 2)
    if national:
        return CoverageResult(True, "national", 1)

    has_institution_rules = isinstance(institutions, list) and bool(institutions)
    has_state_rules = isinstance(states, list) and bool(states)
    if (has_institution_rules and not school) or (has_state_rules and not state):
        return CoverageResult(True, "coverage unresolved", 0)
    if has_institution_rules or has_state_rules:
        return CoverageResult(False, "outside reviewed coverage", -1)
    # Unrecognized or incomplete coverage metadata cannot support exclusion.
    return CoverageResult(True, "coverage unresolved", 0)


def rank_records(records: list[RankingRecord], profile: Mapping[str, Any]) -> list[RankedRecord]:
    """Filter by coverage and order candidates using only transparent factors."""

    ranked: list[tuple[tuple, RankedRecord]] = []
    for record in records:
        if record.eligibility_label not in ELIGIBILITY_ORDER:
            raise ValueError(f"Unknown eligibility label: {record.eligibility_label!r}")
        if record.application_availability not in AVAILABILITY_ORDER:
            raise ValueError(f"Unknown application availability: {record.application_availability!r}")

        coverage = match_coverage(record.coverage, profile)
        if not coverage.applicable:
            continue

        availability = record.application_availability
        # Deadlines determine order only for verified-open opportunities. An
        # unknown availability cannot be promoted based on an unverified date.
        deadline_known = availability == "open" and record.application_deadline is not None
        if deadline_known:
            deadline_key = _utc_timestamp(record.application_deadline)
            deadline_factor = record.application_deadline.isoformat()
        elif availability == "open":
            deadline_key = float("inf")
            deadline_factor = "unknown"
        else:
            deadline_key = 0.0
            deadline_factor = "not used for this availability section"

        section = AVAILABILITY_SECTIONS[availability]
        factors = {
            "eligibility_group": record.eligibility_label,
            "availability_section": section,
            "deadline": deadline_factor,
            "relevance": coverage.relevance,
            "name_tiebreaker": record.name,
        }
        result = RankedRecord(record, section, coverage.relevance, factors)
        key = (
            ELIGIBILITY_ORDER[record.eligibility_label],
            AVAILABILITY_ORDER[availability],
            0 if deadline_known else 1,
            deadline_key,
            -coverage.relevance_score,
            record.name.casefold(),
            record.program_id,
        )
        ranked.append((key, result))

    return [result for _, result in sorted(ranked, key=lambda item: item[0])]


def _utc_timestamp(value: datetime) -> float:
    """Create a comparable instant from aware or SQLite-naive datetimes."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()
