"""
Tests for LLM Provider Configurations and Secret Redaction.
"""

from app.services.secret_service import redact_secrets


def test_provider_config_registration(client, auth_headers):
    """Test registering LLM provider configurations without exposing secret keys."""
    payload = {
        "provider_name": "openai",
        "display_name": "OpenAI Production",
        "secret_key": "sk-12345678901234567890123456789012",
        "available_models": ["gpt-4o", "gpt-4o-mini"],
    }
    res = client.post("/api/v1/providers", json=payload, headers=auth_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["provider"]["provider_name"] == "openai"
    assert "secret_key" not in data["provider"]  # Never expose raw key

    list_res = client.get("/api/v1/providers", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.get_json()["providers"]) >= 1


def test_secret_redaction_service():
    """Test secret redaction service strips API keys from logs/responses."""
    raw_log = "OpenAI key sk-abcdef12345678901234567890 with bearer Bearer 1234567890123456789020"
    redacted = redact_secrets(raw_log)
    assert "sk-abcdef" not in redacted
    assert "[REDACTED" in redacted
