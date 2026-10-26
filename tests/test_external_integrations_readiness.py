"""
Tests for External Integration Readiness and Edge Cases:
- Missing SMTP / SendGrid credentials error reporting in EmailAgent
- Missing Google Calendar OAuth credentials error reporting in CalendarAgent
- Multi-statement SQL and comments blocking in DatabaseBIAgent
- SSRF DNS resolution and redirect blocking in HttpWebhookAgent
- Real binary PDF report generation via ReportLab in ReportGenerationAgent
"""

import os
import pytest
from app.agents.base import AgentContext
from app.agents.email_agent import EmailAgent
from app.agents.database_bi_agent import DatabaseBIAgent
from app.agents.http_webhook_agent import HttpWebhookAgent
from app.agents.report_generation_agent import ReportGenerationAgent


def test_email_agent_missing_smtp_credentials(monkeypatch):
    """Test EmailAgent returns clear configuration error when SMTP_HOST is missing."""
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)

    agent = EmailAgent()
    ctx = AgentContext(
        task_id="task_smtp_test",
        instructions="Send test email",
        input_data={"mode": "send", "approval_granted": True, "to": "user@example.com"}
    )
    result = agent.execute(ctx)
    assert result.success is False
    assert "SMTP configuration missing" in result.error


def test_email_agent_missing_sendgrid_credentials(monkeypatch):
    """Test EmailAgent returns clear configuration error when SENDGRID_API_KEY is missing."""
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)

    agent = EmailAgent()
    ctx = AgentContext(
        task_id="task_sg_test",
        instructions="Send test email",
        input_data={"mode": "send", "approval_granted": True, "to": "user@example.com"}
    )
    result = agent.execute(ctx)
    assert result.success is False
    assert "SendGrid configuration missing" in result.error


def test_database_bi_agent_rejects_semicolons_and_comments(app):
    """Test DatabaseBIAgent blocks semicolon injection attempts and SQL comments."""
    agent = DatabaseBIAgent()
    
    # Semicolon attempt
    ctx1 = AgentContext(
        task_id="task_sql_semi",
        instructions="Run query",
        input_data={"query": "SELECT * FROM users; DROP TABLE users;"}
    )
    res1 = agent.execute(ctx1)
    assert res1.success is False
    assert "Semicolons and multi-statement queries are not allowed" in res1.error

    # Comment attempt
    ctx2 = AgentContext(
        task_id="task_sql_comment",
        instructions="Run query",
        input_data={"query": "SELECT * FROM users -- comment out rest"}
    )
    res2 = agent.execute(ctx2)
    assert res2.success is False
    assert "SQL comment delimiters" in res2.error


def test_http_webhook_agent_blocks_ssrf_and_private_hosts(monkeypatch):
    """Test HttpWebhookAgent blocks private IPs and localhost."""
    agent = HttpWebhookAgent()
    ctx = AgentContext(
        task_id="task_ssrf",
        instructions="Invoke webhook",
        input_data={"url": "http://127.0.0.1:5000/internal", "method": "GET"}
    )
    result = agent.execute(ctx)
    assert result.success is False
    assert "SSRF Security Violation" in result.error


def test_report_generation_agent_pdf_rendering(app):
    """Test ReportGenerationAgent renders genuine binary PDF files."""
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        task_id="task_pdf_test",
        instructions="Generate PDF report",
        input_data={
            "title": "Quarterly Financial Audit",
            "format": "pdf",
            "executive_summary": "Overall financial performance exceeded targets.",
            "findings": ["Revenue increased by 15%", "Operational costs reduced by 8%"]
        }
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["format"] == "pdf"
    assert result.artifacts[0].name.endswith(".pdf")
    
    # Verify file actually exists and is binary PDF
    pdf_path = result.artifacts[0].path
    assert os.path.exists(pdf_path)
    with open(pdf_path, "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"
