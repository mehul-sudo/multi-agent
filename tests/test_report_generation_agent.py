"""
Unit tests for ReportGenerationAgent.
"""

import os
import pytest
from app.agents.base import AgentContext
from app.agents.report_generation_agent import ReportGenerationAgent


def test_report_generation_agent_markdown():
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        input_data={
            "title": "Quarterly Performance Audit",
            "format": "markdown",
            "executive_summary": "Revenue increased 22% YoY across core enterprise tiers.",
            "findings": ["SaaS expansion in EU region", "Customer retention at 94%"],
            "recommendations": ["Expand EMEA support team", "Increase cloud capacity"],
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "report_generation"
    assert result.output["reportTitle"] == "Quarterly Performance Audit"
    assert result.output["format"] == "markdown"
    assert "artifact" in result.output
    assert os.path.exists(result.output["artifact"]["path"])

    # Clean up generated file
    if os.path.exists(result.output["artifact"]["path"]):
        os.remove(result.output["artifact"]["path"])


def test_report_generation_agent_html():
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        input_data={
            "title": "Security Vulnerability Summary",
            "format": "html",
            "summary": "All high-severity vulnerabilities remediated.",
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["format"] == "html"
    assert "<html>" in result.artifacts[0].content

    if os.path.exists(result.output["artifact"]["path"]):
        os.remove(result.output["artifact"]["path"])


def test_report_generation_agent_docx():
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        input_data={
            "title": "Enterprise Cloud Architecture",
            "format": "docx",
            "findings": ["Migration completed with 100% data fidelity", "Latency reduced by 40%"],
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["format"] == "docx"
    path = result.output["artifact"]["path"]
    assert os.path.exists(path)
    assert path.endswith(".docx")
    assert os.path.getsize(path) > 1000  # Valid binary DOCX file

    if os.path.exists(path):
        os.remove(path)


def test_report_generation_agent_pdf():
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        input_data={
            "title": "Compliance Audit Report",
            "format": "pdf",
            "summary": "Full compliance audit executed with zero high-risk findings.",
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["format"] == "pdf"
    path = result.output["artifact"]["path"]
    assert os.path.exists(path)
    assert path.endswith(".pdf")
    assert os.path.getsize(path) > 1000  # Valid binary PDF file

    if os.path.exists(path):
        os.remove(path)
