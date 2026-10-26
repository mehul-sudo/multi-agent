"""
Secret management service.

Handles secret key resolution, redaction in logs/responses, and secure key references.
Raw API keys are NEVER exposed in responses, exception messages, or audit logs.
"""

import os
import re
from typing import Any, Dict

# Regex patterns matching common secret keys (OpenAI, Anthropic, Gemini, JWT, bearer tokens)
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}"),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
]


def resolve_secret(secret_ref: str | None, default_env_var: str | None = None) -> str | None:
    """Resolve a secret key reference or fallback to environment variable.

    Args:
        secret_ref: An alias/reference to a secret (e.g., 'env:OPENAI_API_KEY') or raw string.
        default_env_var: Fallback environment variable name.

    Returns:
        The actual secret string or None if unresolvable.
    """
    if not secret_ref:
        if default_env_var:
            return os.getenv(default_env_var)
        return None

    if secret_ref.startswith("env:"):
        var_name = secret_ref.split("env:", 1)[1]
        return os.getenv(var_name)

    # In development mode, if secret_ref is direct, return it (will be redacted before returning in APIs)
    return secret_ref


def redact_secrets(content: Any) -> Any:
    """Recursively redact secrets, API keys, and sensitive tokens from strings, dicts, or lists."""
    if isinstance(content, str):
        redacted = content
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED_API_KEY]", redacted)
        return redacted
    elif isinstance(content, dict):
        sanitized = {}
        for key, val in content.items():
            key_lower = str(key).lower()
            if any(k in key_lower for k in ["api_key", "secret", "password", "auth_token", "private_key"]):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = redact_secrets(val)
        return sanitized
    elif isinstance(content, list):
        return [redact_secrets(item) for item in content]
    return content


class SecretService:
    """Class wrapper for secret resolution and redaction."""

    @staticmethod
    def redact_secrets(content: Any) -> Any:
        return redact_secrets(content)

    @staticmethod
    def redact_dict(content: Dict[str, Any]) -> Dict[str, Any]:
        return redact_secrets(content)

    @staticmethod
    def resolve_secret(secret_ref: str | None, default_env_var: str | None = None) -> str | None:
        return resolve_secret(secret_ref, default_env_var)

