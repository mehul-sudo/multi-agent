"""
Resilience Package for LLM Operations.

Provides exponential backoff with jitter, retry classification, circuit breaker state control,
and provider fallback policy.
"""

import math
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple

from app.llm.base import LLMProvider
from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.errors import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMProviderUnavailableError,
    LLMTransientError,
)


class CircuitBreakerOpenError(LLMError):
    """Raised when circuit breaker is OPEN due to repeated provider failures."""

    def __init__(self, provider_name: str, recovery_timeout: float):
        super().__init__(
            f"Circuit breaker for provider '{provider_name}' is OPEN. Cooling down for {recovery_timeout}s.",
            provider=provider_name,
            retryable=True,
        )


class CircuitBreaker:
    """Circuit Breaker for isolating provider outages (CLOSED, OPEN, HALF_OPEN)."""

    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()

    def allow_request(self) -> bool:
        """Check if request can proceed based on current state."""
        now = time.time()
        if self.state == self.STATE_OPEN:
            if now - self.last_state_change > self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                self.last_state_change = now
                return True
            return False
        return True

    def record_success(self) -> None:
        """Record successful call and reset failure counters."""
        self.failure_count = 0
        if self.state != self.STATE_CLOSED:
            self.state = self.STATE_CLOSED
            self.last_state_change = time.time()

    def record_failure(self) -> None:
        """Record failure and trip circuit breaker if threshold exceeded."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN
            self.last_state_change = time.time()


class LLMResilienceManager:
    """Manages Retries, Circuit Breakers, and Provider Fallbacks."""

    def __init__(
        self,
        max_retries: int = 2,
        initial_backoff: float = 0.1,
        max_backoff: float = 5.0,
        backoff_factor: float = 2.0,
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_factor = backoff_factor
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, provider_name: str) -> CircuitBreaker:
        """Retrieve or create circuit breaker for provider."""
        key = provider_name.lower()
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CircuitBreaker(provider_name=key)
        return self._circuit_breakers[key]

    def calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with full jitter."""
        exponential = self.initial_backoff * (self.backoff_factor ** (attempt - 1))
        capped = min(exponential, self.max_backoff)
        # Full jitter: random float between 0 and capped
        return random.uniform(0, capped)

    def execute_with_resilience(
        self,
        primary_provider: LLMProvider,
        fallback_provider: Optional[LLMProvider],
        request: LLMRequest,
    ) -> LLMResponse:
        """Execute request with retries, circuit breaker, and optional fallback provider."""
        cb_primary = self.get_circuit_breaker(primary_provider.provider_name)

        if not cb_primary.allow_request():
            if fallback_provider:
                request.metadata["fallback_used"] = True
                request.metadata["fallback_reason"] = f"Circuit breaker OPEN for {primary_provider.provider_name}"
                return self._execute_provider(fallback_provider, request)
            else:
                raise CircuitBreakerOpenError(primary_provider.provider_name, cb_primary.recovery_timeout)

        try:
            response = self._execute_provider_with_retry(primary_provider, request)
            cb_primary.record_success()
            return response
        except LLMError as err:
            cb_primary.record_failure()

            # Non-retryable request or auth errors should not fall back
            if not err.retryable or isinstance(err, (LLMAuthenticationError, LLMInvalidRequestError, LLMConfigurationError)):
                raise err

            # Try fallback provider if primary failed with retryable outage
            if fallback_provider:
                request.metadata["fallback_used"] = True
                request.metadata["fallback_reason"] = f"Primary provider {primary_provider.provider_name} failed: {err.message}"

                fb_request = LLMRequest(**{k: v for k, v in request.__dict__.items() if k != "metadata"})
                fb_request.metadata = dict(request.metadata)
                fb_request.metadata.pop("simulate_rate_limit", None)
                fb_request.metadata.pop("simulate_timeout", None)
                fb_request.metadata.pop("simulate_failure", None)
                try:
                    res = self._execute_provider_with_retry(fallback_provider, fb_request)
                    res.raw_metadata["fallback_used"] = True
                    return res
                except Exception as fb_err:
                    raise LLMProviderUnavailableError(
                        f"Primary ({primary_provider.provider_name}) and fallback ({fallback_provider.provider_name}) providers both failed. Primary error: {err.message}. Fallback error: {str(fb_err)}"
                    ) from fb_err

            raise err

    def _execute_provider_with_retry(
        self, provider: LLMProvider, request: LLMRequest
    ) -> LLMResponse:
        attempt = 0
        max_attempts = self.max_retries + 1
        last_error = None

        while attempt < max_attempts:
            attempt += 1
            try:
                response = provider.generate(request)
                response.retry_count = attempt - 1
                return response
            except LLMError as exc:
                last_error = exc
                if not exc.retryable or attempt >= max_attempts:
                    raise exc

                delay = exc.suggested_retry_delay or self.calculate_backoff(attempt)
                time.sleep(delay)
            except Exception as exc:
                raise LLMProviderUnavailableError(
                    f"Unexpected provider error: {str(exc)}", provider=provider.provider_name
                ) from exc

        if last_error:
            raise last_error
        raise LLMProviderUnavailableError("Provider execution failed with unknown error.")

    def _execute_provider(self, provider: LLMProvider, request: LLMRequest) -> LLMResponse:
        return provider.generate(request)
