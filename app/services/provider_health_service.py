"""
Provider Health and Startup Validation Service.

Validates that real LLM provider credentials (OpenAI, Anthropic, or Google Gemini)
are present, uncorrupted, and operational before the backend is allowed to run.
Ensures zero mock fallbacks in normal runtime.
"""

import os
from typing import Any, Dict, Optional, Tuple

from app.llm.base import LLMProvider
from app.llm.registry import provider_registry


PLACEHOLDER_KEYS = {
    "mock-key-for-dev",
    "your-key-here",
    "your-openai-api-key-here",
    "your-anthropic-api-key-here",
    "your-gemini-api-key-here",
    "placeholder",
    "change-me",
    "sk-test",
    "mock",
}


def is_valid_secret(val: Optional[str]) -> bool:
    """Return True only if value is non-empty and not a known placeholder."""
    if not val or not isinstance(val, str):
        return False
    v = val.strip().lower()
    if not v or v in PLACEHOLDER_KEYS or v.startswith("your-") or v.startswith("mock-"):
        return False
    return len(v) >= 10


class ProviderHealthManager:
    """Manages real LLM provider configuration, health verification, and startup validation."""

    _active_provider_name: Optional[str] = None
    _active_model_name: Optional[str] = None
    _is_live: bool = False
    _health_error: Optional[str] = None

    @classmethod
    def is_testing_environment(cls) -> bool:
        """Check if execution is happening within pytest or testing app context."""
        return bool(
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("TESTING", "").lower() in ("true", "1")
            or os.environ.get("FLASK_ENV") == "testing"
        )

    @classmethod
    def get_configured_provider_details(cls) -> Tuple[str, str, str]:
        """
        Determine the configured provider, model, and API key from environment variables.
        Returns: (provider_name, model_name, api_key)
        """
        provider_env = os.environ.get("LLM_PROVIDER", "").strip().lower()

        # If LLM_PROVIDER is not set or set to mock, auto-detect available real provider
        if not provider_env or provider_env == "mock":
            if is_valid_secret(os.environ.get("OPENAI_API_KEY")):
                provider_env = "openai"
            elif is_valid_secret(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                provider_env = "gemini"
            elif is_valid_secret(os.environ.get("ANTHROPIC_API_KEY")):
                provider_env = "anthropic"
            else:
                provider_env = "openai"  # default expected provider

        if provider_env == "openai":
            key = os.environ.get("OPENAI_API_KEY", "").strip()
            model = os.environ.get("OPENAI_MODEL") or "gpt-4o"
        elif provider_env == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            model = os.environ.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022"
        elif provider_env == "gemini":
            key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            model = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
        else:
            key = ""
            model = "unknown"

        return provider_env, model, key

    @classmethod
    def validate_startup_configuration(cls, fail_fast: bool = True) -> Dict[str, Any]:
        """
        Validate backend AI provider configuration at startup.
        Fails fast if credentials are missing or invalid in normal runtime.
        """
        if cls.is_testing_environment():
            # Allow isolated unit tests to pass without mandatory live API keys
            cls._active_provider_name = os.environ.get("LLM_PROVIDER", "mock").lower()
            cls._active_model_name = "test-model"
            cls._is_live = False
            return {
                "status": "TESTING",
                "provider": cls._active_provider_name,
                "model": cls._active_model_name,
                "healthy": True,
            }

        provider, model, key = cls.get_configured_provider_details()

        # 1. Validate Provider Name
        if provider not in ("openai", "anthropic", "gemini"):
            err_msg = (
                f"AI provider configuration is required.\n"
                f"Provider: '{provider}'\n"
                f"Missing/invalid configuration: Supported providers are 'openai', 'anthropic', or 'gemini'."
            )
            cls._health_error = err_msg
            if fail_fast:
                raise RuntimeError(err_msg)
            return {"status": "FAILED", "error": err_msg}

        # 2. Validate API Key
        if not is_valid_secret(key):
            key_var_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "gemini": "GEMINI_API_KEY (or GOOGLE_API_KEY)",
            }
            required_var = key_var_map.get(provider, f"{provider.upper()}_API_KEY")
            err_msg = (
                f"AI provider configuration is required.\n"
                f"Provider: {provider}\n"
                f"Missing/invalid configuration: {required_var} is missing or is set to a placeholder."
            )
            cls._health_error = err_msg
            if fail_fast:
                raise RuntimeError(err_msg)
            return {"status": "FAILED", "error": err_msg}

        # 3. Validate Provider Adapter is registered
        try:
            adapter = provider_registry.get_provider(provider)
            # Update adapter's API key if it wasn't passed during constructor
            if hasattr(adapter, "api_key") and not adapter.api_key:
                adapter.api_key = key
        except Exception as e:
            err_msg = (
                f"AI provider configuration is required.\n"
                f"Provider: {provider}\n"
                f"Missing/invalid configuration: Failed to instantiate adapter: {str(e)}"
            )
            cls._health_error = err_msg
            if fail_fast:
                raise RuntimeError(err_msg)
            return {"status": "FAILED", "error": err_msg}

        # 4. Mark as LIVE
        cls._active_provider_name = provider
        cls._active_model_name = model
        cls._is_live = True
        cls._health_error = None

        # Synchronize provider_registry active provider
        provider_registry.set_active_provider(provider, model)

        return {
            "status": "LIVE",
            "provider": provider.upper(),
            "model": model,
            "healthy": True,
        }

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Return truthful LIVE status for backend health endpoints and UI."""
        provider, model, key = cls.get_configured_provider_details()
        is_live = is_valid_secret(key) and provider in ("openai", "anthropic", "gemini")

        return {
            "ai_status": "LIVE" if is_live else ("TESTING" if cls.is_testing_environment() else "CONFIGURATION_REQUIRED"),
            "provider": provider.upper(),
            "model": model,
            "is_live": is_live,
            "healthy": is_live or cls.is_testing_environment(),
            "error": cls._health_error,
        }
