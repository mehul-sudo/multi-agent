"""
Comprehensive Verification Suite: Professional HTML Email & Universal Multi-Agent Output Propagation.

Validates:
1. Professional Agent-Aware HTML Email Generation:
   - Data Analysis: HTML table of descriptive statistics (Mean, Median, Range, Std Dev, Total), Outliers alert, Insights.
   - Security Analysis: Risk score gauge, severity breakdown badges, vulnerability cards with severity badge, evidence code block, remediation recommendation.
   - Database & BI: Monospace SQL block, KPI metric cards, Query results HTML table.
   - Document Research: Grounded synthesis, key takeaways, citations cards with document title, page number, excerpt.
   - HTTP / Webhook: Status code badge (200 OK vs 500 FAILED), target endpoint, response payload.
   - Report Generation: Title, summary, download links, attachment info.
   - Deliverables & Attachments: Attached file details, format badge, download instructions.
   - Executive Footer: Clearly separated from business findings, status badge, timestamp, platform trace.
   - Untrusted Input Sanitization: html.escape applied to prevent injection attacks.
2. Direct Agent -> Email Flows:
   - Data Analysis -> Email
   - Security Analysis -> Email
   - HTTP/Webhook -> Email
   - Database & BI -> Email
   - Document Research -> Email
   - Multi-Node: Data Analysis -> Security Analysis -> Email
3. Approval Flow Verification:
   - Proposed output contains real synthesized body & HTML preview (never generic placeholder).
   - Upon approval, resume_execution_after_approval dispatches real agent findings to Resend.
   - Resend payload contains payload["html"] with rich formatting and payload["text"] with clean text.
"""

import os
import re
import json
import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.task_execution import (
    TASK_STATUS_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TaskExecution,
)
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_ALWAYS,
    DEPENDENCY_TYPE_ON_SUCCESS,
    WorkflowDependency,
)
from app.models.workflow_execution import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_QUEUED,
    WorkflowExecution,
)
from app.models.workflow_node import WorkflowNode
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.services.execution_engine import (
    AgentExecutor,
    ExecutionResult,
    WorkflowExecutionEngine,
)
from app.agents.base import AgentContext
from app.agents.email_agent import EmailAgent
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.security_analysis_agent import SecurityAnalysisAgent
from app.agents.http_webhook_agent import HttpWebhookAgent
from app.agents.database_bi_agent import DatabaseBIAgent
from app.agents.document_research_agent import DocumentResearchAgent
from app.agents.report_generation_agent import ReportGenerationAgent


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

def create_test_agents(user_id):
    agents = {}
    for ag_type, name in [
        ("data_analysis", "Market Data Analyst"),
        ("security_analysis", "Security Auditor"),
        ("database_bi", "BI Telemetry Engine"),
        ("document_research", "Doc Evidence Researcher"),
        ("http_webhook", "API Gateway Probe"),
        ("report_generation", "Executive Report Generator"),
        ("email", "Enterprise Dispatcher"),
    ]:
        ag = Agent(
            user_id=user_id,
            name=name,
            agent_type=ag_type,
            status=AGENT_STATUS_ACTIVE,
            system_instructions="Execute assigned tasks accurately.",
            configuration={},
        )
        db.session.add(ag)
        agents[ag_type] = ag
    db.session.commit()
    return agents


# ---------------------------------------------------------------------------
# 1. HTML GENERATOR TESTS
# ---------------------------------------------------------------------------

def test_html_email_data_analysis_table_and_metrics():
    """Verify Data Analysis output is rendered as a clean HTML statistics table with insights and outlier alert."""
    agent = EmailAgent()
    upstream = [{
        "agent_type": "data_analysis",
        "node_id": "da_1",
        "node_name": "Revenue Analytics",
        "output": {
            "rowCount": 250,
            "columns": ["revenue", "units_sold"],
            "summary": "Q3 Revenue performance audit across 250 transaction batches.",
            "statistics": {
                "revenue": {
                    "mean": 14250.50,
                    "median": 13900.00,
                    "min": 2100.00,
                    "max": 48900.00,
                    "std": 3410.25,
                    "sum": 3562625.00,
                    "outliers": [48900.00, 47500.00],
                },
                "units_sold": {
                    "mean": 85.2,
                    "median": 80.0,
                    "min": 10,
                    "max": 320,
                    "std": 22.4,
                    "sum": 21300,
                }
            },
            "insights": [
                "Strong 18% month-over-month revenue velocity in enterprise tier.",
                "Median transaction value stable at $13,900 with tight dispersion."
            ],
            "aggregations": {
                "Total Gross Volume": "$3,562,625.00",
                "Average Order Value": "$14,250.50"
            }
        }
    }]

    html = agent._build_professional_html_email(
        subject="Q3 Revenue Intelligence Briefing",
        body_markdown="Summary text",
        upstream_records=upstream,
        attachments=[],
    )

    # Validate structure & styling
    assert "<table" in html
    assert "Metric / Column" in html
    assert "Mean" in html
    assert "Median" in html
    assert "Range (Min – Max)" in html
    assert "Std Dev" in html
    assert "Total" in html
    assert "revenue" in html
    assert "14250.5" in html
    assert "3562625.0" in html
    assert "Outlier Anomalies" in html
    assert "48900.0" in html
    assert "Statistical Insights & Trends" in html
    assert "Strong 18% month-over-month revenue velocity" in html
    assert "Total Gross Volume" in html
    assert "Pipeline Execution Status:" in html
    assert "Completed Successfully" in html


def test_html_email_security_analysis_badges_and_vulnerabilities():
    """Verify Security Analysis output renders score gauge, severity breakdown badges, and vulnerability cards."""
    agent = EmailAgent()
    upstream = [{
        "agent_type": "security_analysis",
        "node_id": "sec_1",
        "node_name": "API Security Scan",
        "output": {
            "scannedTarget": "auth/token_service.py",
            "security_score": 42,
            "findings_by_severity": {"critical": 1, "high": 2, "medium": 1, "low": 0},
            "findings": [
                {
                    "title": "SQL Injection in User Authentication",
                    "severity": "CRITICAL",
                    "line": 84,
                    "evidence": "db.execute(f'SELECT * FROM users WHERE token = {token}')",
                    "remediation": "Use parameterized prepared statements with bind variables."
                },
                {
                    "title": "Hardcoded JWT Secret Token",
                    "severity": "HIGH",
                    "line": 23,
                    "evidence": "SECRET_KEY = 'super_secret_dev_key'",
                    "remediation": "Load encryption secret from environment vault at runtime."
                }
            ],
            "recommendations": [
                "Rotate all exposed dev tokens immediately.",
                "Enforce static code analysis in CI/CD pipeline."
            ]
        }
    }]

    html = agent._build_professional_html_email(
        subject="Critical Security Audit Alert",
        body_markdown="Security audit body",
        upstream_records=upstream,
        attachments=[],
    )

    # Validate score badge, severity badges, and remediation
    assert "Security Vulnerability & Threat Assessment" in html
    assert "Score: 42/100 (HIGH RISK)" in html
    assert "CRITICAL: 1" in html
    assert "HIGH: 2" in html
    assert "auth/token_service.py" in html
    assert "SQL Injection in User Authentication" in html
    assert "Line 84" in html
    assert "Use parameterized prepared statements" in html
    assert "Hardcoded JWT Secret Token" in html
    assert "Rotate all exposed dev tokens immediately" in html
    assert "Pipeline Execution Status:" in html


def test_html_email_database_bi_and_query_results():
    """Verify Database & BI output renders SQL block, KPIs, and results table."""
    agent = EmailAgent()
    upstream = [{
        "agent_type": "database_bi",
        "node_id": "db_1",
        "node_name": "Postgres Analytics",
        "output": {
            "query": "SELECT region, SUM(amount) AS total, COUNT(*) AS deals FROM sales GROUP BY region ORDER BY total DESC",
            "rowCount": 3,
            "kpis": {
                "Total Revenue": "$4,820,000",
                "Total Transactions": "1,420",
                "Top Region": "North America"
            },
            "columns": ["region", "total", "deals"],
            "rows": [
                {"region": "North America", "total": "$2,400,000", "deals": 720},
                {"region": "EMEA", "total": "$1,620,000", "deals": 510},
                {"region": "APAC", "total": "$800,000", "deals": 190}
            ],
            "insights": ["North America accounts for 50% of global deal volume."]
        }
    }]

    html = agent._build_professional_html_email(
        subject="Sales Operations Telemetry",
        body_markdown="Database briefing",
        upstream_records=upstream,
        attachments=[],
    )

    assert "Database Business Intelligence & Performance" in html
    assert "SELECT region, SUM(amount) AS total" in html
    assert "Total Revenue" in html
    assert "$4,820,000" in html
    assert "North America" in html
    assert "$2,400,000" in html
    assert "EMEA" in html
    assert "North America accounts for 50%" in html


def test_html_email_document_research_citations():
    """Verify Document Research renders grounded synthesis and citations cards."""
    agent = EmailAgent()
    upstream = [{
        "agent_type": "document_research",
        "node_id": "doc_1",
        "node_name": "SOC2 Policy Research",
        "output": {
            "answer": "The organization enforces quarterly access reviews and automated log retention for 365 days.",
            "key_takeaways": [
                "Quarterly access audits mandated for all production environments.",
                "Log retention immutable storage policy enforced."
            ],
            "citations": [
                {
                    "documentName": "SOC2_Security_Policy_2026.pdf",
                    "page": 14,
                    "excerpt": "Access review certifications must be signed off by department heads every 90 days."
                }
            ]
        }
    }]

    html = agent._build_professional_html_email(
        subject="Compliance Evidence Summary",
        body_markdown="Doc briefing",
        upstream_records=upstream,
        attachments=[],
    )

    assert "Document Research & Grounded Evidence" in html
    assert "The organization enforces quarterly access reviews" in html
    assert "SOC2_Security_Policy_2026.pdf • Page 14" in html
    assert "Access review certifications must be signed off" in html


def test_html_email_http_webhook_success_and_failure():
    """Verify HTTP/Webhook renders status badge, latency, endpoint, and payload block."""
    agent = EmailAgent()

    # Success case
    upstream_ok = [{
        "agent_type": "http_webhook",
        "node_id": "wh_1",
        "node_name": "Stripe Webhook",
        "output": {
            "method": "POST",
            "url": "https://api.stripe.com/v1/refunds",
            "statusCode": 200,
            "durationMs": 145,
            "response_body": {"id": "re_12345", "status": "succeeded", "amount": 4900}
        }
    }]
    html_ok = agent._build_professional_html_email(
        subject="Stripe Telemetry", body_markdown="ok", upstream_records=upstream_ok, attachments=[]
    )
    assert "HTTP 200 OK in 145ms" in html_ok
    assert "POST https://api.stripe.com/v1/refunds" in html_ok
    assert "re_12345" in html_ok
    assert "Completed Successfully" in html_ok

    # Failure case
    upstream_err = [{
        "agent_type": "http_webhook",
        "node_id": "wh_2",
        "node_name": "Billing Gateway",
        "output": {
            "method": "POST",
            "url": "https://billing.internal.net/charge",
            "statusCode": 502,
            "durationMs": 3020,
            "error": "Bad Gateway: Upstream billing cluster unreachable."
        }
    }]
    html_err = agent._build_professional_html_email(
        subject="Billing Failure Alert", body_markdown="err", upstream_records=upstream_err, attachments=[]
    )
    assert "HTTP 502 FAILED in 3020ms" in html_err
    assert "Bad Gateway: Upstream billing cluster unreachable" in html_err
    assert "Notice: Upstream Warnings / Failures" in html_err


def test_html_email_attachment_card_and_physical_file(tmp_path):
    """Verify attachment details card is included when physical deliverables are attached."""
    report_file = tmp_path / "Quarterly_Audit_Report.pdf"
    report_file.write_bytes(b"%PDF-1.4 Mock Executive PDF Content")

    agent = EmailAgent()
    html = agent._build_professional_html_email(
        subject="Audit Deliverable",
        body_markdown="Audit report attached",
        upstream_records=[],
        attachments=[str(report_file)],
    )

    assert "Included Deliverables & Attachments" in html
    assert "Quarterly_Audit_Report.pdf" in html
    assert "PDF" in html
    assert "The physical file(s) listed above have been attached directly" in html


def test_html_email_escapes_malicious_untrusted_input():
    """Verify HTML injection attempts are safely sanitized via html.escape."""
    agent = EmailAgent()
    malicious_upstream = [{
        "agent_type": "security_analysis",
        "node_id": "sec_xss",
        "node_name": "<script>alert('pwned')</script>",
        "output": {
            "scannedTarget": "<img src=x onerror=alert('xss')>",
            "security_score": 10,
            "findings": [
                {
                    "title": "<script>evil()</script> XSS Vulnerability",
                    "severity": "CRITICAL",
                    "evidence": "<iframe src='evil.com'></iframe>",
                    "remediation": "<b onmouseover='alert(1)'>Sanitize</b>"
                }
            ]
        }
    }]

    html = agent._build_professional_html_email(
        subject="<script>alert(1)</script>",
        body_markdown="normal",
        upstream_records=malicious_upstream,
        attachments=[],
    )

    # Ensure raw injection tags DO NOT exist
    assert "<script>alert('pwned')</script>" not in html
    assert "<img src=x onerror=alert('xss')>" not in html
    assert "<iframe src='evil.com'></iframe>" not in html
    assert "<b onmouseover=" not in html

    # Ensure escaped versions exist
    assert "&lt;script&gt;evil()&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(&#x27;xss&#x27;)&gt;" in html or "&lt;img src=x onerror=alert('xss')&gt;" in html


# ---------------------------------------------------------------------------
# 2. END-TO-END WORKFLOW INTEGRATION TESTS
# ---------------------------------------------------------------------------

class MockRealisticExecutor(AgentExecutor):
    """Deterministic agent executor generating real domain outputs for end-to-end tests."""
    def __init__(self):
        super().__init__()
        self.recorded_emails = []

    def execute(self, agent, instructions, inputs, config=None):
        ag_type = agent.agent_type if agent else "custom"
        task_id = f"t_{uuid.uuid4().hex[:8]}"

        if ag_type == "data_analysis":
            ctx = AgentContext(user_id=1, task_id=task_id, input_data=inputs, instructions=instructions)
            res = DataAnalysisAgent().execute(ctx)
            return ExecutionResult(success=res.success, output=res.output, error=res.error)

        elif ag_type == "security_analysis":
            ctx = AgentContext(user_id=1, task_id=task_id, input_data=inputs, instructions=instructions)
            res = SecurityAnalysisAgent().execute(ctx)
            return ExecutionResult(success=res.success, output=res.output, error=res.error)

        elif ag_type == "http_webhook":
            ctx = AgentContext(user_id=1, task_id=task_id, input_data=inputs, instructions=instructions)
            res = HttpWebhookAgent().execute(ctx)
            return ExecutionResult(success=res.success, output=res.output, error=res.error)

        elif ag_type == "database_bi":
            ctx = AgentContext(user_id=1, task_id=task_id, input_data=inputs, instructions=instructions)
            res = DatabaseBIAgent().execute(ctx)
            return ExecutionResult(success=res.success, output=res.output, error=res.error)

        elif ag_type == "document_research":
            ctx = AgentContext(user_id=1, task_id=task_id, input_data=inputs, instructions=instructions)
            res = DocumentResearchAgent().execute(ctx)
            return ExecutionResult(success=res.success, output=res.output, error=res.error)

        elif ag_type == "email":
            ctx = AgentContext(user_id=1, task_id=task_id, input_data=inputs, instructions=instructions)
            res = EmailAgent().execute(ctx)
            if res.success and res.output:
                self.recorded_emails.append(res.output)
            return ExecutionResult(
                success=res.success,
                output=res.output,
                error=res.error,
                requires_approval=res.requires_approval,
                approval_details=res.approval_details,
            )

        return ExecutionResult(success=True, output={"status": "completed"})


def test_data_analysis_to_email_e2e_contains_real_metrics_and_html(app, test_user):
    """Test Data Analysis -> Email passes real statistics table and clean body (no generic message)."""
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data Analysis Direct to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Empirical Sales Analysis",
            priority=1,
            configuration={"numbers": "100, 250, 400, 550, 700", "summary": "Five-point sales dataset"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Executive Sales Dispatcher",
            priority=2,
            configuration={"to": "exec@company.com", "mode": "draft"}
        )
        db.session.add_all([n_da, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = MockRealisticExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED
        assert len(executor.recorded_emails) == 1

        email_payload = executor.recorded_emails[0]
        body = email_payload["body"]
        html = email_payload.get("html", "")

        # Verify NO generic text
        assert "Automated workflow task execution completed successfully" not in body
        assert "Automated workflow task execution completed successfully" not in html

        # Verify REAL calculated statistics
        assert "Mean:" in body
        assert "400.0" in body
        assert "Range: `[100 – 700]`" in body or "[100" in body
        assert "Total: `2000`" in body or "2000" in body

        # Verify HTML has styled table
        assert "<table" in html
        assert "Metric / Column" in html
        assert "400.0" in html
        assert "2000" in html


def test_multi_node_data_analysis_plus_security_to_email_e2e(app, test_user):
    """Test 3-Node Workflow: Data Analysis -> Security Analysis -> Email synthesizes both agents' real outputs."""
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data plus Security to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Metrics Analyzer",
            priority=1,
            configuration={"numbers": "12, 14, 18, 24, 32", "summary": "Latency metrics"}
        )
        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["security_analysis"].id,
            name="Security Scanner",
            priority=2,
            configuration={"source_code": "def query(): cursor.execute('SELECT * FROM users WHERE id = ' + uid)", "scan_type": "code_vulnerability"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Executive Briefing Dispatcher",
            priority=3,
            configuration={"to": "board@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_da, n_sec, n_email])
        db.session.commit()

        # Chain: DA -> SEC -> EMAIL
        db.session.add(WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_sec.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS))
        db.session.add(WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS))
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = MockRealisticExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED
        email_payload = executor.recorded_emails[0]
        body = email_payload["body"]
        html = email_payload.get("html", "")

        # Verify NO generic text
        assert "Automated workflow task execution completed successfully" not in body

        # Verify BOTH agents' findings are present
        assert "Empirical Data Analysis Findings" in body or "data_analysis" in body.lower() or "Mean:" in body
        assert "Security Vulnerability" in body or "SQL" in body or "score" in body.lower()
        assert "<table" in html
        assert "🛡️ Security Vulnerability & Threat Assessment" in html


def test_approval_flow_and_resend_dispatch_with_real_findings(app, test_user):
    """Test Email requiring human approval displays real synthesized findings, and upon approval sends real HTML via Resend."""
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Approval Flow Real Telemetry", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["security_analysis"].id,
            name="Core Engine Scanner",
            priority=1,
            configuration={"source_code": "eval(user_input)", "scan_type": "code_vulnerability"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Production Alert Sender",
            priority=2,
            configuration={"to": "security-response@company.com", "mode": "send"}
        )
        db.session.add_all([n_sec, n_email])
        db.session.commit()

        db.session.add(WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS))
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = MockRealisticExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # 1. Pipeline should pause for human approval
        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None

        # Verify proposed output preview contains REAL body and HTML (not generic text)
        proposed = appr.proposed_output
        assert "Automated workflow task execution completed successfully" not in proposed["body"]
        assert "Security Vulnerability" in proposed["body"] or "eval" in proposed["body"]
        assert "<table" in proposed.get("html", "") or "🛡️ Security" in proposed.get("html", "")

        # 2. Approve and Resume Execution with Resend mock
        appr.status = "approved"
        db.session.commit()

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "resend_msg_test_8877"}
            mock_post.return_value.text = '{"id": "resend_msg_test_8877"}'

            resumed_exec = engine.resume_execution_after_approval(
                execution_id=execution.id,
                task_execution_id=appr.task_execution_id,
                approval=appr,
            )

            assert resumed_exec.status == EXECUTION_STATUS_COMPLETED

            # Verify Resend API request payload
            assert mock_post.called
            post_kwargs = mock_post.call_args[1]
            sent_payload = post_kwargs["json"]

            assert "to" in sent_payload
            assert "subject" in sent_payload
            assert "html" in sent_payload
            assert "text" in sent_payload

            # Verify NO generic text in sent email
            assert "Automated workflow task execution completed successfully" not in sent_payload["text"]
            assert "Automated workflow task execution completed successfully" not in sent_payload["html"]

            # Verify real security findings in sent HTML and text
            assert "Security Vulnerability" in sent_payload["text"] or "eval" in sent_payload["text"]
            assert "🛡️ Security Vulnerability & Threat Assessment" in sent_payload["html"]
            assert "Pipeline Execution Status:" in sent_payload["html"]


def test_html_email_markdown_parsing_and_clean_inline_html():
    """Verify that multi-level markdown in agent summaries is cleanly transformed into styled HTML without raw markdown artifacts."""
    agent = EmailAgent()
    upstream = [{
        "agent_type": "data_analysis",
        "node_id": "da_1",
        "node_name": "Deep Data Analysis",
        "output": {
            "rowCount": 500,
            "columns": ["volume", "price"],
            "summary": """# Quantitative Performance & Statistical Analysis Report
## Executive Summary
This report delivers an empirical analysis of operational datasets.

---

## Key Statistical Insights
### 1. Central Tendency & Dispersion
* **Volume (`units`)**:
  * **Mean**: 4.35
  * **Median**: 4.00
  * **Std Dev**: 1.25
* **Revenue (`usd`)**: High stability

> Critical takeaway: Transaction volumes exhibit low volatility.
""",
            "statistics": {
                "volume": {"mean": 4.35, "median": 4.00, "min": 1, "max": 10, "std": 1.25, "sum": 2175}
            }
        }
    }]

    html = agent._build_professional_html_email(
        subject="Empirical Performance Report",
        body_markdown="Report body",
        upstream_records=upstream,
        attachments=[],
    )

    # 1. Heading tags with inline styles must exist
    assert "<h1 style=" in html
    assert "Quantitative Performance &amp; Statistical Analysis Report</h1>" in html
    assert "<h2 style=" in html
    assert "Executive Summary</h2>" in html
    assert "<h3 style=" in html
    assert "1. Central Tendency &amp; Dispersion</h3>" in html

    # 2. Lists and bold styling must exist
    assert "<ul style=" in html
    assert "<li style=" in html
    assert "<strong style=" in html
    assert "Volume" in html
    assert "<code style=" in html

    # 3. Blockquote and horizontal rule must exist
    assert "<blockquote style=" in html
    assert "<hr style=" in html

    # 4. Raw markdown symbols should NOT appear as unparsed heading leaders
    assert "# Quantitative Performance" not in html
    assert "## Executive Summary" not in html
    assert "### 1. Central Tendency" not in html


def test_html_email_multi_node_pipeline_sequence():
    """Verify that workflows with multiple upstream nodes display a clean breadcrumb flow at the top of the email."""
    agent = EmailAgent()
    upstream = [
        {
            "agent_type": "data_analysis",
            "node_id": "node_1",
            "node_name": "Data Analytics",
            "status": "completed",
            "output": {"rowCount": 100, "summary": "Dataset analyzed."},
        },
        {
            "agent_type": "security_analysis",
            "node_id": "node_2",
            "node_name": "Security Audit",
            "status": "completed",
            "output": {"security_score": 85, "summary": "Zero critical CVEs found."},
        },
    ]

    html = agent._build_professional_html_email(
        subject="Multi-Stage Pipeline Execution Briefing",
        body_markdown="Workflow executed",
        upstream_records=upstream,
        attachments=[],
    )

    assert "Multi-Node Pipeline:" in html
    assert "Data Analysis" in html
    assert "Security Analysis" in html
    assert "Email Dispatcher" in html
    assert "&rarr;" in html


def test_html_email_universal_custom_agent_card():
    """Verify that any custom or non-standard agent node renders an executive card with clean HTML output."""
    agent = EmailAgent()
    upstream = [{
        "agent_type": "custom_lead_scorer",
        "node_id": "custom_1",
        "node_name": "Lead Scorer 9000",
        "status": "completed",
        "output": {
            "summary": "### Scored 50 Accounts\n* **Tier 1**: 12 leads\n* **Tier 2**: 38 leads",
            "average_score": 88.5,
        }
    }]

    html = agent._build_professional_html_email(
        subject="Custom Pipeline Result",
        body_markdown="Custom body",
        upstream_records=upstream,
        attachments=[],
    )

    assert "Lead Scorer 9000" in html
    assert "Pipeline Output" in html
    assert "<h3 style=" in html
    assert "Scored 50 Accounts" in html
    assert "<strong style=" in html
    assert "Tier 1" in html

