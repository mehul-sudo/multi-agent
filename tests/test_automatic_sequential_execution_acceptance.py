"""
Acceptance Test Suite: Automatic Sequential Workflow Execution & Gemini Configuration.

Covers:
1. Core Acceptance: Data Analysis -> Report Generation -> Email
   - Single trigger executes connected nodes automatically per dependency DAG.
   - Empirical statistical findings flow into Report Generation.
   - Physical report deliverable generated on disk.
   - Real report artifact and summary flow into Email Agent.
   - Email pauses execution for human approval (WAITING_FOR_APPROVAL status).
   - Approval resolution automatically resumes workflow without re-execution.
   - Resend dispatch occurs only after approval.
   - All node outputs and final statuses persisted.
2. Four-Node Pipeline: Security Analysis + Database/BI -> Report Generation -> Email
   - Multi-dependency resolution and consolidated multi-domain reporting.
3. Dependency Failure Blocking: Upstream failure blocks downstream nodes with real error (BLOCKED status).
4. Real-time Node Status Resolution: QUEUED, RUNNING, COMPLETED, WAITING_FOR_APPROVAL, FAILED, BLOCKED.
5. Gemini Configuration Audit: Existing GEMINI_API_KEY reuse, active models, exception sanitization.
"""

import os
import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.models.task_execution import (
    TASK_STATUS_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TaskExecution,
)
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import DEPENDENCY_TYPE_ON_SUCCESS, WorkflowDependency
from app.models.workflow_execution import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_QUEUED,
    WorkflowExecution,
)
from app.models.workflow_node import WorkflowNode
from app.agents import get_agent_instance, AgentContext
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.report_generation_agent import ReportGenerationAgent
from app.agents.email_agent import EmailAgent
from app.services.execution_engine import (
    AgentExecutor,
    ExecutionResult,
    WorkflowExecutionEngine,
)
from app.services.approval_service import resolve_approval_request
from app.api.executions import _serialize_task_execution
from app.llm.contracts import LLMRequest, LLMMessage
from app.llm.providers.gemini_adapter import GeminiProviderAdapter


def _create_agents(user_id):
    """Helper to provision agents with standard domain types."""
    agent_specs = [
        ("Data Analysis Agent", "data_analysis"),
        ("Report Generation Agent", "report_generation"),
        ("Email Agent", "email"),
        ("Security Analysis Agent", "security_analysis"),
        ("Database BI Agent", "database_bi"),
        ("HTTP Webhook Agent", "http_webhook"),
    ]
    agents = {}
    for name, ag_type in agent_specs:
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


# ---------------------------------------------------------------------------
# ACCEPTANCE TEST 1: Data Analysis -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_acceptance_data_analysis_to_report_to_email_end_to_end(app, db_session, test_user):
    """Verify full end-to-end flow:
    1. Click Execute Workflow once.
    2. Data Analysis processes actual dataset and persists empirical metrics.
    3. Report Generation starts automatically after Data Analysis succeeds.
    4. Report Generation receives actual Data Analysis output and persists PDF artifact.
    5. Email starts automatically after Report Generation succeeds.
    6. Email receives real report content and attachment reference.
    7. Email pauses workflow with WAITING_FOR_APPROVAL status.
    8. Approving resumes workflow automatically and dispatches email with attachment.
    9. Final status and actual output of every node are persisted.
    """
    with app.app_context():
        agents = _create_agents(test_user.id)

        wf = Workflow(
            user_id=test_user.id,
            name="Quarterly Revenue Audit & Executive Delivery Pipeline",
            status=WORKFLOW_STATUS_ACTIVE,
        )
        db.session.add(wf)
        db.session.commit()

        # Node 1: Real Data Analysis
        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["data_analysis"].id,
            name="Revenue Metrics Analysis",
            priority=1,
            configuration={
                "numbers": "12000, 24000, 18500, 31000, 45000, 29000",
                "query": "Quarterly Revenue Variance",
            },
        )
        # Node 2: Real Report Generation
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Revenue Executive Report Generator",
            priority=2,
            configuration={
                "format": "pdf",
                "title": "Quarterly Revenue Financial Performance Report",
            },
        )
        # Node 3: Real Email Agent (mode=send requires human approval)
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Executive Briefing Dispatcher",
            priority=3,
            configuration={
                "to": "cfo@enterprise.com",
                "mode": "send",
            },
        )
        db.session.add_all([n_da, n_rep, n_email])
        db.session.commit()

        # Wire DAG: Data Analysis -> Report Generation -> Email
        dep1 = WorkflowDependency(
            workflow_id=wf.id,
            source_node_id=n_da.id,
            target_node_id=n_rep.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        dep2 = WorkflowDependency(
            workflow_id=wf.id,
            source_node_id=n_rep.id,
            target_node_id=n_email.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        db.session.add_all([dep1, dep2])
        db.session.commit()

        # Create execution in QUEUED state
        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=test_user.id,
            status=EXECUTION_STATUS_QUEUED,
            input_data={},
        )
        db.session.add(execution)
        db.session.commit()

        # Spy on requests.post to ensure Resend is NOT called before approval
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "re_live_acceptance_msg_001"}
        mock_resp.text = '{"id": "re_live_acceptance_msg_001"}'

        with patch("requests.post", return_value=mock_resp) as mock_post:
            # STEP 1: Execute Workflow once via engine
            engine = WorkflowExecutionEngine()
            exec_res = engine.run_execution(execution.id)

            # STEP 2: Verify execution paused at Email node awaiting human approval
            assert exec_res.status == EXECUTION_STATUS_PAUSED
            assert mock_post.call_count == 0  # Zero emails sent before approval!

            # STEP 3: Verify Data Analysis executed and computed real empirical statistics
            te_da = TaskExecution.query.filter_by(
                workflow_execution_id=execution.id, workflow_node_id=n_da.id
            ).first()
            assert te_da.status == TASK_STATUS_COMPLETED
            da_stats = te_da.output_data.get("statistics", {})
            assert "value" in da_stats
            assert da_stats["value"]["min"] == 12000.0
            assert da_stats["value"]["max"] == 45000.0
            assert da_stats["value"]["sum"] == 159500.0
            assert da_stats["value"]["mean"] == pytest.approx(26583.33, rel=1e-2)

            # Serialized status check for Data Analysis node
            ser_da = _serialize_task_execution(te_da)
            assert ser_da["status"] == "COMPLETED"

            # STEP 4: Verify Report Generation ran automatically and produced physical PDF artifact
            te_rep = TaskExecution.query.filter_by(
                workflow_execution_id=execution.id, workflow_node_id=n_rep.id
            ).first()
            assert te_rep.status == TASK_STATUS_COMPLETED
            rep_art = te_rep.output_data.get("artifact", {})
            assert rep_art.get("path") is not None
            pdf_path = rep_art["path"]
            assert os.path.exists(pdf_path)
            assert pdf_path.endswith(".pdf")
            assert os.path.getsize(pdf_path) > 1000  # Real binary PDF

            # Serialized status check for Report Generation node
            ser_rep = _serialize_task_execution(te_rep)
            assert ser_rep["status"] == "COMPLETED"

            # STEP 5: Verify Email node received the real PDF artifact and executive summary
            te_email = TaskExecution.query.filter_by(
                workflow_execution_id=execution.id, workflow_node_id=n_email.id
            ).first()
            assert te_email.status == TASK_STATUS_BLOCKED  # Blocked in DB pending approval
            assert pdf_path in te_email.output_data.get("attachments", [])
            assert te_email.output_data.get("status") == "awaiting_approval"
            assert te_email.output_data.get("attachment_filename", "").endswith(".pdf")

            # Verify truthful real-time status serialization: WAITING_FOR_APPROVAL
            ser_email = _serialize_task_execution(te_email)
            assert ser_email["status"] == "WAITING_FOR_APPROVAL"

            # STEP 6: Verify pending ApprovalRequest exists
            appr = ApprovalRequest.query.filter_by(
                workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING
            ).first()
            assert appr is not None
            assert appr.task_execution_id == te_email.id
            assert "cfo@enterprise.com" in appr.requested_action

            # STEP 7: Human approves the request -> Execution resumes automatically
            resolve_approval_request(
                approval_id=appr.id,
                user_id=test_user.id,
                approve=True,
                prevent_self_approval=False,
                engine=engine,
            )

            # STEP 8: Verify workflow completed automatically after approval
            db.session.refresh(execution)
            assert execution.status == EXECUTION_STATUS_COMPLETED

            # STEP 9: Verify Email node completed and Resend was dispatched with attachment
            db.session.refresh(te_email)
            assert te_email.status == TASK_STATUS_COMPLETED
            ser_email_after = _serialize_task_execution(te_email)
            assert ser_email_after["status"] == "COMPLETED"

            assert mock_post.call_count == 1
            call_kwargs = mock_post.call_args[1]["json"]
            assert "attachments" in call_kwargs
            assert len(call_kwargs["attachments"]) == 1
            assert call_kwargs["attachments"][0]["filename"].endswith(".pdf")
            assert len(call_kwargs["attachments"][0]["content"]) > 0  # Real base64 payload

            # Clean up generated test deliverable
            if os.path.exists(pdf_path):
                os.remove(pdf_path)


# ---------------------------------------------------------------------------
# ACCEPTANCE TEST 2: Multi-Domain 4-Node Pipeline:
# Security + Database/BI -> Report Generation -> Email
# ---------------------------------------------------------------------------
def test_acceptance_four_node_multi_domain_pipeline(app, db_session, test_user):
    """Verify four-node pipeline:
    Node 1: Security Analysis
    Node 2: Database & BI
    Node 3: Report Generation (waits for both Node 1 & 2)
    Node 4: Email Agent (waits for Node 3, delivers consolidated report)
    """
    with app.app_context():
        agents = _create_agents(test_user.id)

        wf = Workflow(
            user_id=test_user.id,
            name="Enterprise Operational & Security Audit Pipeline",
            status=WORKFLOW_STATUS_ACTIVE,
        )
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Infrastructure Vulnerability Scan",
            priority=1,
            configuration={
                "code": "def login(user, pw):\n    query = 'SELECT * FROM users WHERE user=' + user\n    return db.execute(query)",
                "target": "api-gateway-service.py",
            },
        )
        n_db = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["database_bi"].id,
            name="Database Query Telemetry",
            priority=1,
            configuration={"query": "SELECT count(*) as total_users FROM users"},
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Unified Audit Dossier",
            priority=2,
            configuration={"format": "markdown", "title": "Quarterly Operations & Security Assessment"},
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Security Board Dispatcher",
            priority=3,
            configuration={"to": "security-board@enterprise.com", "mode": "send"},
        )
        db.session.add_all([n_sec, n_db, n_rep, n_email])
        db.session.commit()

        # Dependencies: Sec -> Rep, DB -> Rep, Rep -> Email
        d1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        d2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_db.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        d3 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([d1, d2, d3])
        db.session.commit()

        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=test_user.id,
            status=EXECUTION_STATUS_QUEUED,
            input_data={},
        )
        db.session.add(execution)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "re_live_multi_node_002"}
        mock_resp.text = '{"id": "re_live_multi_node_002"}'

        with patch("requests.post", return_value=mock_resp) as mock_post:
            engine = WorkflowExecutionEngine()
            exec_res = engine.run_execution(execution.id)

            # Paused awaiting board approval for email dispatch
            assert exec_res.status == EXECUTION_STATUS_PAUSED

            # Verify Node 1 & Node 2 both completed
            te_sec = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_sec.id).first()
            te_db = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_db.id).first()
            assert te_sec.status == TASK_STATUS_COMPLETED
            assert te_db.status == TASK_STATUS_COMPLETED

            # Verify Node 3 created consolidated markdown report
            te_rep = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_rep.id).first()
            assert te_rep.status == TASK_STATUS_COMPLETED
            md_path = te_rep.output_data["artifact"]["path"]
            assert os.path.exists(md_path)
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Operations & Security" in content

            # Verify Node 4 email is WAITING_FOR_APPROVAL
            te_email = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_email.id).first()
            ser_email = _serialize_task_execution(te_email)
            assert ser_email["status"] == "WAITING_FOR_APPROVAL"

            # Approve email
            appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
            assert appr is not None
            resolve_approval_request(appr.id, user_id=test_user.id, approve=True, prevent_self_approval=False, engine=engine)

            # Verify full completion and email sent
            db.session.refresh(execution)
            assert execution.status == EXECUTION_STATUS_COMPLETED
            assert mock_post.call_count == 1

            if os.path.exists(md_path):
                os.remove(md_path)


# ---------------------------------------------------------------------------
# ACCEPTANCE TEST 3: Dependency Rules - Upstream Failure Blocks Downstream Nodes
# ---------------------------------------------------------------------------
def test_acceptance_upstream_failure_blocks_dependent_nodes_with_real_error(app, db_session, test_user):
    """Verify that when an upstream node fails:
    - Downstream dependent nodes are BLOCKED.
    - Serialized status shows BLOCKED.
    - Real error message is recorded.
    """
    with app.app_context():
        agents = _create_agents(test_user.id)

        wf = Workflow(
            user_id=test_user.id,
            name="Failing Webhook Dependency Pipeline",
            status=WORKFLOW_STATUS_ACTIVE,
        )
        db.session.add(wf)
        db.session.commit()

        # Node 1: Webhook pointing to an unauthorized/failing domain
        n_hook = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["http_webhook"].id,
            name="External Webhook Push",
            priority=1,
            configuration={"url": "http://192.168.1.1/blocked-internal", "method": "POST"},
        )
        # Node 2: Report Generator depends on Node 1
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Webhook Telemetry Report",
            priority=2,
            configuration={"format": "markdown"},
        )
        # Node 3: Email depends on Node 2
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Telemetry Alert Email",
            priority=3,
            configuration={"to": "devops@enterprise.com", "mode": "send"},
        )
        db.session.add_all([n_hook, n_rep, n_email])
        db.session.commit()

        d1 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_hook.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        d2 = WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS)
        db.session.add_all([d1, d2])
        db.session.commit()

        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=test_user.id,
            status=EXECUTION_STATUS_QUEUED,
            input_data={},
        )
        db.session.add(execution)
        db.session.commit()

        engine = WorkflowExecutionEngine()
        exec_res = engine.run_execution(execution.id)

        # Webhook failed due to SSRF security guardrails
        te_hook = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_hook.id).first()
        assert te_hook.status == TASK_STATUS_FAILED
        ser_hook = _serialize_task_execution(te_hook)
        assert ser_hook["status"] == "FAILED"

        # Downstream nodes are BLOCKED
        te_rep = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_rep.id).first()
        te_email = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_email.id).first()

        assert te_rep.status == TASK_STATUS_BLOCKED
        assert te_email.status == TASK_STATUS_BLOCKED

        ser_rep = _serialize_task_execution(te_rep)
        ser_email = _serialize_task_execution(te_email)

        assert ser_rep["status"] == "BLOCKED"
        assert ser_email["status"] == "BLOCKED"
        assert "Blocked:" in te_rep.error_data.get("error", "")
        assert "External Webhook Push" in te_rep.error_data.get("error", "")


# ---------------------------------------------------------------------------
# ACCEPTANCE TEST 4: Real-time Status Serialization Verification
# ---------------------------------------------------------------------------
def test_acceptance_realtime_node_status_serialization(app, db_session, test_user):
    """Verify that all required statuses are truthfully mapped in _serialize_task_execution:
    - QUEUED (from pending)
    - RUNNING (from running)
    - COMPLETED (from completed)
    - WAITING_FOR_APPROVAL (from blocked with pending ApprovalRequest)
    - BLOCKED (from blocked without pending ApprovalRequest)
    - FAILED (from failed)
    """
    with app.app_context():
        agents = _create_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Status Test WF", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        node = WorkflowNode(workflow_id=wf.id, agent_id=agents["email"].id, name="Test Node")
        db.session.add(node)
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        te = TaskExecution(
            workflow_execution_id=execution.id,
            workflow_node_id=node.id,
            agent_id=agents["email"].id,
            status=TASK_STATUS_PENDING,
        )
        db.session.add(te)
        db.session.commit()

        # 1. PENDING -> QUEUED
        assert _serialize_task_execution(te)["status"] == "QUEUED"

        # 2. RUNNING -> RUNNING
        te.status = "running"
        db.session.commit()
        assert _serialize_task_execution(te)["status"] == "RUNNING"

        # 3. COMPLETED -> COMPLETED
        te.status = "completed"
        db.session.commit()
        assert _serialize_task_execution(te)["status"] == "COMPLETED"

        # 4. FAILED -> FAILED
        te.status = "failed"
        db.session.commit()
        assert _serialize_task_execution(te)["status"] == "FAILED"

        # 5. BLOCKED (without pending approval) -> BLOCKED
        te.status = "blocked"
        db.session.commit()
        assert _serialize_task_execution(te)["status"] == "BLOCKED"

        # 6. BLOCKED (with pending approval) -> WAITING_FOR_APPROVAL
        appr = ApprovalRequest(
            workflow_execution_id=execution.id,
            task_execution_id=te.id,
            status=APPROVAL_STATUS_PENDING,
            requested_action="Send email",
            risk_level="high",
            explanation="Requires human check",
        )
        db.session.add(appr)
        db.session.commit()
        assert _serialize_task_execution(te)["status"] == "WAITING_FOR_APPROVAL"


# ---------------------------------------------------------------------------
# ACCEPTANCE TEST 5: Gemini Model Configuration & Secret Sanitization
# ---------------------------------------------------------------------------
def test_acceptance_gemini_configuration_and_secret_sanitization(app):
    """Verify Gemini provider configuration:
    - Reuses existing GEMINI_API_KEY.
    - Validates configuration at startup.
    - Sanitizes exceptions so secrets are never exposed.
    """
    with app.app_context():
        adapter = GeminiProviderAdapter()
        assert adapter.provider_name == "gemini"
        assert adapter.validate_config() is True  # Reuses existing GEMINI_API_KEY

        # Supported models include verified active models
        assert "gemini-flash-lite-latest" in adapter.supported_models
        assert "gemini-3.5-flash" in adapter.supported_models

        # Verify secret sanitization in exceptions
        test_msg_with_secret = (
            "API error at https://generativelanguage.googleapis.com/v1beta/models/gemini:generateContent"
            "?key=AQ.Ab8RN6IbEOJIXDGMwCte7jBnFrNRgBn4yNyQrgQxJ-i9dFiKHw: 400 Bad Request"
        )
        sanitized = adapter._sanitize_error_message(test_msg_with_secret)
        assert "AQ.Ab8RN6IbEOJIXDGMwCte7jBnFrNRgBn4yNyQrgQxJ-i9dFiKHw" not in sanitized
        assert "key=[REDACTED]" in sanitized
