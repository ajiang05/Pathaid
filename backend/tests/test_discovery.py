"""Tests for transparent coverage filtering and discovery ordering."""

from datetime import datetime, timezone

from app.discovery import RankingRecord, match_coverage, rank_records


def record(
    program_id: str,
    name: str,
    label: str,
    availability: str,
    deadline: datetime | None = None,
    coverage: dict | None = None,
) -> RankingRecord:
    """Build a concise synthetic ranking input."""

    return RankingRecord(
        program_id=program_id,
        name=name,
        eligibility_label=label,
        application_availability=availability,
        application_deadline=deadline,
        coverage=coverage or {"type": "national"},
    )


def test_coverage_prefers_institution_then_state_then_national():
    """The most specific reviewed match becomes the relevance factor."""

    profile = {"school": "University of Massachusetts Amherst", "state": "MA"}
    assert match_coverage({"institutions": ["University of Massachusetts Amherst"], "states": ["MA"], "national": True}, profile).relevance == "institution"
    assert match_coverage({"states": ["MA"], "national": True}, profile).relevance == "state"
    assert match_coverage({"type": "national"}, profile).relevance == "national"


def test_explicit_coverage_mismatch_filters_candidate():
    """A student outside reviewed local coverage does not receive the record."""

    local = record("local", "Local Program", "Likely eligible", "open", coverage={"states": ["NY"]})
    assert rank_records([local], {"state": "MA"}) == []


def test_missing_coverage_answer_keeps_candidate_unresolved():
    """Missing school/state data cannot be treated as a coverage mismatch."""

    local = record("local", "Local Program", "Need more information", "open", coverage={"states": ["MA"]})
    ranked = rank_records([local], {})
    assert ranked[0].relevance == "coverage unresolved"


def test_ranking_follows_eligibility_availability_deadline_relevance_and_name():
    """Every ordering factor follows the precedence defined in the plan."""

    near = datetime(2027, 1, 1, tzinfo=timezone.utc)
    far = datetime(2027, 2, 1, tzinfo=timezone.utc)
    records = [
        record("eligible-closed", "Closed", "Likely eligible", "closed"),
        record("unresolved-open", "Unresolved", "Need more information", "open", near),
        record("eligible-unknown", "Confirm", "Likely eligible", "unknown", near),
        record("eligible-open-no-date", "No Date", "Likely eligible", "open"),
        record("eligible-open-far", "Far", "Likely eligible", "open", far),
        record("eligible-open-near-national", "Near National", "Likely eligible", "open", near),
        record("eligible-open-near-state", "Near State", "Likely eligible", "open", near, {"states": ["MA"]}),
        record("ineligible-open", "Ineligible", "Likely ineligible", "open", near),
    ]
    ranked = rank_records(records, {"state": "MA"})
    assert [item.record.program_id for item in ranked] == [
        "eligible-open-near-state",
        "eligible-open-near-national",
        "eligible-open-far",
        "eligible-open-no-date",
        "eligible-unknown",
        "eligible-closed",
        "unresolved-open",
        "ineligible-open",
    ]
    assert ranked[4].section == "Confirm availability"
    assert ranked[4].ranking_factors["deadline"] == "not used for this availability section"


def test_name_and_id_make_ties_stable():
    """Name and stable program ID produce repeatable final tie-breaks."""

    records = [
        record("b", "Same Name", "Likely eligible", "open"),
        record("z", "Zulu", "Likely eligible", "open"),
        record("a", "Same Name", "Likely eligible", "open"),
        record("alpha", "Alpha", "Likely eligible", "open"),
    ]
    assert [item.record.program_id for item in rank_records(records, {})] == ["alpha", "a", "b", "z"]
