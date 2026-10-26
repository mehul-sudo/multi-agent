"""
LLM Provider Registry and Factory.

Central registry for looking up, registering, and instantiating provider adapters,
verifying model capabilities, and resolving per-agent provider policies.
"""

from typing import Dict, List, Optional, Type

from app.llm.base import LLMProvider
from app.llm.errors import LLMConfigurationError, LLMInvalidRequestError
from app.llm.providers.anthropic_adapter import AnthropicProviderAdapter
from app.llm.providers.gemini_adapter import GeminiProviderAdapter
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.openai_adapter import OpenAIProviderAdapter


import os

class LLMProviderRegistry:
    """Registry managing available LLM providers and models."""

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._active_provider: Optional[str] = None
        self._active_model: Optional[str] = None

        # Register providers
        self.register_provider(MockLLMProvider())
        self.register_provider(OpenAIProviderAdapter())
        self.register_provider(AnthropicProviderAdapter())
        self.register_provider(GeminiProviderAdapter())

    def set_active_provider(self, provider_name: str, model_name: Optional[str] = None) -> None:
        """Explicitly set the active production provider and default model."""
        self._active_provider = provider_name.lower()
        if model_name:
            self._active_model = model_name

    def register_provider(self, provider: LLMProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.provider_name.lower()] = provider

    def get_provider(self, provider_name: str) -> LLMProvider:
        """Retrieve a registered provider by name."""
        key = provider_name.lower()
        if key not in self._providers:
            raise LLMInvalidRequestError(
                f"Unsupported LLM provider '{provider_name}'. Supported providers: {list(self._providers.keys())}."
            )
        return self._providers[key]

    def list_providers(self) -> List[str]:
        """List registered provider names."""
        return list(self._providers.keys())

    def get_available_models(self) -> Dict[str, List[str]]:
        """Return dict of provider -> list of supported models."""
        return {name: p.supported_models for name, p in self._providers.items()}

    def validate_capability(self, provider_name: str, capability: str) -> None:
        """Ensure provider supports specified capability (e.g. 'json_mode', 'tools')."""
        provider = self.get_provider(provider_name)
        if not provider.supports_capability(capability):
            raise LLMInvalidRequestError(
                f"Provider '{provider_name}' does not support requested capability '{capability}'."
            )

    def resolve_provider_and_model(
        self,
        requested_provider: Optional[str] = None,
        requested_model: Optional[str] = None,
    ) -> tuple[LLMProvider, str]:
        """Resolve provider instance and model name without mock fallback in production runtime."""
        is_test = bool(
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("TESTING", "").lower() in ("true", "1")
            or os.environ.get("FLASK_ENV") == "testing"
        )

        # 1. Determine Provider Name
        provider_name = (requested_provider or "").lower().strip()

        if provider_name == "mock":
            if not is_test:
                # Disallow mock in normal runtime
                provider_name = ""

        if not provider_name:
            # Auto-resolve configured live provider
            if self._active_provider and self._active_provider != "mock":
                provider_name = self._active_provider
            else:
                env_p = os.environ.get("LLM_PROVIDER", "").strip().lower()
                if env_p and env_p != "mock":
                    provider_name = env_p
                elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                    provider_name = "gemini"
                elif os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENAI_API_KEY", "").startswith("mock-"):
                    provider_name = "openai"
                elif os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY", "").startswith("mock-"):
                    provider_name = "anthropic"
                elif is_test:
                    provider_name = "mock"
                else:
                    # Default to gemini as primary expected real provider
                    provider_name = "gemini"

        provider = self.get_provider(provider_name)

        # 2. Determine Model Name
        model_name = requested_model
        if not model_name:
            if provider_name == self._active_provider and self._active_model:
                model_name = self._active_model
            elif provider_name == "openai":
                model_name = os.environ.get("OPENAI_MODEL") or "gpt-4o"
            elif provider_name == "anthropic":
                model_name = os.environ.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022"
            elif provider_name == "gemini":
                model_name = os.environ.get("GEMINI_MODEL") or "gemini-1.5-flash"
            else:
                supported = provider.supported_models
                model_name = supported[0] if supported else "default-model"

        return provider, model_name


# Global singleton instance
provider_registry = LLMProviderRegistry()
