"""Provider-independent tests for the structured recommendation adapter."""

from types import SimpleNamespace

import pytest

from app.recommendations import (
    GeminiRecommendationAdapter,
    GeminiRecommendationConfig,
    OpenAIRecommendationAdapter,
    RecommendationConfig,
    RecommendationError,
    configured_recommendation_provider,
)
from app.recommendation_schemas import ModelRecommendationSelection


class FakeResponses:
    """Capture a structured Responses API call without network access."""

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
    """Capture a Gemini structured generation request."""

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
    """Construct an adapter with deterministic provider behavior."""

    responses = FakeResponses(response, error)
    client = SimpleNamespace(responses=responses)
    adapter = OpenAIRecommendationAdapter(RecommendationConfig(api_key="test", model="test-model"), client=client)
    return adapter, responses


def test_configuration_requires_a_key_and_positive_bounds():
    """Missing credentials and invalid limits become safe fallback codes."""

    with pytest.raises(RecommendationError) as missing:
        RecommendationConfig.from_env({})
    assert missing.value.code == "missing_api_key"
    with pytest.raises(RecommendationError) as invalid:
        RecommendationConfig.from_env({"OPENAI_API_KEY": "test", "PATHAID_RECOMMENDATION_MAX_OUTPUT_TOKENS": "0"})
    assert invalid.value.code == "invalid_configuration"


def test_adapter_uses_strict_selection_schema_and_returns_aggregate_usage():
    """The adapter accepts IDs while provider-written factual prose is absent."""

    selection = ModelRecommendationSelection(emphasis="eligibility", criterion_ids=["criterion-1"])
    response = SimpleNamespace(
        output_parsed=selection,
        usage=SimpleNamespace(input_tokens=9, output_tokens=3, total_tokens=12),
    )
    adapter, responses = adapter_with(response=response)
    result = adapter.select({"profile": {"gpa": 3.5}, "criteria": [{"id": "criterion-1"}]})
    assert responses.kwargs["text_format"] is ModelRecommendationSelection
    assert responses.kwargs["model"] == "test-model"
    assert result.selection.criterion_ids == ["criterion-1"]
    assert result.usage.total_tokens == 12


def test_refusal_timeout_and_invalid_output_have_stable_codes():
    """Every provider failure can safely fall back without retaining details."""

    refusal = SimpleNamespace(type="refusal", refusal="private refusal details")
    adapter, _ = adapter_with(response=SimpleNamespace(output_parsed=None, output=[SimpleNamespace(content=[refusal])]))
    with pytest.raises(RecommendationError) as refused:
        adapter.select({})
    assert refused.value.code == "model_refusal"

    timeout_type = type("APITimeoutError", (Exception,), {})
    adapter, _ = adapter_with(error=timeout_type("private provider details"))
    with pytest.raises(RecommendationError) as timed_out:
        adapter.select({})
    assert timed_out.value.code == "provider_unavailable"

    adapter, _ = adapter_with(response=SimpleNamespace(output_parsed={"unknown": True}, output=[]))
    with pytest.raises(RecommendationError) as invalid:
        adapter.select({})
    assert invalid.value.code == "invalid_output"


def test_gemini_recommendation_uses_strict_ids_and_aggregate_usage():
    """Gemini can assist wording without returning factual prose to students."""

    selection = ModelRecommendationSelection(emphasis="eligibility", criterion_ids=["criterion-1"])
    response = SimpleNamespace(
        parsed=selection.model_dump(mode="json"),
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=2, total_token_count=12),
    )
    models = FakeModels(response)
    adapter = GeminiRecommendationAdapter(
        GeminiRecommendationConfig(api_key="test", model="gemini-test"),
        client=SimpleNamespace(models=models),
    )
    result = adapter.select({"criteria": [{"id": "criterion-1"}]})
    assert models.kwargs["config"]["response_schema"] is ModelRecommendationSelection
    assert result.selection.criterion_ids == ["criterion-1"]
    assert result.usage.total_tokens == 12


def test_gemini_recommendation_provider_selection():
    """Gemini is selected only when explicitly configured with its own key."""

    provider = configured_recommendation_provider(
        {
            "PATHAID_RECOMMENDATION_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test",
            "PATHAID_RECOMMENDATION_MODEL": "gemini-test",
        }
    )
    assert isinstance(provider, GeminiRecommendationAdapter)
    with pytest.raises(RecommendationError) as missing:
        configured_recommendation_provider({"PATHAID_RECOMMENDATION_PROVIDER": "gemini"})
    assert missing.value.code == "missing_api_key"
