"""
Unit tests for LLM Resilience Manager (Retries, Exponential Backoff, Circuit Breaker, Fallback).
"""

from unittest.mock import MagicMock
import pytest

from app.llm.contracts import LLMMessage, LLMRequest, LLMResponse
from app.llm.errors import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMProviderUnavailableError,
)
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.resilience import CircuitBreaker, CircuitBreakerOpenError, LLMResilienceManager


def test_circuit_breaker_transitions():
    """Verify CircuitBreaker moves from CLOSED to OPEN after failure threshold, and HALF_OPEN after timeout."""
    cb = CircuitBreaker(provider_name="test_prov", failure_threshold=2, recovery_timeout=0.1)
    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.allow_request() is True

    # Record 2 failures -> OPEN
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.STATE_OPEN
    assert cb.allow_request() is False

    # Wait for recovery timeout -> HALF_OPEN
    import time
    time.sleep(0.15)
    assert cb.allow_request() is True
    assert cb.state == CircuitBreaker.STATE_HALF_OPEN

    # Record success -> CLOSED
    cb.record_success()
    assert cb.state == CircuitBreaker.STATE_CLOSED


def test_resilience_fallback_provider():
    """Verify LLMResilienceManager executes fallback provider when primary fails with retryable error."""
    primary = MockLLMProvider()
    fallback = MockLLMProvider()

    req = LLMRequest(
        provider="mock",
        model="mock-v1",
        messages=[LLMMessage(role="user", content="Hi")],
        metadata={"simulate_rate_limit": True},  # Primary will raise LLMRateLimitError
    )

    mgr = LLMResilienceManager(max_retries=1, initial_backoff=0.01)

    # Secondary req metadata for fallback execution override
    req.metadata["custom_text_output"] = "Fallback answer"

    res = mgr.execute_with_resilience(
        primary_provider=primary,
        fallback_provider=fallback,
        request=req,
    )

    assert res is not None
    assert req.metadata.get("fallback_used") is True


def test_non_retryable_error_does_not_retry_or_fallback():
    """Verify LLMAuthenticationError (non-retryable) fails immediately without retry or fallback."""
    primary = MockLLMProvider()
    fallback = MockLLMProvider()

    req = LLMRequest(
        provider="mock",
        model="mock-v1",
        messages=[LLMMessage(role="user", content="Hi")],
        metadata={"simulate_auth_error": True},
    )

    mgr = LLMResilienceManager(max_retries=2, initial_backoff=0.01)

    with pytest.raises(LLMAuthenticationError):
        mgr.execute_with_resilience(primary_provider=primary, fallback_provider=fallback, request=req)

    assert "fallback_used" not in req.metadata
