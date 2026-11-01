"""Combine pure eligibility with stable current-match ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .discovery import RankingRecord, rank_current_matches
from .eligibility import EligibilityResult, evaluate_eligibility


@dataclass(frozen=True)
class ScholarshipCandidate:
    scholarship_id: str
    version_id: str
    name: str
    hard_requirements: Mapping[str, Any]
    requirements_complete: bool
    availability: str
    deadline: datetime | None
    source_freshness: datetime | None
    relevance_score: int = 0
    selection_preferences: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class MatchResult:
    candidate: ScholarshipCandidate
    eligibility: EligibilityResult
    ranking_factors: Mapping[str, str] | None = None


def evaluate_candidates(candidates: list[ScholarshipCandidate], profile: Mapping[str, Any], field_registry: Mapping[str, Mapping[str, Any]]) -> tuple[MatchResult, ...]:
    """Evaluate every candidate, then rank only verified actionable matches."""

    evaluations = {
        candidate.scholarship_id: evaluate_eligibility(
            revision_id=candidate.version_id,
            rule=candidate.hard_requirements,
            profile=profile,
            field_registry=field_registry,
            coverage_complete=candidate.requirements_complete,
        )
        for candidate in candidates
    }
    ranked = rank_current_matches([
        RankingRecord(
            scholarship_id=candidate.scholarship_id,
            name=candidate.name,
            match_label=evaluations[candidate.scholarship_id].label.value,
            availability=candidate.availability,
            deadline=candidate.deadline,
            source_freshness=candidate.source_freshness,
            relevance_score=candidate.relevance_score,
        )
        for candidate in candidates
    ])
    factors = {item.record.scholarship_id: item.ranking_factors for item in ranked}
    candidate_by_id = {candidate.scholarship_id: candidate for candidate in candidates}
    current = [MatchResult(candidate_by_id[item.record.scholarship_id], evaluations[item.record.scholarship_id], item.ranking_factors) for item in ranked]
    hidden = [
        MatchResult(candidate, evaluations[candidate.scholarship_id])
        for candidate in sorted(candidates, key=lambda item: item.scholarship_id)
        if candidate.scholarship_id not in factors
    ]
    return tuple(current + hidden)

