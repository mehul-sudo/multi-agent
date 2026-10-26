"""
Unit tests for normalized LLM contracts, requests, responses, and limit validations (Phase 6).
"""

import pytest
from app.llm.contracts import LLMMessage, LLMRequest, LLMResponse, LLMToolDefinition, LLMUsage


def test_llm_request_limit_validation():
    """Verify limit validations on LLMRequest."""
    req = LLMRequest(
        provider="mock",
        model="mock-v1",
        messages=[LLMMessage(role="user", content="Hello")] * 10,
    )
    # Valid limits pass
    req.validate_limits(max_messages=20)

    # Exceeding message count raises ValueError
    with pytest.raises(ValueError, match="Message count"):
        req.validate_limits(max_messages=5)

    # Exceeding max_tokens cap raises ValueError
    req_large = LLMRequest(max_tokens=10000)
    with pytest.raises(ValueError, match="max_tokens"):
        req_large.validate_limits(max_output_tokens_cap=8192)


def test_llm_response_structure():
    """Verify LLMResponse structure and usage fields."""
    res = LLMResponse(
        provider="openai",
        model="gpt-4o",
        text="Hello world!",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        request_duration_ms=150,
    )
    assert res.provider == "openai"
    assert res.text == "Hello world!"
    assert res.usage.total_tokens == 15
    assert res.request_duration_ms == 150
