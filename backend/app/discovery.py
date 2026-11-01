"""Stable ordering for current verified scholarship matches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from .eligibility import EligibilityLabel


MATCH_ORDER = {EligibilityLabel.STRONG.value: 0, EligibilityLabel.POSSIBLE.value: 1}


@dataclass(frozen=True)
class RankingRecord:
    scholarship_id: str
    name: str
    match_label: str
    availability: str
    deadline: datetime | None
    source_freshness: datetime | None
    relevance_score: int


@dataclass(frozen=True)
class RankedRecord:
    record: RankingRecord
    ranking_factors: Mapping[str, str]


def _utc_timestamp(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def rank_current_matches(records: list[RankingRecord]) -> list[RankedRecord]:
    """Filter non-actionable records and apply every nullable sort key explicitly."""

    ranked: list[tuple[tuple, RankedRecord]] = []
    for record in records:
        if record.match_label not in {label.value for label in EligibilityLabel}:
            raise ValueError(f"Unknown match label: {record.match_label!r}")
        # Current Discover never treats unknown, closed, expired, disappeared,
        # or otherwise unverifiable availability as actionable.
        if record.availability != "verified_open" or record.match_label == EligibilityLabel.NOT_MATCH.value:
            continue
        deadline_known = record.deadline is not None
        freshness_known = record.source_freshness is not None
        factors = {
            "match_class": record.match_label,
            "availability": record.availability,
            "deadline": record.deadline.isoformat() if deadline_known else "unknown",
            "source_freshness": record.source_freshness.isoformat() if freshness_known else "unknown",
            "relevance": str(record.relevance_score),
            "stable_id": record.scholarship_id,
        }
        key = (
            MATCH_ORDER[record.match_label],
            0 if deadline_known else 1,
            _utc_timestamp(record.deadline) if record.deadline else float("inf"),
            0 if freshness_known else 1,
            -_utc_timestamp(record.source_freshness) if record.source_freshness else float("inf"),
            -record.relevance_score,
            record.scholarship_id,
        )
        ranked.append((key, RankedRecord(record, factors)))
    return [item for _, item in sorted(ranked, key=lambda pair: pair[0])]
