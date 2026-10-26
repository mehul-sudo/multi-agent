"""
Abstract LLM Provider Base Class.

Defines the contract that all LLM provider adapters (Mock, OpenAI, Anthropic, Gemini) must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any

from app.llm.contracts import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstract base class for provider adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g. 'mock', 'openai', 'anthropic', 'gemini')."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """Return list of supported model names for this provider."""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Verify API keys or credentials needed for this provider."""
        pass

    @abstractmethod
    def supports_capability(self, capability: str) -> bool:
        """Check if provider supports a capability (e.g. 'json_mode', 'tools', 'streaming')."""
        pass

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute a normalized request synchronously and return a normalized LLMResponse."""
        pass
