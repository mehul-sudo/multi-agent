"""
Unit tests for EmailAgent.
"""

import pytest
from app.agents.base import AgentContext
from app.agents.email_agent import EmailAgent


def test_email_agent_draft_mode():
    agent = EmailAgent()
    ctx = AgentContext(
        input_data={
            "mode": "draft",
            "to": "executive@example.com",
            "subject": "Monthly Business Summary",
            "body": "Please review attached metrics.",
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "email"
    assert result.output["mode"] == "draft"
    assert result.output["status"] == "drafted"
    assert result.output["to"] == ["executive@example.com"]
    assert result.requires_approval is False


def test_email_agent_send_mode_requires_approval():
    agent = EmailAgent()
    ctx = AgentContext(
        input_data={
            "mode": "send",
            "to": "client@external.com",
            "subject": "Contract Renewal",
            "body": "Your renewal terms are ready.",
            "approval_granted": False,
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["mode"] == "send"
    assert result.output["status"] == "awaiting_approval"
    assert result.requires_approval is True
    assert "Send email" in result.approval_details["requested_action"]


def test_email_agent_send_mode_with_approval_succeeds():
    agent = EmailAgent()
    ctx = AgentContext(
        input_data={
            "mode": "send",
            "to": "client@external.com",
            "subject": "Contract Renewal",
            "body": "Terms approved.",
            "approval_granted": True,
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["status"] == "sent"
    assert result.output["messageId"].startswith("mock_msg_") or result.output["messageId"].startswith("msg_")


def test_email_agent_invalid_email_fails():
    agent = EmailAgent()
    ctx = AgentContext(
        input_data={"mode": "draft", "to": "not-an-email-address"},
    )

    result = agent.execute(ctx)
    assert result.success is False
    assert "Invalid email address" in result.error
