"""
Unit tests for Provider Adapters (Mock, OpenAI, Anthropic, Gemini) and Registry (Phase 6).
"""

from unittest.mock import MagicMock
import pytest

from app.llm.contracts import LLMMessage, LLMRequest
from app.llm.errors import LLMAuthenticationError, LLMConfigurationError, LLMRateLimitError
from app.llm.providers.anthropic_adapter import AnthropicProviderAdapter
from app.llm.providers.gemini_adapter import GeminiProviderAdapter
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.openai_adapter import OpenAIProviderAdapter
from app.llm.registry import provider_registry


def test_provider_registry_lookup():
    """Verify registry resolves registered providers and model lists."""
    assert "mock" in provider_registry.list_providers()
    assert "openai" in provider_registry.list_providers()
    assert "anthropic" in provider_registry.list_providers()
    assert "gemini" in provider_registry.list_providers()

    provider, model = provider_registry.resolve_provider_and_model("mock", "mock-v1")
    assert provider.provider_name == "mock"
    assert model == "mock-v1"


def test_mock_provider_deterministic_generation():
    """Verify MockLLMProvider returns deterministic outputs and handles simulation flags."""
    mock_prov = MockLLMProvider()
    req = LLMRequest(
        provider="mock",
        model="mock-v1",
        messages=[LLMMessage(role="user", content="Test prompt")],
    )
    res = mock_prov.generate(req)
    assert res.provider == "mock"
    assert "Mock LLM response" in res.text

    # Simulated auth error
    req_auth_err = LLMRequest(metadata={"simulate_auth_error": True})
    with pytest.raises(LLMAuthenticationError):
        mock_prov.generate(req_auth_err)


def test_openai_adapter_with_mocked_sdk():
    """Verify OpenAIProviderAdapter translates SDK response to normalized LLMResponse."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "OpenAI answer"
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"
    mock_res = MagicMock()
    mock_res.choices = [mock_choice]
    mock_res.model = "gpt-4o"
    mock_res.usage.prompt_tokens = 12
    mock_res.usage.completion_tokens = 8
    mock_res.usage.total_tokens = 20
    mock_res.id = "req_123"
    mock_client.chat.completions.create.return_value = mock_res

    adapter = OpenAIProviderAdapter(api_key="sk-test", client=mock_client)
    req = LLMRequest(provider="openai", model="gpt-4o", messages=[LLMMessage(role="user", content="Hi")])
    res = adapter.generate(req)

    assert res.provider == "openai"
    assert res.text == "OpenAI answer"
    assert res.usage.total_tokens == 20


def test_anthropic_adapter_with_mocked_sdk():
    """Verify AnthropicProviderAdapter translates SDK response to normalized LLMResponse."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Claude answer"
    mock_res = MagicMock()
    mock_res.content = [mock_block]
    mock_res.stop_reason = "end_turn"
    mock_res.model = "claude-3-5-sonnet-20240620"
    mock_res.usage.input_tokens = 15
    mock_res.usage.output_tokens = 10
    mock_res.id = "msg_456"
    mock_client.messages.create.return_value = mock_res

    adapter = AnthropicProviderAdapter(api_key="sk-ant-test", client=mock_client)
    req = LLMRequest(provider="anthropic", model="claude-3-5-sonnet-20240620", messages=[LLMMessage(role="user", content="Hi")])
    res = adapter.generate(req)

    assert res.provider == "anthropic"
    assert res.text == "Claude answer"
    assert res.usage.total_tokens == 25


def test_gemini_adapter_with_mocked_sdk():
    """Verify GeminiProviderAdapter translates SDK response to normalized LLMResponse."""
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = "Gemini answer"
    mock_res.usage_metadata.prompt_token_count = 8
    mock_res.usage_metadata.candidates_token_count = 6
    mock_client.generate_content.return_value = mock_res

    adapter = GeminiProviderAdapter(api_key="gemini-key", client=mock_client)
    req = LLMRequest(provider="gemini", model="gemini-1.5-pro", messages=[LLMMessage(role="user", content="Hi")])
    res = adapter.generate(req)

    assert res.provider == "gemini"
    assert res.text == "Gemini answer"
    assert res.usage.total_tokens == 14
