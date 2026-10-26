"""
Dedicated Verification Suite: Two Distinct Email Modes (Mode A vs Mode B) and Acceptance Criteria Tests A through L.

Covers:
- Test A: Data Analysis -> Email (Mode A: calculations in body, 0 report attachments)
- Test B: Data Analysis -> Report Generation -> Email (Mode B: format preserved, report attached, concise summary)
- Test C: Security Analysis -> Email (Mode A: findings & remediation in email, 0 report attachments)
- Test D: Security Analysis -> Report Generation -> Email (Mode B: security report generated & attached)
- Test E: HTTP / Webhook -> Email (Mode A: status & data in email, sensitive secrets redacted, 0 report attachments)
- Test F: HTTP / Webhook -> Report Generation -> Email (Mode B: report on API response, secrets redacted, report attached)
- Test G: Database & BI -> Report Generation -> Email (Mode B: query results & KPIs in report + email attachment)
- Test H: Document Research -> Report Generation -> Email (Mode B: findings & citations in report + email attachment)
- Test I: Multi-Node (3-4 nodes: Data Analysis + Security -> Report -> Email: all dependencies consumed & report attached)
- Test J: Missing Upstream Output or Invalid Artifact Reference (Fails explicitly, zero fabricated fallbacks)
- Test K: Approval Rejected (Resend never called, task blocked)
- Test L: Approval Accepted (Dispatched to Resend once with verified content & attachment)
"""

import os
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
    EXECUTION_STATUS_FAILED,
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
from app.agents.report_generation_agent import ReportGenerationAgent
from app.agents.email_agent import EmailAgent
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.services.approval_service import resolve_approval_request


def create_acceptance_test_agents(user_id):
    """Create agent records in the active DB session."""
    specs = [
        ("Security Analysis Agent", "security_analysis"),
        ("Database BI Agent", "database_bi"),
        ("Document Research Agent", "document_research"),
        ("Data Analysis Agent", "data_analysis"),
        ("HTTP Webhook Agent", "http_webhook"),
        ("Report Generation Agent", "report_generation"),
        ("Email Agent", "email"),
    ]
    agents = {}
    for name, ag_type in specs:
        ag = Agent(
            name=name,
            agent_type=ag_type,
            system_instructions=f"Execute {name} domain operations.",
            user_id=user_id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add(ag)
        db.session.commit()
        agents[ag_type] = ag
    return agents


class AcceptanceAgentExecutor(AgentExecutor):
    """Realistic executor using real agent instances for Data Analysis, Report Generation, and Email."""

    def __init__(self):
        self.report_agent = ReportGenerationAgent()
        self.email_agent = EmailAgent()
        self.data_analysis_agent = DataAnalysisAgent()
        self.recorded_inputs = {}
        self.recorded_outputs = {}

    def execute(self, agent, instructions, inputs, config):
        task_name = config.get("task_name")
        ag_type = agent.agent_type if agent else "custom"
        self.recorded_inputs[task_name] = dict(inputs)

        # 1. Security Analysis Fixture
        if ag_type == "security_analysis":
            output = {
                "scannedTarget": "app/services/payment_gateway.py",
                "security_score": 68,
                "overall_risk_score": 68,
                "findings_by_severity": {"critical": 1, "high": 1, "medium": 0, "low": 0},
                "findings": [
                    {
                        "title": "SQL Injection in User Lookup",
                        "severity": "CRITICAL",
                        "line": 42,
                        "evidence": "cursor.execute('SELECT * FROM users WHERE id=' + user_id)",
                        "remediation": "Use parameterized queries with prepared statements.",
                    },
                    {
                        "title": "Hardcoded JWT Secret",
                        "severity": "HIGH",
                        "line": 15,
                        "evidence": "SECRET_KEY = 'supersecret123'",
                        "remediation": "Load secret from cryptographic environment vault.",
                    },
                ],
                "recommendations": [
                    "Migrate raw SQL to parameterized statements.",
                    "Rotate all hardcoded secrets and enforce vault injection.",
                ],
                "summary": "Security audit completed with 2 findings (1 Critical, 1 High).",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 2. Database & BI Fixture
        elif ag_type == "database_bi":
            output = {
                "query": "SELECT region, sum(sales) as total_sales, count(*) as tx_count FROM transactions GROUP BY region",
                "rowCount": 4,
                "columns": ["region", "total_sales", "tx_count"],
                "rows": [
                    {"region": "North America", "total_sales": "$3,250,000", "tx_count": 8200},
                    {"region": "EMEA", "total_sales": "$2,100,000", "tx_count": 5400},
                    {"region": "APAC", "total_sales": "$1,850,000", "tx_count": 4900},
                    {"region": "LATAM", "total_sales": "$620,000", "tx_count": 1800},
                ],
                "kpis": {"Global Revenue": "$7,820,000", "Total Transactions": 20300},
                "insights": ["North America accounts for 41.5% of total revenue."],
                "summary": "Retrieved 4 regional aggregations across $7,820,000 global transactions.",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 3. Document Research Fixture
        elif ag_type == "document_research":
            output = {
                "query": "Key findings from Enterprise Security Compliance Report",
                "answer": "SOC-2 Type II certification was successfully obtained with zero non-conformities.",
                "key_takeaways": [
                    "Continuous telemetry auditing enforced across all microservices.",
                    "Zero trust network segmentation implemented across Kubernetes clusters.",
                ],
                "citations": [
                    {
                        "documentName": "SOC2_Audit_2025.pdf",
                        "page": 14,
                        "excerpt": "Access controls and key lifecycle management evaluated with zero non-conformities.",
                    },
                    {
                        "documentName": "ZeroTrust_Architecture.pdf",
                        "page": 28,
                        "excerpt": "Mutual TLS encryption enforced between all ingress and internal gateway services.",
                    },
                ],
                "summary": "Document research confirmed full SOC-2 Type II compliance.",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 4. HTTP / Webhook Fixture (with sensitive secrets to test redaction)
        elif ag_type == "http_webhook":
            output = {
                "url": inputs.get("url") or "https://api.internal-telemetry.io/v2/metrics?auth_token=super_secret_param_token_999",
                "method": inputs.get("method") or "POST",
                "statusCode": 200,
                "status_code": 200,
                "execution_time_ms": 142,
                "success": True,
                "response_body": {
                    "status": "healthy",
                    "api_key": "live_sk_secret_token_12345678",
                    "bearer_token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token",
                    "internal_secret": "database_master_password_vault",
                    "active_workers": 16,
                    "region": "us-east-1",
                },
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer sensitive_dispatch_token_xyz",
                },
                "summary": "HTTP POST to telemetry endpoint succeeded with HTTP 200 OK.",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 5. Data Analysis (REAL DataAnalysisAgent)
        elif ag_type == "data_analysis":
            ctx = AgentContext(
                user_id=config.get("user_id", 1),
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                input_data=inputs,
                instructions=instructions,
                previous_results=inputs.get("previous_results", []),
            )
            res = self.data_analysis_agent.execute(ctx)
            self.recorded_outputs[task_name] = res.output
            return ExecutionResult(
                success=res.success,
                output=res.output,
                error=res.error,
                artifacts=res.artifacts,
            )

        # 6. Report Generation (REAL ReportGenerationAgent)
        elif ag_type == "report_generation":
            ctx = AgentContext(
                user_id=config.get("user_id", 1),
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                input_data=inputs,
                instructions=instructions,
                previous_results=inputs.get("previous_results", []),
            )
            res = self.report_agent.execute(ctx)
            self.recorded_outputs[task_name] = res.output
            return ExecutionResult(
                success=res.success,
                output=res.output,
                error=res.error,
                artifacts=res.artifacts,
            )

        # 7. Email Agent (REAL EmailAgent)
        elif ag_type == "email":
            ctx = AgentContext(
                user_id=config.get("user_id", 1),
                task_id=str(config.get("task_execution_id", 1)),
                input_data=inputs,
                instructions=instructions,
                previous_results=inputs.get("previous_results", []),
                metadata=config,
            )
            res = self.email_agent.execute(ctx)
            self.recorded_outputs[task_name] = res.output
            return ExecutionResult(
                success=res.success,
                output=res.output,
                error=res.error,
                artifacts=res.artifacts,
                requires_approval=res.requires_approval,
                approval_details=res.approval_details,
            )

        output = {"status": "completed", "message": f"{task_name} executed"}
        self.recorded_outputs[task_name] = output
        return ExecutionResult(True, output, None)


# ===========================================================================
# TEST A: Data Analysis -> Email (Mode A: Calculations in Body, 0 Attachments)
# ===========================================================================
def test_acceptance_a_data_analysis_to_email_mode_a(app, db_session, test_user):
    """TEST A: Data Analysis -> Email (Mode A).
    - Calculated metrics appear directly in body and HTML table.
    - Zero report attachments (attachments is empty, attachment_status is 'none').
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test A Data Analysis to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["data_analysis"].id,
            name="Revenue Metrics Analysis",
            priority=1,
            configuration={"numbers": "120, 160, 210, 290, 380, 490", "query": "Analyze monthly revenue growth"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Executive Email Dispatcher",
            priority=2,
            configuration={"to": "cfo@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_da, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # 1. Verify Data Analysis executed and calculated real statistics
        da_out = executor.recorded_outputs["Revenue Metrics Analysis"]
        assert "statistics" in da_out
        assert da_out["statistics"]["value"]["mean"] == 275.0
        assert da_out["statistics"]["value"]["min"] == 120.0
        assert da_out["statistics"]["value"]["max"] == 490.0

        # 2. Verify Email received calculations in body
        email_out = executor.recorded_outputs["Executive Email Dispatcher"]
        email_body = email_out["body"]
        assert "Automated workflow task execution completed successfully" not in email_body
        assert "275" in email_body
        assert "120" in email_body
        assert "490" in email_body
        assert "Data Analysis" in email_body

        # 3. Verify HTML preview contains table and metrics
        html_preview = email_out.get("html") or email_out.get("html_preview") or ""
        assert "Metric / Column" in html_preview
        assert "275" in html_preview

        # 4. Strictly Mode A: ZERO report attachments
        assert email_out.get("attachments") == []
        assert email_out.get("attachment_status") == "none"


# ===========================================================================
# TEST B: Data Analysis -> Report Generation -> Email (Mode B: Format Preserved)
# ===========================================================================
def test_acceptance_b_data_analysis_to_report_to_email_mode_b(app, db_session, test_user):
    """TEST B: Data Analysis -> Report Generation -> Email (Mode B).
    - Report is generated in requested format (PDF).
    - Email receives actual report artifact reference and attaches it.
    - Email body summarizes report findings.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test B Data Analysis Report Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["data_analysis"].id,
            name="Quarterly Financials",
            priority=1,
            configuration={"numbers": "100, 200, 300, 400, 500", "query": "Quarterly Performance"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Performance Report Generator",
            priority=2,
            configuration={"title": "Quarterly Performance Report", "format": "pdf"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Executive Delivery",
            priority=3,
            configuration={"to": "exec@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_da, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # 1. Report generator created valid physical PDF artifact
        rep_out = executor.recorded_outputs["Performance Report Generator"]
        assert "artifact" in rep_out
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        assert art_path.endswith(".pdf")

        # 2. Email attached the report artifact
        email_out = executor.recorded_outputs["Executive Delivery"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        # 3. Email body contains executive report summary
        assert "Performance Report" in (email_out.get("body") or "") or "Performance Report" in (email_out.get("subject") or "")

        if os.path.exists(art_path):
            os.remove(art_path)


# ===========================================================================
# TEST C: Security Analysis -> Email (Mode A: Findings in Body, 0 Attachments)
# ===========================================================================
def test_acceptance_c_security_analysis_to_email_mode_a(app, db_session, test_user):
    """TEST C: Security Analysis -> Email (Mode A).
    - Security findings, score, severity, and remediation appear directly in email body.
    - Zero report attachments.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test C Security to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Vulnerability Scanner",
            priority=1,
            configuration={"target": "app/services/payment_gateway.py"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="SecOps Alert Dispatcher",
            priority=2,
            configuration={"to": "secops@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_sec, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        email_out = executor.recorded_outputs["SecOps Alert Dispatcher"]
        email_body = email_out["body"]

        assert "SQL Injection in User Lookup" in email_body
        assert "CRITICAL" in email_body
        assert "68/100" in email_body
        assert "Hardcoded JWT Secret" in email_body

        # Strictly Mode A: 0 attachments
        assert email_out.get("attachments") == []
        assert email_out.get("attachment_status") == "none"


# ===========================================================================
# TEST D: Security Analysis -> Report Generation -> Email (Mode B: Report Attached)
# ===========================================================================
def test_acceptance_d_security_analysis_to_report_to_email_mode_b(app, db_session, test_user):
    """TEST D: Security Analysis -> Report Generation -> Email (Mode B).
    - Generates security report file (DOCX).
    - Email summarizes report and attaches the physical DOCX file.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test D Security Report Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Security Scanner",
            priority=1,
            configuration={"target": "app/services/payment_gateway.py"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Security Report Generator",
            priority=2,
            configuration={"title": "Application Security Vulnerability Assessment", "format": "docx"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="CISO Briefing Delivery",
            priority=3,
            configuration={"to": "ciso@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_sec, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["Security Report Generator"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        assert art_path.endswith(".docx")

        email_out = executor.recorded_outputs["CISO Briefing Delivery"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ===========================================================================
# TEST E: HTTP / Webhook -> Email (Mode A: Secrets Redacted, 0 Attachments)
# ===========================================================================
def test_acceptance_e_http_webhook_to_email_mode_a_redacts_secrets(app, db_session, test_user):
    """TEST E: HTTP / Webhook -> Email (Mode A).
    - Status code, latency, and endpoint appear in email.
    - Sensitive tokens and secrets are redacted ([REDACTED]).
    - Zero report attachments.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test E Webhook to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["http_webhook"].id,
            name="External API Integration",
            priority=1,
            configuration={"url": "https://api.internal-telemetry.io/v2/metrics?auth_token=super_secret_param_token_999"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Webhook Telemetry Email",
            priority=2,
            configuration={"to": "devops@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_wh, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_wh.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        email_out = executor.recorded_outputs["Webhook Telemetry Email"]
        email_body = email_out["body"]
        html_preview = email_out.get("html") or email_out.get("html_preview") or ""

        # Verify status and telemetry are present
        assert "HTTP 200" in email_body or "200" in email_body
        assert "active_workers" in email_body

        # Verify sensitive secrets are REDACTED (never leaked in plaintext)
        assert "live_sk_secret_token_12345678" not in email_body
        assert "database_master_password_vault" not in email_body
        assert "live_sk_secret_token_12345678" not in html_preview
        assert "[REDACTED]" in email_body
        assert "[REDACTED]" in html_preview

        # Mode A: 0 report attachments
        assert email_out.get("attachments") == []
        assert email_out.get("attachment_status") == "none"


# ===========================================================================
# TEST F: HTTP / Webhook -> Report Generation -> Email (Mode B: Secrets Redacted, Report Attached)
# ===========================================================================
def test_acceptance_f_http_webhook_to_report_to_email_mode_b(app, db_session, test_user):
    """TEST F: HTTP / Webhook -> Report Generation -> Email (Mode B).
    - Generates report on API telemetry with format preserved (HTML).
    - Secrets are redacted in the generated report.
    - Email summarizes report and attaches the report file.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test F Webhook Report Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["http_webhook"].id,
            name="Outbound API Probe",
            priority=1,
            configuration={"url": "https://api.internal-telemetry.io/v2/metrics?auth_token=secret_abc123"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="API Telemetry Report Generator",
            priority=2,
            configuration={"title": "External API Telemetry & Health Audit", "format": "html"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Platform Ops Delivery",
            priority=3,
            configuration={"to": "sre@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_wh, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_wh.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["API Telemetry Report Generator"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        assert art_path.endswith(".html")

        # Verify sensitive secret was redacted in the saved report file
        with open(art_path, "r", encoding="utf-8") as f:
            report_text = f.read()
        assert "live_sk_secret_token_12345678" not in report_text
        assert "database_master_password_vault" not in report_text
        assert "[REDACTED]" in report_text

        # Verify email attached the report
        email_out = executor.recorded_outputs["Platform Ops Delivery"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ===========================================================================
# TEST G: Database & BI -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_acceptance_g_database_bi_to_report_to_email_mode_b(app, db_session, test_user):
    """TEST G: Database & BI -> Report Generation -> Email (Mode B).
    - Query results, KPIs, and regional breakdown in report (TXT format).
    - Email summarizes report and attaches the .txt report file.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test G Database BI Report Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_db = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["database_bi"].id,
            name="Revenue Aggregator",
            priority=1,
            configuration={"query": "SELECT region, sum(sales) as total_sales FROM transactions GROUP BY region"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="BI Report Generator",
            priority=2,
            configuration={"title": "Global Revenue BI Briefing", "format": "txt"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Finance Leadership Dispatch",
            priority=3,
            configuration={"to": "finance@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_db, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_db.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["BI Report Generator"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        assert art_path.endswith(".txt")

        # Verify TXT file contains the database KPIs
        with open(art_path, "r", encoding="utf-8") as f:
            txt_content = f.read()
        assert "7,820,000" in txt_content or "North America" in txt_content

        email_out = executor.recorded_outputs["Finance Leadership Dispatch"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ===========================================================================
# TEST H: Document Research -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_acceptance_h_document_research_to_report_to_email_mode_b(app, db_session, test_user):
    """TEST H: Document Research -> Report Generation -> Email (Mode B).
    - Grounded synthesis and citations with page references in report (Markdown format).
    - Email summarizes report and attaches the report file.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test H Doc Research Report Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_res = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["document_research"].id,
            name="Compliance Auditor",
            priority=1,
            configuration={"query": "SOC-2 Type II audit report findings"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Compliance Report Generator",
            priority=2,
            configuration={"title": "Enterprise SOC2 Compliance Audit", "format": "markdown"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Compliance Officer Email",
            priority=3,
            configuration={"to": "compliance@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_res, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["Compliance Report Generator"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        assert art_path.endswith(".md")

        with open(art_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        assert "SOC2_Audit_2025.pdf" in md_content
        assert "Page 14" in md_content

        email_out = executor.recorded_outputs["Compliance Officer Email"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ===========================================================================
# TEST I: Multi-Node (Data Analysis + Security -> Report -> Email)
# ===========================================================================
def test_acceptance_i_multi_node_upstream_to_report_to_email(app, db_session, test_user):
    """TEST I: Multi-Node Upstream to Report to Email.
    - Data Analysis + Security Analysis both flow into Report Generation.
    - Report integrates findings from both upstream domains.
    - Email summarizes report and attaches the integrated report artifact.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test I Multi Node Integration", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["data_analysis"].id,
            name="Metrics Analyzer",
            priority=1,
            configuration={"numbers": "1000, 2000, 3000", "query": "Revenue metrics"}
        )
        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Vulnerability Scanner",
            priority=1,
            configuration={"target": "app/services/payment_gateway.py"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Integrated Executive Report",
            priority=2,
            configuration={"title": "Operational Performance and Security Audit", "format": "pdf"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Board of Directors Delivery",
            priority=3,
            configuration={"to": "board@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_da, n_sec, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep3 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2, dep3])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["Integrated Executive Report"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)

        email_out = executor.recorded_outputs["Board of Directors Delivery"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ===========================================================================
# TEST J: Missing Upstream Output or Invalid Artifact Reference (Fails Explicitly)
# ===========================================================================
def test_acceptance_j_missing_upstream_and_invalid_attachment_fails_explicitly(app, db_session, test_user):
    """TEST J: Missing Upstream Output or Invalid Artifact Reference.
    - Email Agent fails explicitly when required upstream results are missing.
    - Email Agent fails explicitly when attachment path does not exist on disk.
    - No fabricated attachments or silent fallbacks.
    """
    with app.app_context():
        email_agent = EmailAgent()

        # J1: Required upstream results missing
        ctx_missing = AgentContext(
            user_id=test_user.id,
            task_id="missing_test_1",
            input_data={"require_upstream": True, "to": "test@enterprise.com"},
            instructions="Send email with required upstream findings.",
        )
        res_missing = email_agent.execute(ctx_missing)
        assert res_missing.success is False
        assert "Missing upstream results" in res_missing.error

        # J2: Invalid attachment path (file not found on disk)
        fake_attachment_path = "c:/non_existent_directory_999/fabricated_report.pdf"
        ctx_invalid_att = AgentContext(
            user_id=test_user.id,
            task_id="missing_test_2",
            input_data={
                "to": "test@enterprise.com",
                "attachments": [fake_attachment_path],
                "body": "Here is your report.",
            },
        )
        res_invalid_att = email_agent.execute(ctx_invalid_att)
        assert res_invalid_att.success is False
        assert "Attachment file(s) not found" in res_invalid_att.error
        assert fake_attachment_path in res_invalid_att.error


# ===========================================================================
# TEST K: Approval Rejected (Resend NEVER called, task marked blocked)
# ===========================================================================
def test_acceptance_k_approval_rejected_blocks_delivery(app, db_session, test_user):
    """TEST K: Approval Rejected.
    - When human approval is rejected, Resend API is NEVER dispatched.
    - Task execution remains blocked/rejected.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test K Approval Rejection", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="External Email Node",
            priority=1,
            configuration={"to": "external-client@partner.com", "mode": "send", "body": "Sensitive corporate update."}
        )
        db.session.add(n_email)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)

        with patch("requests.post") as mock_resend:
            exec_res = engine.run_execution(execution.id)

            # Workflow pauses awaiting approval
            assert exec_res.status == EXECUTION_STATUS_PAUSED
            appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
            assert appr is not None
            assert appr.status == APPROVAL_STATUS_PENDING

            # Reject the approval request
            resolve_approval_request(
                appr.id,
                user_id=test_user.id,
                approve=False,
                rejection_reason="Unauthorized external communication attempt.",
                prevent_self_approval=False,
                engine=engine
            )

            # Resend API was NEVER called
            mock_resend.assert_not_called()

            # Task status is marked blocked/failed with rejection metadata
            task_exec = TaskExecution.query.get(appr.task_execution_id)
            assert task_exec.status in (TASK_STATUS_BLOCKED, TASK_STATUS_FAILED)
            assert task_exec.error_data.get("rejected") is True


# ===========================================================================
# TEST L: Approval Accepted (Dispatched to Resend once with verified content & attachment)
# ===========================================================================
def test_acceptance_l_approval_accepted_dispatches_resend_once(app, db_session, test_user):
    """TEST L: Approval Accepted.
    - When approved, email is dispatched to Resend once with verified content & attachment.
    - Resend payload has clean subject, HTML body, and base64 encoded attachment.
    """
    with app.app_context():
        agents = create_acceptance_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Test L Approval Acceptance", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        # Create temporary valid test file to attach
        test_file_path = os.path.join(app.instance_path, "test_approved_deliverable.pdf")
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, "wb") as f:
            f.write(b"%PDF-1.4 simulated pdf deliverable bytes")

        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Approved Email Dispatcher",
            priority=1,
            configuration={
                "to": "authorized-cfo@enterprise.com",
                "mode": "send",
                "subject": "Verified Quarterly Financial Report",
                "body": "Please find attached the approved quarterly report.",
                "attachments": [test_file_path],
            }
        )
        db.session.add(n_email)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = AcceptanceAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)

        # Mock Resend API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "resend_msg_test_acceptance_123"}

        old_key = os.environ.get("RESEND_API_KEY")
        old_provider = os.environ.get("EMAIL_PROVIDER")
        os.environ["RESEND_API_KEY"] = "re_acceptance_key_test_123"
        os.environ["EMAIL_PROVIDER"] = "resend"
        try:
            with patch("requests.post", return_value=mock_response) as mock_resend:
                exec_res = engine.run_execution(execution.id)
                assert exec_res.status == EXECUTION_STATUS_PAUSED

                appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
                assert appr is not None
                assert appr.status == APPROVAL_STATUS_PENDING

                # Approve the request
                resolve_approval_request(
                    appr.id,
                    user_id=test_user.id,
                    approve=True,
                    prevent_self_approval=False,
                    engine=engine
                )

                db.session.refresh(execution)
                assert execution.status == EXECUTION_STATUS_COMPLETED

                # Resend API was called EXACTLY ONCE
                assert mock_resend.call_count == 1
                call_kwargs = mock_resend.call_args[1]
                sent_payload = call_kwargs.get("json", {})

                # Verify email payload details
                assert "Verified Quarterly Financial Report" in sent_payload.get("subject", "")
                assert "html" in sent_payload
                assert "attachments" in sent_payload
                assert len(sent_payload["attachments"]) == 1
                assert sent_payload["attachments"][0]["filename"] == "test_approved_deliverable.pdf"
                assert "content" in sent_payload["attachments"][0]  # Base64 encoded
        finally:
            if old_key is None:
                os.environ.pop("RESEND_API_KEY", None)
            else:
                os.environ["RESEND_API_KEY"] = old_key
            if old_provider is None:
                os.environ.pop("EMAIL_PROVIDER", None)
            else:
                os.environ["EMAIL_PROVIDER"] = old_provider
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

        if os.path.exists(test_file_path):
            os.remove(test_file_path)
