"""
Normalized Exception Hierarchy for LLM Providers.

Translates provider-specific SDK errors (OpenAI, Anthropic, Gemini) into a unified,
safe exception taxonomy without leaking sensitive API details or stack traces to clients.
"""

from typing import Any, Dict, Optional


class LLMError(Exception):
    """Base exception for all LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        model: Optional[str] = None,
        retryable: bool = False,
        suggested_retry_delay: Optional[float] = None,
        correlation_id: Optional[str] = None,
        raw_error_type: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.retryable = retryable
        self.suggested_retry_delay = suggested_retry_delay
        self.correlation_id = correlation_id
        self.raw_error_type = raw_error_type

    def to_dict(self) -> Dict[str, Any]:
        """Return a safe serialized dictionary representation of the error."""
        return {
            "error_category": self.__class__.__name__,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "retryable": self.retryable,
            "suggested_retry_delay": self.suggested_retry_delay,
            "correlation_id": self.correlation_id,
        }


class LLMConfigurationError(LLMError):
    """Raised when provider API keys or configuration are missing or invalid."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class LLMAuthenticationError(LLMError):
    """Raised when API key authentication fails (e.g. 401 Unauthorized)."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class LLMRateLimitError(LLMError):
    """Raised when provider rate limit is exceeded (e.g. 429 Too Many Requests)."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class LLMTimeoutError(LLMError):
    """Raised when provider API request times out."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class LLMInvalidRequestError(LLMError):
    """Raised when prompt/schema input is malformed or invalid."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class LLMProviderUnavailableError(LLMError):
    """Raised when provider service is down or returning 5xx server errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class LLMResponseFormatError(LLMError):
    """Raised when structured JSON parsing or Pydantic validation fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class LLMQuotaExceededError(LLMError):
    """Raised when hard token or cost budget is exceeded."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class LLMContentPolicyError(LLMError):
    """Raised when content moderation or safety filters block the request."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class LLMTransientError(LLMError):
    """Generic temporary failure that can be retried."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=True, **kwargs)
