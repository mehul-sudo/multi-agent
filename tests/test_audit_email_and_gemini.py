"""
Targeted Audit Verification Test Suite:
1. Fix generic email fallback: If required upstream results are unavailable or cannot
   be converted into meaningful email content, fail clearly instead of sending generic success text.
2. Preserve valid standalone email drafting/sending behaviour where upstream data is not required.
3. Audit GeminiProviderAdapter: Deprecated model IDs (gemini-1.5-pro, gemini-1.5-flash) removed
   from active supported-model list; verified active models present; existing GEMINI_API_KEY preserved.
4. Mocked Resend tests distinguished from real provider calls; safe test recipient verified.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.agents.base import AgentContext
from app.agents.email_agent import EmailAgent
from app.llm.providers.gemini_adapter import GeminiProviderAdapter


def test_audit_email_missing_required_upstream_fails_clearly():
    """Verify that when upstream results are required but unavailable, EmailAgent fails clearly."""
    agent = EmailAgent()
    ctx = AgentContext(
        task_id="audit_req_upstream_missing",
        input_data={"require_upstream": True, "to": "audit@enterprise.com", "mode": "draft"},
        instructions="Send email with required pipeline findings.",
    )
    res = agent.execute(ctx)
    assert res.success is False
    assert "Missing upstream results" in res.error
    assert "preceding pipeline outputs" in res.error


def test_audit_email_unconvertible_upstream_results_fails_clearly():
    """Verify that when upstream results exist in graph but contain no substantive data
    (e.g. empty output dict), EmailAgent fails clearly instead of sending generic success text."""
    agent = EmailAgent()
    # Upstream record has empty output dict
    ctx = AgentContext(
        task_id="audit_unconvertible_upstream",
        input_data={
            "to": "audit@enterprise.com",
            "mode": "draft",
            "upstream_results": {
                "custom_node": {
                    "agent_type": "custom",
                    "node_id": "empty_node_1",
                    "output": {},  # No substantive findings
                }
            },
        },
        instructions="Send email based on upstream node.",
    )
    res = agent.execute(ctx)
    assert res.success is False
    assert "Cannot convert upstream results into meaningful email content" in res.error
    assert "missing substantive findings" in res.error


def test_audit_email_standalone_with_body_preserves_valid_behaviour():
    """Verify that standalone email drafting/sending with explicit body is fully preserved."""
    agent = EmailAgent()
    ctx = AgentContext(
        task_id="audit_standalone_body",
        input_data={
            "mode": "draft",
            "to": "partner@external.com",
            "subject": "Quarterly Partnership Review",
            "body": "Here are the discussion points for our upcoming quarterly review meeting.",
        },
    )
    res = agent.execute(ctx)
    assert res.success is True
    assert res.output["mode"] == "draft"
    assert res.output["status"] == "drafted"
    assert res.output["body"] == "Here are the discussion points for our upcoming quarterly review meeting."
    assert res.output["subject"] == "Quarterly Partnership Review"


def test_audit_email_standalone_with_instructions_preserves_valid_behaviour():
    """Verify standalone email extracting message from instructions succeeds without requiring upstream."""
    agent = EmailAgent()
    ctx = AgentContext(
        task_id="audit_standalone_instructions",
        input_data={
            "mode": "draft",
            "to": "team@internal.com",
            "subject": "Deployment Notice",
        },
        instructions='Send message saying "Production release 2.4.0 deployed successfully."',
    )
    res = agent.execute(ctx)
    assert res.success is True
    assert res.output["mode"] == "draft"
    assert "Production release 2.4.0 deployed successfully." in res.output["body"]


def test_audit_email_standalone_without_content_fails_clearly():
    """Verify standalone email with neither body nor instructions fails clearly instead of sending generic text."""
    agent = EmailAgent()
    ctx = AgentContext(
        task_id="audit_standalone_no_content",
        input_data={
            "mode": "draft",
            "to": "team@internal.com",
        },
    )
    res = agent.execute(ctx)
    assert res.success is False
    assert "Email content is required" in res.error


def test_audit_gemini_adapter_deprecated_models_removed():
    """Verify deprecated model IDs (gemini-1.5-pro, gemini-1.5-flash) are removed from active supported_models."""
    adapter = GeminiProviderAdapter()
    supported = adapter.supported_models

    # Deprecated models must NOT be present
    assert "gemini-1.5-pro" not in supported
    assert "gemini-1.5-flash" not in supported
    assert "gemini-1.0-pro" not in supported

    # Officially verified active models must be present
    assert "gemini-flash-lite-latest" in supported
    assert "gemini-3.5-flash" in supported
    assert "gemini-3.5-flash-lite" in supported
    assert "gemini-3.8-flash" in supported
    assert "gemini-flash-latest" in supported
    assert "gemini-pro-latest" in supported
    assert "gemini-2.5-flash" in supported
    assert "gemini-2.5-pro" in supported


def test_audit_gemini_adapter_reuses_existing_key():
    """Verify GeminiProviderAdapter reuses GEMINI_API_KEY from environment without requiring a new key."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AQ.Ab8RN6IbEOJIXDGMwCte7jBnFrNRgBn4yNyQrgQxJ-i9dFiKHw"}):
        adapter = GeminiProviderAdapter()
        assert adapter.api_key == "AQ.Ab8RN6IbEOJIXDGMwCte7jBnFrNRgBn4yNyQrgQxJ-i9dFiKHw"
        assert adapter.validate_config() is True


def test_audit_resend_mocked_vs_live_protection():
    """Verify that in test runtime, Resend dispatch is guarded and does not send emails to arbitrary recipients."""
    agent = EmailAgent()
    with patch.dict(os.environ, {
        "EMAIL_PROVIDER": "resend",
        "EMAIL_MODE": "sandbox",
        "RESEND_TEST_RECIPIENT": "safe-test@enterprise.com",
        "RESEND_API_KEY": "re_mock_test_key_123",
        "PYTEST_CURRENT_TEST": "test_audit_resend_mocked_vs_live_protection",
    }):
        # Mock requests.post to ensure test isolation
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "re_msg_mock_audit_999"}, text='{"id": "re_msg_mock_audit_999"}')
            
            ctx = AgentContext(
                task_id="audit_resend_guard",
                input_data={
                    "mode": "send",
                    "to": "arbitrary-stranger@random-domain-xyz.com",
                    "subject": "System Verification",
                    "body": "Audited body message for delivery testing.",
                    "approval_granted": True,
                },
                metadata={"_backend_approval_verified": True},
            )
            res = agent.execute(ctx)
            assert res.success is True
            assert mock_post.call_count == 1
            call_kwargs = mock_post.call_args[1]
            # Must be redirected to the safe test recipient, NOT sent to arbitrary stranger!
            assert call_kwargs["json"]["to"] == ["safe-test@enterprise.com"]
