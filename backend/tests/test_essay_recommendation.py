"""Unit tests for local-first and constrained essay analysis."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.essay_recommendation import EssayAnalysisResponse, local_recommendations
from app.models import Essay


def essay(essay_id: str, *, title: str, prompt: str, tags: list[str], words: int = 100) -> Essay:
    return Essay(
        id=essay_id, title=title, original_prompt=prompt, text="word " * words,
        tags=tags, themes=[], word_count=words, written_on=date(2026, 1, 1),
    )


def test_local_recommendations_rank_metadata_without_changing_text():
    leadership = essay(
        "leadership", title="Community leadership", prompt="Describe your service",
        tags=["volunteering"], words=600,
    )
    technical = essay(
        "technical", title="Software project", prompt="Describe a technical challenge",
        tags=["engineering"], words=300,
    )
    original = leadership.text

    result = local_recommendations(
        [technical, leadership], "How has community service shaped your leadership?", 500,
    )

    assert [item["essay_id"] for item in result] == ["leadership", "technical"]
    assert "destination limit is 500" in result[0]["warnings"][0]
    assert leadership.text == original


def test_provider_schema_rejects_rewritten_or_extra_fields():
    with pytest.raises(ValidationError):
        EssayAnalysisResponse.model_validate({
            "rankings": [{
                "essay_id": "essay-1", "rationale": "Relevant experience.",
                "mismatches": [], "replacement_prose": "Use this generated paragraph...",
            }]
        })


def test_provider_schema_rejects_duplicate_rankings():
    with pytest.raises(ValidationError):
        EssayAnalysisResponse.model_validate({
            "rankings": [
                {"essay_id": "essay-1", "rationale": "First", "mismatches": []},
                {"essay_id": "essay-1", "rationale": "Second", "mismatches": []},
            ]
        })
