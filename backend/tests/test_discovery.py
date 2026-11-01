"""Tests for strict matching and stable current scholarship ordering."""

import json
from datetime import datetime, timezone

from app.discovery import RankingRecord, rank_current_matches
from app.eligibility import EligibilityLabel
from app.matching import ScholarshipCandidate, evaluate_candidates


def record(identifier: str, *, label="Strong match", availability="verified_open", deadline=None, freshness=None, relevance=0):
    return RankingRecord(identifier, identifier.title(), label, availability, deadline, freshness, relevance)


def test_only_verified_strong_and_possible_matches_are_current():
    records = [
        record("strong"),
        record("possible", label="Possible match"),
        record("failed", label="Not a match"),
        record("unknown", availability="unknown"),
        record("closed", availability="closed"),
        record("unavailable", availability="unavailable"),
    ]
    assert [item.record.scholarship_id for item in rank_current_matches(records)] == ["strong", "possible"]


def test_ranking_has_explicit_nullable_keys_and_stable_id_tiebreaker():
    near = datetime(2027, 1, 1, tzinfo=timezone.utc)
    far = datetime(2027, 2, 1, tzinfo=timezone.utc)
    fresh = datetime(2026, 12, 1, tzinfo=timezone.utc)
    stale = datetime(2026, 11, 1, tzinfo=timezone.utc)
    records = [
        record("possible", label="Possible match", deadline=near, freshness=fresh, relevance=100),
        record("unknown-deadline", freshness=fresh, relevance=100),
        record("far", deadline=far, freshness=fresh, relevance=100),
        record("near-stale", deadline=near, freshness=stale, relevance=100),
        record("near-fresh-low", deadline=near, freshness=fresh, relevance=1),
        record("near-fresh-high-b", deadline=near, freshness=fresh, relevance=10),
        record("near-fresh-high-a", deadline=near, freshness=fresh, relevance=10),
    ]
    ranked = rank_current_matches(records)
    assert [item.record.scholarship_id for item in ranked] == [
        "near-fresh-high-a",
        "near-fresh-high-b",
        "near-fresh-low",
        "near-stale",
        "far",
        "unknown-deadline",
        "possible",
    ]
    assert ranked[5].ranking_factors["deadline"] == "unknown"
    assert ranked[0].ranking_factors["stable_id"] == "near-fresh-high-a"


def test_same_inputs_produce_byte_stable_ordered_ids():
    records = [record("b"), record("a"), record("c", label="Possible match")]
    first = [item.record.scholarship_id for item in rank_current_matches(records)]
    second = [item.record.scholarship_id for item in rank_current_matches(records)]
    assert first == second == ["a", "b", "c"]


def test_same_fixture_produces_byte_stable_explanations_and_ranking_factors():
    evidence = {"snapshot_id": "fixture", "excerpt": "Applicants need a 3.0 GPA."}
    candidates = [ScholarshipCandidate(
        scholarship_id="stable-scholarship",
        version_id="stable-cycle",
        name="Stable Scholarship",
        hard_requirements={"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": evidence},
        requirements_complete=True,
        availability="verified_open",
        deadline=datetime(2027, 3, 1, tzinfo=timezone.utc),
        source_freshness=datetime(2026, 11, 1, tzinfo=timezone.utc),
        relevance_score=7,
    )]

    def snapshot():
        result = evaluate_candidates(candidates, {"gpa": 3.5}, {"gpa": {"type": "number"}})[0]
        return json.dumps({
            "id": result.candidate.scholarship_id,
            "label": result.eligibility.label.value,
            "truth": result.eligibility.truth.value,
            "reasons": [item.reason for item in result.eligibility.criteria],
            "ranking": result.ranking_factors,
        }, sort_keys=True, separators=(",", ":"))

    assert snapshot() == snapshot()


def test_selection_preferences_never_override_hard_eligibility():
    evidence = {"snapshot_id": "fixture", "excerpt": "Synthetic GPA requirement."}
    candidate = ScholarshipCandidate(
        scholarship_id="synthetic",
        version_id="v1",
        name="Synthetic Scholarship",
        hard_requirements={"type": "condition", "field": "gpa", "operator": "gte", "value": 3.5, "evidence": evidence},
        requirements_complete=True,
        availability="verified_open",
        deadline=None,
        source_freshness=None,
        relevance_score=100,
        selection_preferences=({"field": "leadership", "weight": "high"},),
    )
    result = evaluate_candidates([candidate], {"gpa": 3.0}, {"gpa": {"type": "number"}})[0]
    assert result.eligibility.label is EligibilityLabel.NOT_MATCH
    assert result.ranking_factors is None


def test_fixture_profiles_produce_strong_possible_and_not_match():
    evidence = {"snapshot_id": "fixture", "excerpt": "Synthetic state and GPA requirements."}
    candidate = ScholarshipCandidate(
        scholarship_id="fixture-scholarship",
        version_id="cycle-1",
        name="Fixture Scholarship",
        hard_requirements={
            "type": "and",
            "children": [
                {"type": "condition", "field": "school_state", "operator": "eq", "value": "MA", "evidence": evidence},
                {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": evidence},
            ],
        },
        requirements_complete=True,
        availability="verified_open",
        deadline=None,
        source_freshness=None,
    )
    registry = {"school_state": {"type": "choice", "values": ["MA", "NY"]}, "gpa": {"type": "number"}}
    cases = [
        ({"school_state": "MA", "gpa": 3.5}, EligibilityLabel.STRONG),
        ({"school_state": "MA"}, EligibilityLabel.POSSIBLE),
        ({"school_state": "NY", "gpa": 4.0}, EligibilityLabel.NOT_MATCH),
    ]
    for profile, expected in cases:
        result = evaluate_candidates([candidate], profile, registry)[0]
        assert result.eligibility.label is expected
