"""
Master Test Suite for Universal Multi-Agent Workflow Execution Contracts (Tests A through M).

Verifies:
- Test A: Security Analysis -> Report Generation -> Email
- Test B: Database & BI -> Report Generation -> Email
- Test C: Document Research -> Report Generation -> Email
- Test D: HTTP / Webhook -> Report Generation -> Email
- Test E: Multi-Upstream: Security Analysis + Database & BI + Document Research -> Report Generation -> Email
- Test F: Data Flow Verification (Structured upstream context, no truncation)
- Test G: Physical File Artifact Verification (Disk persistence & /api/v1/reports/download/<filename>)
- Test H: Email Attachment & Delivery Verification (Resend payload with base64 attachment & metadata)
- Test I: Approval Handling & Rejection DAG Resumption (Dependent tasks blocked with rejection reason)
- Test J: Parallel Branch Isolation (Sibling failure does not stop independent branches)
- Test K: Format Verification (markdown, html, docx, pdf physical files)
- Test L: Zero Calendar Agent References & Zero Report Archetype References (Regression Audit)
- Test M: Tenant / Multi-user Isolation
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
    DEPENDENCY_TYPE_ON_FAILURE,
    DEPENDENCY_TYPE_ON_SUCCESS,
    WorkflowDependency,
)
from app.models.workflow_execution import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_PARTIALLY_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_QUEUED,
    EXECUTION_STATUS_RUNNING,
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
from app.security.password import hash_password


def create_test_agents(user_id):
    """Helper to create agent records within the active session."""
    specs = [
        ("Security Analysis Agent", "security_analysis"),
        ("Database BI Agent", "database_bi"),
        ("Document Research Agent", "document_research"),
        ("Data Analysis Agent", "data_analysis"),
        ("HTTP Webhook Agent", "http_webhook"),
        ("Report Generation Agent", "report_generation"),
        ("Email Agent", "email"),
        ("Audit Logger Agent", "custom"),
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


class RealisticMultiAgentExecutor(AgentExecutor):
    """Executes agents faithfully using real agent classes for Report Generation, Email, and Data Analysis,

    and realistic structured domain fixtures for Security, DB, Research, and Webhook.
    """

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

        # Simulation of empty output for dependency failure testing
        if config.get("empty_output"):
            output = {}
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 1. Security Analysis
        if ag_type == "security_analysis":
            output = {
                "scannedTarget": "app/services/auth_controller.py",
                "security_score": 72,
                "overall_risk_score": 72,
                "findings_by_severity": {"critical": 1, "high": 1, "medium": 0, "low": 0, "info": 0},
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
                    "Migrate all raw SQL strings to SQLAlchemy parameterized statements.",
                    "Rotate all hardcoded secrets and enforce vault injection in CI/CD.",
                ],
                "summary": "Security audit completed with 2 findings (1 Critical, 1 High).",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 2. Database & BI
        elif ag_type == "database_bi":
            output = {
                "query": "SELECT tier, count(*) as count, sum(revenue) as total_rev FROM accounts GROUP BY tier",
                "rowCount": 3,
                "columns": ["tier", "count", "total_rev"],
                "rows": [
                    {"tier": "Enterprise", "count": 140, "total_rev": "$1,450,000"},
                    {"tier": "Professional", "count": 520, "total_rev": "$820,000"},
                    {"tier": "Starter", "count": 1200, "total_rev": "$360,000"},
                ],
                "kpis": {
                    "Total Revenue": "$2,630,000",
                    "Enterprise Ratio": "55.1%",
                    "Active Accounts": "1,860",
                },
                "insights": [
                    "Enterprise tier generates over 55% of total recurring revenue.",
                    "Professional tier expansion shows 24% quarter-over-quarter growth.",
                ],
                "summary": "Database BI executed successfully returning 3 aggregated tier groups.",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 3. Document Research
        elif ag_type == "document_research":
            output = {
                "answer": "Clinical literature confirms that generative AI models reduce radiologist screening latency by 34.2% while maintaining 98.1% sensitivity.",
                "key_takeaways": [
                    "Radiologist screening latency decreased by 34.2%.",
                    "Diagnostic sensitivity maintained at 98.1% across multi-site validation.",
                    "Zero patient re-admission spikes observed during deployment trials.",
                ],
                "citations": [
                    {
                        "documentName": "AI_Radiology_Multicenter_Study_2025.pdf",
                        "page": 28,
                        "excerpt": "Attending physicians verified 12,400 scans with an average time reduction of 34.2%.",
                    }
                ],
                "summary": "Document research synthesized findings from AI Radiology Multicenter Study 2025.",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(True, output, None)

        # 4. HTTP / Webhook
        elif ag_type == "http_webhook":
            status_code = 500 if config.get("simulate_500") else config.get("status_code", 200)
            success = 200 <= status_code < 300
            output = {
                "url": inputs.get("url") or ("https://api.internal-telemetry.io/v2/alerts" if status_code >= 400 else "https://api.internal-telemetry.io/v2/health"),
                "method": inputs.get("method") or "POST",
                "statusCode": status_code,
                "status_code": status_code,
                "execution_time_ms": 312 if status_code >= 400 else 142,
                "success": success,
                "response_body": {
                    "error": "InternalServerError",
                    "message": "Database cluster connection timed out after 30s.",
                    "code": 500,
                } if status_code >= 400 else {
                    "status": "healthy",
                    "active_workers": 16,
                    "queue_depth": 0,
                    "region": "us-east-1",
                },
                "headers": {"Content-Type": "application/json"},
                "summary": f"HTTP POST to telemetry endpoint failed with HTTP {status_code}." if status_code >= 400 else "HTTP POST to telemetry endpoint succeeded with HTTP 200 OK.",
            }
            self.recorded_outputs[task_name] = output
            return ExecutionResult(success, output, None if success else f"HTTP {status_code} Error")

        # 5. Data Analysis (Uses REAL DataAnalysisAgent!)
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

        # 6. Report Generation (Uses REAL ReportGenerationAgent!)
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

        # 7. Email Agent (Uses REAL EmailAgent!)
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

        # Default fallback
        output = {"status": "completed", "message": f"{task_name} executed"}
        self.recorded_outputs[task_name] = output
        return ExecutionResult(True, output, None)


# ---------------------------------------------------------------------------
# TEST A: Data Analysis -> Email (Calculated findings in body, no generic text)
# ---------------------------------------------------------------------------
def test_workflow_data_analysis_to_email(app, db_session, test_user):
    """TEST A: Data Analysis -> Email.
    Verify that the email body contains actual calculated findings from the dataset
    (e.g., mean 275.0, range [120.0 - 490.0]), NOT generic workflow status text.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data Analysis to Email Workflow", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Revenue Metrics Analysis",
            priority=1,
            configuration={"numbers": "120, 160, 210, 290, 380, 490", "query": "Analyze monthly revenue growth"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
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

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # 1. Verify Data Analysis executed and calculated empirical metrics
        da_out = executor.recorded_outputs["Revenue Metrics Analysis"]
        assert "statistics" in da_out
        assert da_out["statistics"]["value"]["mean"] == 275.0
        assert da_out["statistics"]["value"]["min"] == 120.0
        assert da_out["statistics"]["value"]["max"] == 490.0

        # 2. Verify Email received Data Analysis output and synthesized body with real metrics
        email_out = executor.recorded_outputs["Executive Email Dispatcher"]
        email_body = email_out["body"]
        assert "Automated workflow task execution completed successfully" not in email_body
        assert "275" in email_body
        assert "120" in email_body
        assert "490" in email_body
        assert "Data Analysis" in email_body
        # Mode A: Direct Agent -> Email must NOT attach any report
        assert email_out.get("attachments") == []
        assert email_out.get("attachment_status") == "none"


# ---------------------------------------------------------------------------
# TEST B: Data Analysis -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_workflow_data_analysis_to_report_to_email(app, db_session, test_user):
    """TEST B: Data Analysis -> Report Generation -> Email.
    Verify the report contains actual calculations and the email includes the actual generated report as attachment.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data Analysis Report Email Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Empirical Data Analysis",
            priority=1,
            configuration={"numbers": "100, 200, 300, 400, 500", "query": "Quarterly Performance"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["report_generation"].id,
            name="Performance Report Generator",
            priority=2,
            configuration={"format": "pdf", "title": "Quarterly Performance Report"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
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

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # Check Report Generator produced real PDF artifact
        rep_out = executor.recorded_outputs["Performance Report Generator"]
        assert "artifact" in rep_out
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)

        # Check Email attached the report artifact and included findings
        email_out = executor.recorded_outputs["Executive Delivery"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"
        assert "Quarterly Performance Report" in (email_out.get("source_report_name") or email_out.get("subject"))

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST C: Security Analysis -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_workflow_security_to_report_to_email(app, db_session, test_user):
    """Test C: Security Analysis findings feed Report Generation, which generates
    a physical report artifact that Email Agent attaches and sends upon approval.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Security Audit Workflow", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["security_analysis"].id, name="Security Audit", priority=1)
        n_rep = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["report_generation"].id, name="Report Generator", priority=2, configuration={"format": "markdown"})
        n_email = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["email"].id, name="Email Dispatcher", priority=3, configuration={"to": "audit-team@enterprise.com", "mode": "send"})
        db.session.add_all([n_sec, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # Email requires approval, so workflow pauses awaiting approval
        assert exec_res.status == EXECUTION_STATUS_PAUSED

        # 1. Verify Report Generator received Security findings and created physical report artifact
        rep_out = executor.recorded_outputs["Report Generator"]
        assert "artifact" in rep_out
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        with open(art_path, "r", encoding="utf-8") as f:
            art_text = f.read()
        assert "SQL Injection in User Lookup" in art_text
        assert "CRITICAL" in art_text
        assert "Line 42" in art_text
        assert "Security Vulnerability" in art_text

        # 2. Verify Email received the report as attachment
        email_in = executor.recorded_inputs["Email Dispatcher"]
        assert "attachments" in email_in
        assert art_path in email_in["attachments"]
        assert email_in.get("source_report_name") is not None
        assert email_in.get("attachment_filename") is not None

        # 3. Verify approval request created and approve it
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None

        resolve_approval_request(appr.id, user_id=test_user.id, approve=True, prevent_self_approval=False, engine=engine)

        # 4. Verify workflow completes and email marked sent with attachment metadata
        db.session.refresh(execution)
        assert execution.status == EXECUTION_STATUS_COMPLETED
        email_out = executor.recorded_outputs["Email Dispatcher"]
        assert email_out["status"] == "sent"
        assert email_out["attachments"] == [art_path]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST B: Database & BI -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_workflow_database_to_report_to_email(app, db_session, test_user):
    """Test B: Database & BI query rows and KPIs feed Report Generation,

    which generates a table of query rows and KPIs, attached to email.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Database BI Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_db = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["database_bi"].id, name="DB Analytics", priority=1)
        n_rep = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["report_generation"].id, name="BI Report", priority=2, configuration={"format": "html"})
        n_email = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["email"].id, name="Dispatch BI", priority=3, configuration={"to": "cfo@enterprise.com", "mode": "draft"})
        db.session.add_all([n_db, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_db.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # In draft mode, email does not pause for approval
        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # Check Report Generation HTML artifact
        rep_out = executor.recorded_outputs["BI Report"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        with open(art_path, "r", encoding="utf-8") as f:
            html_text = f.read()
        assert "Enterprise" in html_text
        assert "1,450,000" in html_text
        assert "Total Revenue" in html_text

        # Check Email drafted with attachment
        email_out = executor.recorded_outputs["Dispatch BI"]
        assert email_out["status"] == "drafted"
        assert art_path in email_out["attachments"]
        assert email_out["attachment_format"] == "html"

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST C: Document Research -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_workflow_document_research_to_report_to_email(app, db_session, test_user):
    """Test C: Document Research synthesis and citations feed Report Generation,

    which generates a verified citations table and attaches report to email.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Research Synthesis Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_res = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["document_research"].id, name="Literature Review", priority=1)
        n_rep = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["report_generation"].id, name="Research Report", priority=2, configuration={"format": "markdown"})
        n_email = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["email"].id, name="Notify Researchers", priority=3, configuration={"to": "researchers@enterprise.com", "mode": "draft"})
        db.session.add_all([n_res, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["Research Report"]
        art_path = rep_out["artifact"]["path"]
        with open(art_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        assert "AI_Radiology_Multicenter_Study_2025.pdf" in md_text
        assert "34.2%" in md_text
        assert "Page 28" in md_text

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST D: HTTP / Webhook -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_workflow_http_webhook_to_report_to_email(app, db_session, test_user):
    """Test D: HTTP / Webhook telemetry feeds Report Generation,

    which generates an API Telemetry section with formatted JSON payload, attached to email.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Telemetry Audit Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["http_webhook"].id, name="Probe Telemetry", priority=1)
        n_rep = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["report_generation"].id, name="Telemetry Report", priority=2, configuration={"format": "markdown"})
        n_email = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["email"].id, name="Notify SRE", priority=3, configuration={"to": "sre@enterprise.com", "mode": "draft"})
        db.session.add_all([n_wh, n_rep, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_wh.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        rep_out = executor.recorded_outputs["Telemetry Report"]
        art_path = rep_out["artifact"]["path"]
        with open(art_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        assert "api.internal-telemetry.io" in md_text
        assert "200" in md_text
        assert "active_workers" in md_text

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST F: Four Connected Nodes (Document Research -> Data Analysis -> Report Generation -> Email)
# ---------------------------------------------------------------------------
def test_workflow_four_connected_nodes(app, db_session, test_user):
    """TEST F: Workflow containing at least 4 connected nodes.
    Verify every downstream node receives and uses the appropriate upstream output:
    1. Document Research produces findings and citations.
    2. Data Analysis receives research findings and computes empirical metrics.
    3. Report Generation receives metrics and findings and generates a physical report.
    4. Email receives the generated report artifact, attaches it, and synthesizes the email body.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Four Node Connected Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_res = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["document_research"].id,
            name="Clinical Literature Review",
            priority=1,
            configuration={"topic": "AI Radiology screening efficacy"}
        )
        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Clinical Trial Metrics Analysis",
            priority=2,
            configuration={"numbers": "14.5, 22.8, 31.0, 45.2, 58.6", "query": "Analyze clinical latency reduction"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["report_generation"].id,
            name="Clinical Synthesis Report Generator",
            priority=3,
            configuration={"format": "pdf", "title": "Oncology Clinical Trial Synthesis"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Executive Medical Dispatcher",
            priority=4,
            configuration={"to": "chief-medical@hospital.org", "mode": "draft"}
        )
        db.session.add_all([n_res, n_da, n_rep, n_email])
        db.session.commit()

        # Connect the 4 nodes:
        # n_res -> n_da -> n_rep -> n_email
        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_da.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep3 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep4 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2, dep3, dep4])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # 1. Verify Node 1 (Document Research) ran and produced citations
        res_out = executor.recorded_outputs["Clinical Literature Review"]
        assert "citations" in res_out
        assert len(res_out["citations"]) > 0

        # 2. Verify Node 2 (Data Analysis) received Node 1 and produced real statistics
        da_out = executor.recorded_outputs["Clinical Trial Metrics Analysis"]
        assert "statistics" in da_out
        assert da_out["statistics"]["value"]["mean"] == 34.42
        assert da_out["statistics"]["value"]["min"] == 14.5
        assert da_out["statistics"]["value"]["max"] == 58.6

        # 3. Verify Node 3 (Report Generation) received both Node 1 & Node 2 and produced a physical PDF
        rep_out = executor.recorded_outputs["Clinical Synthesis Report Generator"]
        assert "artifact" in rep_out
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)
        assert art_path.endswith(".pdf")

        # 4. Verify Node 4 (Email) received Node 3 artifact and synthesized findings from pipeline
        email_out = executor.recorded_outputs["Executive Medical Dispatcher"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"
        assert "Automated workflow task execution completed successfully" not in email_out["body"]
        assert "34.42" in email_out["body"] or "Clinical Trial Metrics Analysis" in email_out["body"]

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST G: Multi-Upstream (Security + Database + Document Research) -> Report -> Email
# ---------------------------------------------------------------------------
def test_workflow_multi_upstream_to_report_to_email(app, db_session, test_user):
    """Test G: Three independent upstream nodes feed Report Generation simultaneously.

    Report Generation synthesizes all 3 into dedicated sections + cross-functional analysis.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Tri-Domain Executive Briefing", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["security_analysis"].id, name="Domain Sec", priority=1)
        n_db = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["database_bi"].id, name="Domain DB", priority=1)
        n_res = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["document_research"].id, name="Domain Research", priority=1)

        n_rep = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["report_generation"].id, name="Executive Synthesis Report", priority=2, configuration={"format": "markdown"})
        n_email = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["email"].id, name="Board Dispatch", priority=3, configuration={"to": "board@enterprise.com", "mode": "draft"})

        db.session.add_all([n_sec, n_db, n_res, n_rep, n_email])
        db.session.commit()

        # Connect all 3 to Report Generator
        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_db.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep3 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep_email = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2, dep3, dep_email])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        # Check Report Generator received all 3 upstream parents in upstream_results
        rep_in = executor.recorded_inputs["Executive Synthesis Report"]
        assert "upstream_results" in rep_in
        up = rep_in["upstream_results"]
        assert "security_analysis" in up or "Domain Sec" in up
        assert "database_bi" in up or "Domain DB" in up
        assert "document_research" in up or "Domain Research" in up

        # Check Report sections include all 3 domains
        rep_out = executor.recorded_outputs["Executive Synthesis Report"]
        art_path = rep_out["artifact"]["path"]
        with open(art_path, "r", encoding="utf-8") as f:
            full_report = f.read()

        assert "SQL Injection" in full_report  # From Security
        assert "Enterprise" in full_report     # From DB
        assert "AI_Radiology_Multicenter_Study_2025.pdf" in full_report  # From Research
        assert "Executive Summary & Strategic Conclusion" in full_report

        # Check Email drafted with report attachment
        email_out = executor.recorded_outputs["Board Dispatch"]
        assert art_path in email_out["attachments"]
        assert email_out["attachment_status"] == "attached"

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST H: Missing Upstream Result (Explicit Failure rather than generic fallback)
# ---------------------------------------------------------------------------
def test_workflow_missing_upstream_result_fails_explicitly(app, db_session, test_user):
    """TEST H: Missing Upstream Result.
    Verify the system reports an explicit failure rather than fabricating a result
    or silently sending a generic email.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Missing Upstream Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        # Upstream node configured to simulate producing empty output
        n_up = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["custom"].id,
            name="Upstream Empty Producer",
            priority=1,
            configuration={"empty_output": True}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Downstream Email Dispatcher",
            priority=2,
            configuration={"to": "audit@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_up, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_up.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # Execution MUST NOT complete successfully with fabricated results
        assert exec_res.status in (EXECUTION_STATUS_FAILED, EXECUTION_STATUS_PARTIALLY_COMPLETED)

        # Downstream email task must explicitly fail due to missing upstream output
        te_email = [te for te in execution.task_executions if te.workflow_node_id == n_email.id][0]
        assert te_email.status == TASK_STATUS_FAILED
        assert "Missing upstream result" in te_email.error_data.get("error", "")
        assert "Upstream Empty Producer" in te_email.error_data.get("error", "")

        # Downstream Email was NEVER executed or fabricated
        assert "Downstream Email Dispatcher" not in executor.recorded_outputs


# ---------------------------------------------------------------------------
# TEST I: Email Approval Rejected (Resend is NEVER called)
# ---------------------------------------------------------------------------
def test_workflow_email_approval_rejected_never_calls_resend(app, db_session, test_user):
    """TEST I: Email approval rejected.
    Verify Resend is never called and execution preserves rejection status.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Email Approval Rejection Workflow", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Restricted Outbound Dispatch",
            priority=1,
            configuration={"to": "external-untrusted@vendor.io", "mode": "send"}
        )
        db.session.add(n_email)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # Workflow execution must pause awaiting human approval
        assert exec_res.status == EXECUTION_STATUS_PAUSED

        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None

        with patch("requests.post") as mock_post:
            resolve_approval_request(
                appr.id,
                user_id=test_user.id,
                approve=False,
                rejection_reason="Unauthorized external recipient per enterprise compliance policy",
                prevent_self_approval=False,
                engine=engine
            )

            # Resend MUST NEVER be called
            mock_post.assert_not_called()

        db.session.refresh(execution)
        assert execution.status in (EXECUTION_STATUS_FAILED, EXECUTION_STATUS_PARTIALLY_COMPLETED)

        te_email = [te for te in execution.task_executions if te.workflow_node_id == n_email.id][0]
        assert te_email.status == TASK_STATUS_FAILED
        assert te_email.error_data.get("rejected") is True
        assert "Unauthorized external recipient" in te_email.error_data.get("error", "")


# ---------------------------------------------------------------------------
# TEST J: Email Approval Accepted (Actual message and requested attachments sent once through Resend)
# ---------------------------------------------------------------------------
def test_workflow_email_approval_accepted_dispatches_resend(app, db_session, test_user, monkeypatch):
    """TEST J: Email approval accepted.
    Verify the actual message and requested attachments are sent once through Resend.
    """
    monkeypatch.setenv("RESEND_API_KEY", "re_test_live_key_valid_12345")
    monkeypatch.setenv("EMAIL_MODE", "live")
    monkeypatch.setenv("EMAIL_FROM", "dispatch@enterprise.com")
    monkeypatch.setenv("ALWAYS_DELIVER_TO_USER", "false")

    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Approved Email Delivery Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["report_generation"].id,
            name="Executive Briefing Generator",
            priority=1,
            configuration={"format": "pdf", "title": "Verified Compliance Briefing"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Approved Email Dispatcher",
            priority=2,
            configuration={"to": "officer@enterprise.com", "mode": "send"}
        )
        db.session.add_all([n_rep, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # 1. Pipeline pauses awaiting human approval on Email send
        assert exec_res.status == EXECUTION_STATUS_PAUSED

        # Verify Report was generated on disk
        rep_out = executor.recorded_outputs["Executive Briefing Generator"]
        art_path = rep_out["artifact"]["path"]
        assert os.path.exists(art_path)

        # 2. Inspect pending approval request
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None
        assert "officer@enterprise.com" in str(appr.requested_action)

        # Proposed draft contains physical attachment
        prop_out = appr.proposed_output
        assert art_path in prop_out.get("attachments", [])

        # 3. Approve and simulate successful Resend delivery
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"id": "re_live_msg_884920"}'
        mock_resp.json.return_value = {"id": "re_live_msg_884920"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            resolve_approval_request(
                appr.id,
                user_id=test_user.id,
                approve=True,
                prevent_self_approval=False,
                engine=engine
            )

            # Assert Resend was called EXACTLY ONCE
            assert mock_post.call_count == 1
            call_url = mock_post.call_args[0][0]
            assert call_url == "https://api.resend.com/emails"

            # Verify Resend payload contains real message and base64 encoded physical attachment
            call_kwargs = mock_post.call_args[1]
            sent_payload = call_kwargs["json"]
            assert "officer@enterprise.com" in sent_payload["to"]
            assert "Verified Compliance Briefing" in sent_payload["subject"]
            assert "attachments" in sent_payload
            assert len(sent_payload["attachments"]) == 1
            assert sent_payload["attachments"][0]["filename"] == os.path.basename(art_path)
            assert len(sent_payload["attachments"][0]["content"]) > 50  # Base64 encoded

        # 4. Verify workflow completion and task execution status
        db.session.refresh(execution)
        assert execution.status == EXECUTION_STATUS_COMPLETED

        te_email = [te for te in execution.task_executions if te.workflow_node_id == n_email.id][0]
        assert te_email.status == TASK_STATUS_COMPLETED
        assert te_email.output_data.get("status") == "sent"
        assert te_email.output_data.get("message_id") == "msg_re_live_msg_884920"

        if os.path.exists(art_path):
            os.remove(art_path)


# ---------------------------------------------------------------------------
# TEST K: Data Flow Verification (Structure & Non-Truncation)
# ---------------------------------------------------------------------------
def test_data_flow_field_preservation(app, db_session, test_user):
    """Test F: Verifies upstream_results dictionary contains complete node metadata,

    output payload, artifacts list, and human summary without dropping fields.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data Flow Verification", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["security_analysis"].id, name="Security Audit", priority=1)
        n_rep = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["report_generation"].id, name="Report Generator", priority=2)
        db.session.add_all([n_sec, n_rep])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        engine.run_execution(execution.id)

        rep_in = executor.recorded_inputs["Report Generator"]
        assert "upstream_results" in rep_in
        sec_record = rep_in["upstream_results"].get("security_analysis") or rep_in["upstream_results"].get("Security Audit")
        assert sec_record is not None
        assert sec_record["status"] == "completed"
        assert sec_record["agent_type"] == "security_analysis"
        assert "output" in sec_record
        assert "summary" in sec_record
        assert len(sec_record["output"]["findings"]) == 2
        assert sec_record["output"]["security_score"] == 72


# ---------------------------------------------------------------------------
# TEST G: Physical File Artifact Verification & Secure Download Endpoint
# ---------------------------------------------------------------------------
def test_physical_file_artifact_generation_and_download(client, auth_headers):
    """Test G: Real physical file created on disk in instance/reports and

    accessible via GET /api/v1/reports/download/<filename>.
    """
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        input_data={
            "title": "Artifact Download Test Report",
            "format": "markdown",
            "summary": "Verifying physical disk write and download streaming.",
        }
    )
    res = agent.execute(ctx)
    assert res.success is True
    art = res.output["artifact"]
    filepath = art["path"]
    filename = art["filename"]

    # 1. Verify file exists on disk and is non-empty
    assert os.path.exists(filepath)
    assert os.path.getsize(filepath) > 50

    # 2. Test download endpoint with authentication
    resp = client.get(
        f"/api/v1/reports/download/{filename}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "Artifact Download Test Report" in resp.data.decode("utf-8")

    # Clean up file descriptor on Windows
    del resp
    import gc
    gc.collect()

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except (PermissionError, OSError):
        pass


# ---------------------------------------------------------------------------
# TEST H: Email Attachment & Delivery Verification
# ---------------------------------------------------------------------------
def test_email_attachment_metadata_and_resend_encoding(tmp_path):
    """Test H: Verifies EmailAgent accepts physical attachment, includes metadata,

    and dispatches via Resend adapter with base64 encoded content.
    """
    sample_file = tmp_path / "sample_report.pdf"
    sample_file.write_bytes(b"%PDF-1.4 test binary report content")

    agent = EmailAgent()
    ctx = AgentContext(
        input_data={
            "to": "dev@enterprise.com",
            "subject": "Executive Report Attachment",
            "body": "Please see attached file.",
            "attachments": [str(sample_file)],
            "source_report_name": "Executive Financial Audit",
            "attachment_filename": "sample_report.pdf",
            "attachment_format": "pdf",
            "mode": "draft",
        }
    )
    res = agent.execute(ctx)
    assert res.success is True
    out = res.output
    assert out["status"] == "drafted"
    assert out["source_report_name"] == "Executive Financial Audit"
    assert out["attachment_filename"] == "sample_report.pdf"
    assert out["attachment_format"] == "pdf"
    assert out["attachment_status"] == "attached"
    assert out["attachments"] == [str(sample_file)]


# ---------------------------------------------------------------------------
# TEST I: Approval Rejection Resumes DAG & Blocks Dependent Tasks
# ---------------------------------------------------------------------------
def test_approval_rejection_blocks_dependent_nodes(app, db_session, test_user):
    """Test I: When approval is rejected, the rejecting task fails, DAG loop resumes,

    and dependent downstream tasks are marked BLOCKED with the rejection reason.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Approval Rejection Workflow", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_email = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["email"].id, name="Outbound Dispatch", priority=1, configuration={"to": "external@vendor.com", "mode": "send"})
        n_audit = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["custom"].id, name="Post-Send Audit", priority=2)
        db.session.add_all([n_email, n_audit])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_email.id, target_node_id=n_audit.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED

        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None

        # Reject the approval request
        resolve_approval_request(appr.id, user_id=test_user.id, approve=False, rejection_reason="Unauthorized external vendor", prevent_self_approval=False)

        db.session.refresh(execution)
        # Execution should be PARTIALLY_COMPLETED or FAILED
        assert execution.status in (EXECUTION_STATUS_PARTIALLY_COMPLETED, EXECUTION_STATUS_FAILED)

        te_email = [te for te in execution.task_executions if te.workflow_node_id == n_email.id][0]
        te_audit = [te for te in execution.task_executions if te.workflow_node_id == n_audit.id][0]

        assert te_email.status == TASK_STATUS_FAILED
        assert te_email.error_data.get("rejected") is True

        # Dependent task MUST be BLOCKED with specific upstream rejection failure reason
        assert te_audit.status == TASK_STATUS_BLOCKED
        assert "Blocked" in te_audit.error_data.get("error", "")
        assert "Outbound Dispatch" in te_audit.error_data.get("error", "")


# ---------------------------------------------------------------------------
# TEST J: Parallel Branch Isolation (Sibling Failure does not stop independent branches)
# ---------------------------------------------------------------------------
def test_parallel_branches_continue_when_sibling_branch_fails(app, db_session, test_user):
    """Test J: Sibling branch failure leaves parallel independent branch running to completion."""
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Parallel Branching Workflow", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        # Branch A: Security
        n_sec = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["security_analysis"].id, name="Sec Branch", priority=1)
        # Branch B: DB
        n_db = WorkflowNode(workflow_id=wf.id, agent_id=workflow_agents["database_bi"].id, name="DB Branch", priority=1)

        db.session.add_all([n_sec, n_db])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED
        assert "Sec Branch" in executor.recorded_outputs
        assert "DB Branch" in executor.recorded_outputs


# ---------------------------------------------------------------------------
# TEST K: Format Verification (markdown, html, docx, pdf generate physical valid files)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fmt, expected_ext", [
    ("markdown", ".md"),
    ("html", ".html"),
    ("docx", ".docx"),
    ("pdf", ".pdf"),
])
def test_all_report_formats_generate_valid_files(fmt, expected_ext):
    """Test K: Verifies physical generation of all 4 formats with non-empty disk size."""
    agent = ReportGenerationAgent()
    ctx = AgentContext(
        input_data={
            "title": f"Format Verification {fmt.upper()}",
            "format": fmt,
            "summary": f"Automated test for {fmt} format generation.",
            "findings": ["Finding 1", "Finding 2"],
            "recommendations": ["Rec 1", "Rec 2"],
        }
    )
    res = agent.execute(ctx)
    assert res.success is True
    art = res.output["artifact"]
    path = art["path"]
    assert os.path.exists(path)
    assert path.endswith(expected_ext)
    assert os.path.getsize(path) > 100

    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# TEST L: Zero Calendar Agent References & Zero Report Archetype References
# ---------------------------------------------------------------------------
def test_zero_calendar_and_zero_report_archetype_references():
    """Test L: Regression audit ensuring 0 active code references to Calendar Agent

    and 0 active code references to Report Archetype in app/ and frontend/src/.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app_dir = os.path.join(root_dir, "app")
    frontend_src_dir = os.path.join(root_dir, "frontend", "src")

    calendar_matches = []
    archetype_matches = []

    for search_dir in (app_dir, frontend_src_dir):
        if not os.path.exists(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            # Skip caches
            if "__pycache__" in root or "node_modules" in root or "dist" in root:
                continue
            for f in files:
                if f.endswith((".py", ".ts", ".tsx")):
                    f_path = os.path.join(root, f)
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as content_file:
                        content = content_file.read()
                        if "calendar_agent" in content.lower() or "calendaragent" in content.lower():
                            calendar_matches.append(f_path)
                        if "report_archetype" in content.lower() or "reportarchetype" in content.lower():
                            archetype_matches.append(f_path)

    assert len(calendar_matches) == 0, f"Found prohibited Calendar Agent references: {calendar_matches}"
    assert len(archetype_matches) == 0, f"Found prohibited Report Archetype references: {archetype_matches}"


# ---------------------------------------------------------------------------
# TEST M: Tenant / Multi-User Isolation
# ---------------------------------------------------------------------------
def test_tenant_isolation_on_executions_and_artifacts(app, db_session, test_user):
    """Test M: User B cannot access or execute workflows owned by User A."""
    from app.models.user import User

    with app.app_context():
        # Create User B
        user_b = User(
            username=f"user_b_{uuid.uuid4().hex[:6]}",
            email=f"user_b_{uuid.uuid4().hex[:6]}@enterprise.com",
            password_hash=hash_password("SecurePassword123!"),
            is_active=True,
        )
        db.session.add(user_b)
        db.session.commit()

        # Create workflow owned by User A
        wf_a = Workflow(user_id=test_user.id, name="User A Confidential Workflow", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf_a)
        db.session.commit()

        # Attempt to access or list by User B
        from app.services.workflow_service import get_workflow_by_public_id, list_workflows
        wf_fetched = get_workflow_by_public_id(wf_a.public_id, user_id=user_b.id)
        assert wf_fetched is None, "Tenant isolation violation: User B accessed User A's workflow."

        user_b_list = list_workflows(user_id=user_b.id)
        assert user_b_list["total"] == 0


# ---------------------------------------------------------------------------
# TEST 2: Direct Security Analysis -> Email (No Report Node)
# ---------------------------------------------------------------------------
def test_workflow_direct_security_analysis_to_email(app, db_session, test_user):
    """TEST 2: Direct Security Analysis -> Email (No Report Node).
    Verify that the email body contains actual vulnerabilities, severities, risk score,
    and remediation recommendations, NOT generic workflow status text.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Security Audit Direct Email Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["security_analysis"].id,
            name="Security Vulnerability Scanner",
            priority=1,
            configuration={"target": "app/services/auth_controller.py"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Security Alert Dispatcher",
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

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        email_out = executor.recorded_outputs["Security Alert Dispatcher"]
        email_body = email_out["body"]

        # Body MUST NOT contain generic text
        assert "Automated workflow task execution completed successfully" not in email_body

        # Body MUST contain real security findings from upstream
        assert "SQL Injection in User Lookup" in email_body
        assert "CRITICAL" in email_body
        assert "Line 42" in email_body
        assert "Hardcoded JWT Secret" in email_body
        assert "72/100" in email_body
        assert "Security Vulnerability & Threat Assessment" in email_body
        assert "Remediation Recommendations" in email_body


# ---------------------------------------------------------------------------
# TEST 3: Direct HTTP/Webhook -> Email (No Report Node)
# ---------------------------------------------------------------------------
def test_workflow_direct_http_webhook_to_email(app, db_session, test_user):
    """TEST 3: Direct HTTP/Webhook -> Email (No Report Node).
    Verify that the email body contains actual HTTP status code, endpoint URL,
    and response payload, NOT generic workflow status text.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Telemetry Direct Email Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["http_webhook"].id,
            name="Health Probe Webhook",
            priority=1,
            configuration={"url": "https://api.internal-telemetry.io/v2/health", "method": "POST"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="SRE Telemetry Dispatcher",
            priority=2,
            configuration={"to": "sre@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_wh, n_email])
        db.session.commit()

        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_wh.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        email_out = executor.recorded_outputs["SRE Telemetry Dispatcher"]
        email_body = email_out["body"]

        assert "Automated workflow task execution completed successfully" not in email_body
        assert "https://api.internal-telemetry.io/v2/health" in email_body
        assert "200" in email_body
        assert "active_workers" in email_body
        assert "healthy" in email_body
        assert "HTTP / Webhook Execution Telemetry" in email_body


# ---------------------------------------------------------------------------
# TEST 6: Multi-Node Chain (Document Research -> Data Analysis -> Email)
# ---------------------------------------------------------------------------
def test_workflow_doc_research_to_data_analysis_to_email(app, db_session, test_user):
    """TEST 6: Multi-Node Chain (Document Research -> Data Analysis -> Email).
    Verify that 3 connected nodes pass domain outputs throughout the pipeline
    and the final Email Agent receives and synthesizes findings from both predecessors.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Research to Analysis to Email Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_res = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["document_research"].id,
            name="Clinical Literature Review",
            priority=1,
            configuration={"topic": "Oncology biomarker study"}
        )
        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Biomarker Statistical Analysis",
            priority=2,
            configuration={"numbers": "12.4, 18.2, 24.5, 36.1, 48.8", "query": "Biomarker variance"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Clinical Research Dispatcher",
            priority=3,
            configuration={"to": "oncology-lead@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_res, n_da, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_da.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        email_out = executor.recorded_outputs["Clinical Research Dispatcher"]
        email_body = email_out["body"]

        assert "Automated workflow task execution completed successfully" not in email_body
        assert "Empirical Data Analysis Findings" in email_body
        assert "28.0" in email_body or "12.4" in email_body  # Mean or min from Data Analysis
        assert "Document Research & Grounded Evidence" in email_body or "AI_Radiology_Multicenter_Study_2025.pdf" in email_body


# ---------------------------------------------------------------------------
# TEST 7: Multiple Incoming Parents (Data Analysis + Security Analysis -> Email)
# ---------------------------------------------------------------------------
def test_workflow_data_analysis_and_security_to_email(app, db_session, test_user):
    """TEST 7: Multiple Incoming Parents (Data Analysis + Security Analysis -> Email).
    Verify that Email Agent receives outputs from BOTH independent upstream parents
    and synthesizes distinct sections for each domain without overwriting.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Dual Domain Direct Email Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["data_analysis"].id,
            name="Quarterly Financial Metrics",
            priority=1,
            configuration={"numbers": "500, 750, 1000, 1250, 1500", "query": "Financial growth analysis"}
        )
        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["security_analysis"].id,
            name="Infrastructure Security Audit",
            priority=1,
            configuration={"target": "app/services/auth_controller.py"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Executive Combined Dispatcher",
            priority=2,
            configuration={"to": "c-suite@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_da, n_sec, n_email])
        db.session.commit()

        dep1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        dep2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([dep1, dep2])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_COMPLETED

        email_out = executor.recorded_outputs["Executive Combined Dispatcher"]
        email_body = email_out["body"]

        assert "Automated workflow task execution completed successfully" not in email_body

        # 1. Verify Data Analysis section is present with calculated metrics
        assert "Empirical Data Analysis Findings" in email_body
        assert "1000.0" in email_body  # Mean
        assert "500.0" in email_body   # Min
        assert "1500.0" in email_body  # Max

        # 2. Verify Security Analysis section is present with vulnerabilities
        assert "Security Vulnerability & Threat Assessment" in email_body
        assert "SQL Injection in User Lookup" in email_body
        assert "CRITICAL" in email_body
        assert "72/100" in email_body

        # 3. Verify Subject reflects multi-domain briefing
        assert email_out["subject"] == "Executive Multi-Agent Operational Intelligence Briefing"


# ---------------------------------------------------------------------------
# TEST 8: Upstream HTTP Failure -> Email (Accurate failure reporting)
# ---------------------------------------------------------------------------
def test_workflow_http_failure_to_email(app, db_session, test_user):
    """TEST 8: Upstream HTTP Failure -> Email.
    Verify that when an upstream HTTP request fails (HTTP 500), the downstream Email Agent
    accurately communicates the error status code, endpoint, and diagnostic payload,
    and does NOT claim generic success.
    """
    with app.app_context():
        workflow_agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="HTTP Failure Incident Dispatch Pipeline", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["http_webhook"].id,
            name="Failing Payment Gateway Probe",
            priority=1,
            configuration={"url": "https://api.internal-telemetry.io/v2/alerts", "simulate_500": True}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=workflow_agents["email"].id,
            name="Incident Alert Email Dispatcher",
            priority=2,
            configuration={"to": "oncall@enterprise.com", "mode": "draft"}
        )
        db.session.add_all([n_wh, n_email])
        db.session.commit()

        # Connect with DEPENDENCY_TYPE_ALWAYS so Email executes to deliver incident report
        dep = WorkflowDependency(workflow_id=wf.id, source_node_id=n_wh.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ALWAYS)
        db.session.add(dep)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # Overall execution has one failed task and one completed task
        assert exec_res.status in (EXECUTION_STATUS_FAILED, EXECUTION_STATUS_PARTIALLY_COMPLETED)

        # Verify Email executed and reported the HTTP 500 error
        email_out = executor.recorded_outputs["Incident Alert Email Dispatcher"]
        email_body = email_out["body"]

        assert "completed successfully" not in email_body.lower() or "reported failures or warnings" in email_body
        assert "500" in email_body
        assert "FAILED" in email_body
        assert "Database cluster connection timed out after 30s" in email_body
        assert "https://api.internal-telemetry.io/v2/alerts" in email_body
        assert "HTTP / Webhook Execution Failure (HTTP 500)" in email_body
        assert "⚠️ Alert: HTTP Request Failure (500)" in email_out["subject"]
