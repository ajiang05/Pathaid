"""Tests for provider-independent behavior of the OpenAI extraction adapter."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from app.extraction import (
    DeterministicExtractionStub,
    ExtractionConfig,
    ExtractionError,
    GeminiExtractionAdapter,
    GeminiExtractionConfig,
    OpenAIExtractionAdapter,
    PROMPT_VERSION,
    SYSTEM_INSTRUCTIONS,
    configured_extraction_provider,
)
from app.extraction_schemas import EXTRACTION_SCHEMA_VERSION, ExtractedProgramDraft


@dataclass(frozen=True)
class Snapshot:
    """Minimal retained source accepted by either extraction provider."""

    id: str = "snapshot-1"
    source_url: str = "https://example.edu/aid"
    source_text: str = "Applicants must have a 3.0 GPA."
    acquired_at: datetime = datetime(2026, 10, 24, 15, 30, tzinfo=timezone.utc)


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


class FakeModels:
    """Capture a Gemini generate-content call without network access."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    def generate_content(self, **kwargs):
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
    assert json.loads(responses.kwargs["input"][1]["content"])["extraction_date"] == "2026-10-24"
    assert result.schema_version == EXTRACTION_SCHEMA_VERSION
    assert result.usage.total_tokens == 200
    assert result.request_id == "request-1"


def test_prompt_requires_complete_mandatory_rule_coverage_and_current_profile_fields():
    """The extraction contract must not silently omit rules or drift from profile fields."""

    assert PROMPT_VERSION == "1.3.0"
    assert "every mandatory eligibility requirement" in SYSTEM_INSTRUCTIONS
    assert "Never omit a mandatory requirement" in SYSTEM_INSTRUCTIONS
    assert "race, first_generation_student" in SYSTEM_INSTRUCTIONS
    assert "Do not translate \"no prior bachelor's degree\" into study_level" in SYSTEM_INSTRUCTIONS


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


def test_gemini_adapter_uses_same_schema_and_normalizes_usage():
    """Gemini proposals cross the same strict contract as OpenAI proposals."""

    models = FakeModels(
        SimpleNamespace(
            parsed=draft().model_dump(mode="json"),
            usage_metadata=SimpleNamespace(prompt_token_count=21, candidates_token_count=8, total_token_count=29),
            response_id="gemini-request-1",
        )
    )
    adapter = GeminiExtractionAdapter(
        GeminiExtractionConfig(api_key="test", model="gemini-test"),
        client=SimpleNamespace(models=models),
    )
    result = adapter.extract(Snapshot())

    schema = models.kwargs["config"]["response_json_schema"]
    assert schema["title"] == "ExtractedProgramDraft"
    assert "oneOf" not in str(schema)
    assert "discriminator" not in str(schema)
    assert "children" not in schema["$defs"]["RuleGroup"]["required"]
    assert schema["$defs"]["ConditionRule"]["properties"]["type"]["enum"] == ["condition"]
    assert models.kwargs["config"]["response_mime_type"] == "application/json"
    assert result.draft.name == "Example Award"
    assert result.usage.total_tokens == 29
    assert result.request_id == "gemini-request-1"


def test_gemini_adapter_discards_oversized_optional_amount():
    """An ignored maxLength becomes unknown instead of truncated financial data."""

    raw = draft().model_dump(mode="json")
    raw["assistance_amount"] = "x" * 241
    adapter = GeminiExtractionAdapter(
        GeminiExtractionConfig(api_key="test", model="gemini-test"),
        client=SimpleNamespace(models=FakeModels(SimpleNamespace(parsed=raw, usage_metadata=None))),
    )

    result = adapter.extract(Snapshot())

    assert result.draft.assistance_amount is None


def test_provider_selection_requires_matching_key_and_known_provider():
    """Provider selection never silently sends a key to a different service."""

    provider = configured_extraction_provider(
        {
            "PATHAID_EXTRACTION_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test",
            "PATHAID_EXTRACTION_MODEL": "gemini-test",
        }
    )
    assert isinstance(provider, GeminiExtractionAdapter)
    with pytest.raises(ExtractionError) as missing:
        configured_extraction_provider({"PATHAID_EXTRACTION_PROVIDER": "gemini"})
    assert missing.value.code == "missing_api_key"
    with pytest.raises(ExtractionError) as unknown:
        configured_extraction_provider({"PATHAID_EXTRACTION_PROVIDER": "unknown"})
    assert unknown.value.code == "invalid_configuration"


def test_gemini_block_and_rate_limit_map_to_safe_failures():
    """Gemini safety and quota outcomes preserve the existing retry contract."""

    blocked = SimpleNamespace(parsed=None, prompt_feedback=SimpleNamespace(block_reason="SAFETY"), candidates=[])
    adapter = GeminiExtractionAdapter(
        GeminiExtractionConfig(api_key="test"),
        client=SimpleNamespace(models=FakeModels(blocked)),
    )
    with pytest.raises(ExtractionError) as refused:
        adapter.extract(Snapshot())
    assert refused.value.code == "model_refusal"

    rate_limit = type("ServerError", (Exception,), {"status_code": 429})
    adapter = GeminiExtractionAdapter(
        GeminiExtractionConfig(api_key="test"),
        client=SimpleNamespace(models=FakeModels(error=rate_limit("private details"))),
    )
    with pytest.raises(ExtractionError) as unavailable:
        adapter.extract(Snapshot())
    assert unavailable.value.code == "provider_unavailable"
    assert unavailable.value.retryable
