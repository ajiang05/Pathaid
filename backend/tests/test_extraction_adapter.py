"""Tests for provider-independent behavior of the OpenAI extraction adapter."""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.extraction import DeterministicExtractionStub, ExtractionConfig, ExtractionError, OpenAIExtractionAdapter
from app.extraction_schemas import EXTRACTION_SCHEMA_VERSION, ExtractedProgramDraft


@dataclass(frozen=True)
class Snapshot:
    """Minimal retained source accepted by either extraction provider."""

    id: str = "snapshot-1"
    source_url: str = "https://example.edu/aid"
    source_text: str = "Applicants must have a 3.0 GPA."


def draft() -> ExtractedProgramDraft:
    """Return a small parsed proposal for adapter tests."""

    evidence = {"snapshot_id": "snapshot-1", "excerpt": "Applicants must have a 3.0 GPA."}
    return ExtractedProgramDraft.model_validate(
        {
            "name": "Example Award",
            "description": "Example scholarship.",
            "categories": ["scholarships"],
            "coverage": {"national": True, "states": [], "institutions": []},
            "checklist": [],
            "eligibility_tree": {"type": "condition", "field": "gpa", "operator": "gte", "value": 3.0, "evidence": evidence, "exceptions_complete": True},
            "coverage_complete": True,
            "award_cycle": None,
            "application_deadline": None,
            "deadline_timezone": None,
            "application_availability": "unknown",
            "assistance_amount": None,
            "selection_factors": [],
            "application_url": None,
            "unresolved_conditions": [],
        }
    )


class FakeResponses:
    """Capture a Responses API parse call and return a controlled response."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def adapter_with(response=None, error=None):
    """Build an adapter with no network client or environment dependency."""

    responses = FakeResponses(response, error)
    client = SimpleNamespace(responses=responses)
    return OpenAIExtractionAdapter(ExtractionConfig(api_key="test-key", model="test-model"), client=client), responses


def test_missing_key_has_an_explicit_configuration_outcome():
    """A missing credential fails before creating a provider client."""

    with pytest.raises(ExtractionError) as caught:
        ExtractionConfig.from_env({})
    assert caught.value.code == "missing_api_key"
    assert not caught.value.retryable


def test_adapter_uses_structured_output_and_records_metadata():
    """The provider receives the strict schema and returns versioned usage data."""

    response = SimpleNamespace(output_parsed=draft(), usage=SimpleNamespace(input_tokens=120, output_tokens=80, total_tokens=200), _request_id="request-1")
    adapter, responses = adapter_with(response=response)
    result = adapter.extract(Snapshot())

    assert responses.kwargs["text_format"] is ExtractedProgramDraft
    assert responses.kwargs["model"] == "test-model"
    assert "student_profile" not in responses.kwargs["input"][1]["content"]
    assert result.schema_version == EXTRACTION_SCHEMA_VERSION
    assert result.usage.total_tokens == 200
    assert result.request_id == "request-1"


def test_refusal_has_an_explicit_safe_outcome():
    """Provider refusal text is detected but is not retained in the error."""

    refusal = SimpleNamespace(type="refusal", refusal="private provider explanation")
    adapter, _ = adapter_with(response=SimpleNamespace(output_parsed=None, output=[SimpleNamespace(content=[refusal])]))
    with pytest.raises(ExtractionError) as caught:
        adapter.extract(Snapshot())
    assert caught.value.code == "model_refusal"
    assert "private" not in caught.value.safe_message


def test_missing_parsed_output_is_invalid_output():
    """A non-refusal response without parsed data cannot enter review."""

    adapter, _ = adapter_with(response=SimpleNamespace(output_parsed=None, output=[]))
    with pytest.raises(ExtractionError) as caught:
        adapter.extract(Snapshot())
    assert caught.value.code == "invalid_output"


def test_retryable_provider_error_is_normalized_without_details():
    """Transient SDK failures expose a retry decision and a safe message."""

    error_type = type("RateLimitError", (Exception,), {})
    adapter, _ = adapter_with(error=error_type("secret provider details"))
    with pytest.raises(ExtractionError) as caught:
        adapter.extract(Snapshot())
    assert caught.value.code == "provider_unavailable"
    assert caught.value.retryable
    assert "secret" not in caught.value.safe_message


def test_oversized_source_is_rejected_before_provider_call():
    """The adapter never silently truncates evidence-bearing source text."""

    responses = FakeResponses()
    adapter = OpenAIExtractionAdapter(ExtractionConfig(api_key="test-key", max_source_characters=5), client=SimpleNamespace(responses=responses))
    with pytest.raises(ExtractionError) as caught:
        adapter.extract(Snapshot())
    assert caught.value.code == "source_too_large"
    assert responses.kwargs is None


def test_deterministic_stub_returns_fixture_with_version_metadata():
    """Offline tests can exercise orchestration without model calls or keys."""

    result = DeterministicExtractionStub({"snapshot-1": draft()}).extract(Snapshot())
    assert result.draft.name == "Example Award"
    assert result.model == "deterministic-stub"
    assert result.usage.total_tokens is None
