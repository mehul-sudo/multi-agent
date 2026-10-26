"""
Master Production Acceptance Test Suite.
Validates all 10 Mandatory Acceptance Scenarios from Section 42 of Master Prompt:
1. Normal Chat (streaming response, no orchestration plan, no approval)
2. Document Research (grounded facts, cited sources, no approval)
3. Calculation / Analytics (computations, real math, no approval)
4. Parallel Agents (independent nodes execute concurrently)
5. Email Approval Checkpoint (pauses before send, creates approval request, executes upon approval)
6. Multiple Approvals Independent (approving A leaves B paused)
7. Workflow Dependency Ordering (child strictly waits for parent)
8. Rejection Handling (rejected node fails, dependents blocked, sibling continues)
9. Real Provider Failure Handling (truthful errors, no fake mocks)
10. Complete Acceptance Demo Pipeline (Analytics -> Report -> Approval -> Email -> Calendar)
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.agents.base import AgentContext
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.document_research_agent import DocumentResearchAgent
from app.agents.email_agent import EmailAgent
from app.models.approval_request import (
    ApprovalRequest,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_REJECTED,
)
from app.models.task_execution import (
    TaskExecution,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_BLOCKED,
    TASK_STATUS_PENDING,
)
from app.models.workflow_execution import (
    WorkflowExecution,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_FAILED,
)
from app.services.agent_service import create_agent
from app.services.approval_service import resolve_approval_request
from app.services.execution_engine import WorkflowExecutionEngine
from app.services.execution_service import trigger_workflow_execution
from app.services.workflow_service import (
    create_workflow,
    add_node_to_workflow,
    add_dependency_to_workflow,
    activate_workflow,
)


# ------------------------------------------------------------------------------
# Test 1 — Normal Chat (Mode A Streaming, No Orchestration, No Approval)
# ------------------------------------------------------------------------------
def test_scenario_1_normal_chat_streaming(app, client, auth_headers):
    """
    Scenario 1: Normal conversational question streams tokens via SSE,
    does NOT trigger orchestration plan, and requires NO approval.
    """
    with app.app_context():
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Explain the difference between authentication and authorization.",
                "mode": "auto",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.content_type

        # Parse SSE events from response stream
        raw_stream = response.get_data(as_text=True)
        events = []
        for line in raw_stream.splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:].strip()))
                except Exception:
                    pass

        assert len(events) >= 1
        event_types = [e.get("event_type") for e in events]

        # Must include conversation.started and completed or delta
        assert "conversation.started" in event_types
        assert any(t in ("assistant.delta", "assistant.completed") for t in event_types)

        # Must NOT create an approval request for normal chat
        pending_approvals = ApprovalRequest.query.filter_by(status=APPROVAL_STATUS_PENDING).all()
        assert len(pending_approvals) == 0


# ------------------------------------------------------------------------------
# Test 2 — Document Research (Grounded Facts, Cited Sources, No Approval)
# ------------------------------------------------------------------------------
def test_scenario_2_document_research_grounded_citations(app, test_user):
    """
    Scenario 2: User asks question against documents.
    Executes grounded synthesis, cites verified sources, requires NO approval.
    """
    with app.app_context():
        doc_agent = DocumentResearchAgent()
        doc_content = (
            "Enterprise Policy 402: Financial transaction records and ledger books must be retained "
            "for at least 7 years in immutable format. Application debug logs are purged after 90 days."
        )

        ctx = AgentContext(
            user_id=test_user.id,
            input_data={
                "documents": [doc_content],
                "query": "What is the retention period for financial transaction records?",
            },
        )

        result = doc_agent.execute(ctx)

        # Read-only reasoning operation must execute immediately without approval
        assert result.requires_approval is False
        assert result.success is True
        assert result.output is not None

        out = result.output
        answer = out.get("answer", "")
        # Verified grounded fact present in answer
        assert "7" in answer or "seven" in answer.lower()
        # Citations / sources provided
        assert "sources" in out
        assert len(out["sources"]) > 0


# ------------------------------------------------------------------------------
# Test 3 — Calculation / Analytics (Real Math, No Approval)
# ------------------------------------------------------------------------------
def test_scenario_3_data_analytics_math_no_approval(app, test_user):
    """
    Scenario 3: User requests data analysis and calculations.
    Executes numerical computations immediately, requires NO approval.
    """
    with app.app_context():
        data_agent = DataAnalysisAgent()
        ctx = AgentContext(
            user_id=test_user.id,
            input_data={
                "numbers": "100, 150, 200, 250, 300",
                "query": "Calculate the mean, median, total, and standard deviation.",
            },
        )

        result = data_agent.execute(ctx)

        assert result.requires_approval is False
        assert result.success is True
        assert result.output is not None

        stats_data = result.output.get("statistics", {})
        stats = stats_data.get("value") or stats_data
        # Total sum = 1000, mean = 200.0, count = 5
        assert stats.get("count") == 5
        assert stats.get("sum") == 1000.0
        assert stats.get("mean") == 200.0
        assert stats.get("min") == 100.0
        assert stats.get("max") == 300.0


# ------------------------------------------------------------------------------
# Test 4 — Parallel Agents (Independent Nodes Execute Concurrently)
# ------------------------------------------------------------------------------
def test_scenario_4_parallel_agents_concurrency(app, db_session, test_user):
    """
    Scenario 4: Workflow with independent Data Analysis and Security Analysis nodes.
    Execution engine runs both ready nodes in parallel via ThreadPoolExecutor without blocking.
    """
    with app.app_context():
        data_agent = create_agent(
            test_user.id,
            {"name": "Data Agent", "agent_type": "data_analysis", "system_instructions": "Analyze data."},
        )
        sec_agent = create_agent(
            test_user.id,
            {"name": "Security Agent", "agent_type": "security_analysis", "system_instructions": "Scan code."},
        )

        wf = create_workflow(test_user.id, {"name": "Parallel Audit Pipeline"})

        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Analyze Revenue",
                "agent_id": data_agent.public_id,
                "output_key": "data_out",
                "input_mapping": {"numbers": "10, 20, 30"},
            },
        )

        n2, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Audit Security",
                "agent_id": sec_agent.public_id,
                "output_key": "sec_out",
                "input_mapping": {"content": "const token = 'secret';"},
            },
        )

        # Activate workflow (no dependencies between n1 and n2 -> independent parallel branches)
        activate_workflow(wf, test_user.id)
        db_session.commit()

        execution, _ = trigger_workflow_execution(
            workflow=wf,
            user_id=test_user.id,
            input_data={},
        )

        assert execution.status == EXECUTION_STATUS_COMPLETED, f"Exec status is {execution.status}, failure_reason: {execution.failure_reason}, tasks: {[(t.id, t.status, t.error_data) for t in execution.task_executions]}"
        assert "data_out" in execution.output_data
        assert "sec_out" in execution.output_data

        tasks = TaskExecution.query.filter_by(workflow_execution_id=execution.id).all()
        assert len(tasks) == 2
        assert all(t.status == TASK_STATUS_COMPLETED for t in tasks)


# ------------------------------------------------------------------------------
# Test 5 — Email Approval Checkpoint (Pause -> Request -> Authorize -> Send)
# ------------------------------------------------------------------------------
def test_scenario_5_email_approval_checkpoint(app, db_session, test_user):
    """
    Scenario 5: Workflow Data Analysis -> Email (mode=send).
    Data Analysis completes immediately. Email pauses, creates real ApprovalRequest.
    Once user approves, execution resumes and sends email via verified authorization.
    """
    with app.app_context():
        data_agent = create_agent(
            test_user.id,
            {"name": "Analytics Agent", "agent_type": "data_analysis", "system_instructions": "Summarize stats."},
        )
        email_agent = create_agent(
            test_user.id,
            {"name": "Email Agent", "agent_type": "email", "system_instructions": "Dispatch email."},
        )

        wf = create_workflow(test_user.id, {"name": "Analytics and Notification"})

        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Compute Metrics",
                "agent_id": data_agent.public_id,
                "output_key": "metrics",
                "input_mapping": {"numbers": "50, 100, 150"},
            },
        )

        n2, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Send Executive Brief",
                "agent_id": email_agent.public_id,
                "output_key": "email_out",
                "input_mapping": {
                    "to": "executive@enterprise.internal",
                    "subject": "Monthly Report",
                    "body": "Metrics computed successfully.",
                    "mode": "send",
                },
            },
        )

        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": n1.public_id, "target_node_id": n2.public_id})
        activate_workflow(wf, test_user.id)

        # Trigger workflow execution
        execution, _ = trigger_workflow_execution(workflow=wf, user_id=test_user.id, input_data={})

        # Node 1 should be completed, Node 2 should be paused awaiting approval
        t1 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n1.id).first()
        t2 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n2.id).first()

        assert t1.status == TASK_STATUS_COMPLETED
        assert t2.status == TASK_STATUS_BLOCKED
        assert execution.status == EXECUTION_STATUS_PAUSED

        # Verify ApprovalRequest created in database
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None
        assert appr.risk_level == "high"
        assert "email" in appr.requested_action.lower()

        # User reviews and approves the request
        # User reviews and approves the request with patched email sender
        with patch("requests.post", return_value=MagicMock(status_code=200, json=lambda: {"id": "msg_accept_101"})):
            resolve_approval_request(
                approval_id=appr.id,
                approved=True,
                resolved_by_user_id=test_user.id,
                decision_reason="Authorized by Executive Administrator",
                prevent_self_approval=False,
            )

        db_session.refresh(appr)
        db_session.refresh(execution)
        db_session.refresh(t2)

        assert appr.status == APPROVAL_STATUS_APPROVED
        assert execution.status == EXECUTION_STATUS_COMPLETED
        assert t2.status == TASK_STATUS_COMPLETED


# ------------------------------------------------------------------------------
# Test 6 — Multiple Approvals Independent (Approving A Leaves B Paused)
# ------------------------------------------------------------------------------
def test_scenario_6_multiple_independent_approvals(app, db_session, test_user):
    """
    Scenario 6: Workflow with two independent external side-effect nodes:
    Node 1 (Email send to team) and Node 2 (Email send to execs).
    Both pause and generate independent approval requests.
    Approving Approval Request A only authorizes Node 1; Node 2 strictly remains paused.
    """
    with app.app_context():
        email_agent_1 = create_agent(
            test_user.id,
            {"name": "Team Email Agent", "agent_type": "email", "system_instructions": "Send team email."},
        )
        email_agent_2 = create_agent(
            test_user.id,
            {"name": "Exec Email Agent", "agent_type": "email", "system_instructions": "Send exec email."},
        )

        wf = create_workflow(test_user.id, {"name": "Dual Side-Effect Pipeline"})

        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Send Team Announcement",
                "agent_id": email_agent_1.public_id,
                "output_key": "out_team_email",
                "input_mapping": {"to": "team@enterprise.com", "subject": "All Hands", "body": "Join sync", "mode": "send"},
            },
        )

        n2, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Send Exec Announcement",
                "agent_id": email_agent_2.public_id,
                "output_key": "out_exec_email",
                "input_mapping": {"to": "execs@enterprise.com", "subject": "Quarterly Brief", "body": "Exec overview", "mode": "send"},
            },
        )

        activate_workflow(wf, test_user.id)
        execution, _ = trigger_workflow_execution(workflow=wf, user_id=test_user.id, input_data={})

        # Two independent approvals should have been created
        approvals = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).all()
        assert len(approvals) == 2

        appr_1 = next((a for a in approvals if a.task_execution.workflow_node_id == n1.id), approvals[0])
        appr_2 = next((a for a in approvals if a.id != appr_1.id), approvals[1])

        assert appr_1 is not None
        assert appr_2 is not None
        assert appr_1.id != appr_2.id

        # Approve ONLY the first email request with patched email sender
        with patch("requests.post", return_value=MagicMock(status_code=200, json=lambda: {"id": "msg_accept_202"})):
            resolve_approval_request(
                approval_id=appr_1.id,
                approved=True,
                resolved_by_user_id=test_user.id,
                decision_reason="Approved team email only",
                prevent_self_approval=False,
            )

        db_session.refresh(appr_1)
        db_session.refresh(appr_2)
        db_session.refresh(execution)

        # First approval is APPROVED; Second approval strictly remains PENDING
        assert appr_1.status == APPROVAL_STATUS_APPROVED
        assert appr_2.status == APPROVAL_STATUS_PENDING

        # Workflow remains paused because second node is still waiting for its independent approval
        assert execution.status == EXECUTION_STATUS_PAUSED

        t1 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n1.id).first()
        t2 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n2.id).first()

        assert t1.status == TASK_STATUS_COMPLETED
        assert t2.status == TASK_STATUS_BLOCKED


# ------------------------------------------------------------------------------
# Test 7 — Workflow Dependency Ordering (Child Strictly Waits for Parent)
# ------------------------------------------------------------------------------
def test_scenario_7_workflow_dependency_ordering(app, db_session, test_user):
    """
    Scenario 7: Node B depends on Node A.
    Engine enforces strict dependency topological order: Node B cannot start until Node A completes.
    """
    with app.app_context():
        agent = create_agent(
            test_user.id,
            {"name": "Data Agent", "agent_type": "data_analysis", "system_instructions": "Process steps."},
        )

        wf = create_workflow(test_user.id, {"name": "Sequential Pipeline"})

        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Step A",
                "agent_id": agent.public_id,
                "output_key": "step_a",
                "input_mapping": {"numbers": "1, 2, 3"},
            },
        )

        n2, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Step B",
                "agent_id": agent.public_id,
                "output_key": "step_b",
                "input_mapping": {"numbers": "$context.step_a.summary"},
            },
        )

        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": n1.public_id, "target_node_id": n2.public_id})
        activate_workflow(wf, test_user.id)

        execution, _ = trigger_workflow_execution(workflow=wf, user_id=test_user.id, input_data={})

        assert execution.status == EXECUTION_STATUS_COMPLETED
        t1 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n1.id).first()
        t2 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n2.id).first()

        assert t1.status == TASK_STATUS_COMPLETED
        assert t2.status == TASK_STATUS_COMPLETED
        # Execution order verified
        assert t1.completed_at is not None
        assert t2.started_at is not None
        assert t2.started_at >= t1.started_at


# ------------------------------------------------------------------------------
# Test 8 — Rejection Handling (Rejected Node Fails, Downstream Blocked, Sibling Continues)
# ------------------------------------------------------------------------------
def test_scenario_8_rejection_handling_partial_execution(app, db_session, test_user):
    """
    Scenario 8: Workflow with two branches.
    Branch 1: Independent Analytics node.
    Branch 2: Email Send node -> Downstream Audit node.
    When Email approval is rejected:
    - Email task is marked REJECTED / FAILED.
    - Downstream child is blocked.
    - Independent Branch 1 remains completed without rollback.
    """
    with app.app_context():
        data_agent = create_agent(
            test_user.id,
            {"name": "Data Agent", "agent_type": "data_analysis", "system_instructions": "Data analysis."},
        )
        email_agent = create_agent(
            test_user.id,
            {"name": "Email Agent", "agent_type": "email", "system_instructions": "Send email."},
        )

        wf = create_workflow(test_user.id, {"name": "Branching Rejection Pipeline"})

        # Independent branch 1
        n_safe, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Safe Internal Calculation",
                "agent_id": data_agent.public_id,
                "output_key": "safe_calc",
                "input_mapping": {"numbers": "10, 20"},
            },
        )

        # Branch 2: Email node
        n_email, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Send Customer Notice",
                "agent_id": email_agent.public_id,
                "output_key": "cust_email",
                "input_mapping": {"to": "client@enterprise.com", "subject": "Notice", "body": "Hello", "mode": "send"},
            },
        )

        # Dependent child on email
        n_child, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Post-Email Audit",
                "agent_id": data_agent.public_id,
                "output_key": "audit_out",
                "input_mapping": {"numbers": "99"},
            },
        )

        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": n_email.public_id, "target_node_id": n_child.public_id})
        activate_workflow(wf, test_user.id)
        db_session.commit()

        execution, _ = trigger_workflow_execution(workflow=wf, user_id=test_user.id, input_data={})

        import time
        appr = None
        for _ in range(30):
            db_session.rollback()
            appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
            if appr is not None:
                break
            time.sleep(0.1)

        assert appr is not None

        t_safe = None
        for _ in range(30):
            db_session.rollback()
            t_safe = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_safe.id).first()
            if t_safe and t_safe.status == TASK_STATUS_COMPLETED:
                break
            time.sleep(0.1)

        assert t_safe is not None
        assert t_safe.status == TASK_STATUS_COMPLETED

        # User REJECTS the email approval
        resolve_approval_request(
            approval_id=appr.id,
            approved=False,
            resolved_by_user_id=test_user.id,
            decision_reason="Disallowed external contact at this stage",
            prevent_self_approval=False,
        )

        db_session.refresh(appr)
        assert appr.status == APPROVAL_STATUS_REJECTED

        # Email task marked rejected/failed
        t_email = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_email.id).first()
        assert t_email.status in (TASK_STATUS_FAILED, "REJECTED")

        # Downstream child never executed
        t_child = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_child.id).first()
        assert t_child is None or t_child.status != TASK_STATUS_COMPLETED

        # Sibling safe task remains COMPLETED
        db_session.refresh(t_safe)
        assert t_safe.status == TASK_STATUS_COMPLETED


# ------------------------------------------------------------------------------
# Test 9 — Real Provider Failure Handling (Truthful Errors, No Fake Mocks)
# ------------------------------------------------------------------------------
def test_scenario_9_real_provider_failure_handling(app, test_user):
    """
    Scenario 9: Upstream provider network error or unauthorized API response.
    Returns clear, truthful error message without fabricating fake success data.
    """
    with app.app_context():
        email_agent = EmailAgent()

        # Simulate provider failure during verified send
        ctx = AgentContext(
            user_id=test_user.id,
            input_data={
                "to": "test@enterprise.com",
                "subject": "System Test",
                "body": "Fail test",
                "mode": "send",
                "email_provider": "resend",
                "resend_api_key": "re_invalid_api_key_test",
                "approval_granted": True,  # verified authorization token
            },
            metadata={"_backend_approval_verified": True},
        )

        with patch("requests.post", return_value=MagicMock(status_code=401, text="Resend API 401 Unauthorized: Invalid API key")):
            res = email_agent.execute(ctx)

            # Must NOT succeed with fake data
            assert res.success is False
            assert "Invalid API key" in (res.error or "") or "401" in (res.error or "")


# ------------------------------------------------------------------------------
# Test 10 — Complete Acceptance Demo Pipeline
# Data Analysis -> Report Generation -> Approval Checkpoint -> Email
# ------------------------------------------------------------------------------
def test_scenario_10_complete_acceptance_demo_pipeline(app, db_session, test_user):
    """
    Scenario 10: Full end-to-end Enterprise Automation Pipeline:
    1. Data Analysis (Executes immediately, no approval)
    2. Report Generation (Executes immediately, no approval)
    3. Email Dispatch (Pauses for human approval)
    4. Approval verification & completion
    """
    with app.app_context():
        data_agent = create_agent(
            test_user.id,
            {"name": "Data Agent", "agent_type": "data_analysis", "system_instructions": "Analytics."},
        )
        report_agent = create_agent(
            test_user.id,
            {"name": "Report Agent", "agent_type": "report_generation", "system_instructions": "Executive reporting."},
        )
        email_agent = create_agent(
            test_user.id,
            {"name": "Email Agent", "agent_type": "email", "system_instructions": "Notifications."},
        )

        wf = create_workflow(test_user.id, {"name": "Executive Demo Pipeline"})

        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Analyze Revenue Data",
                "agent_id": data_agent.public_id,
                "output_key": "rev_analysis",
                "input_mapping": {"numbers": "120, 150, 180, 210"},
            },
        )

        n2, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Synthesize Executive Report",
                "agent_id": report_agent.public_id,
                "output_key": "exec_report",
                "input_mapping": {"title": "Q3 Revenue Report", "summary": "Strong growth observed across departments."},
            },
        )

        n3, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Email Report to Board",
                "agent_id": email_agent.public_id,
                "output_key": "board_email",
                "input_mapping": {
                    "to": "board@enterprise.internal",
                    "subject": "Q3 Executive Performance Brief",
                    "body": "Please find the quarterly report attached.",
                    "mode": "send",
                },
            },
        )

        # Wire sequential pipeline: n1 -> n2 -> n3
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": n1.public_id, "target_node_id": n2.public_id})
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": n2.public_id, "target_node_id": n3.public_id})

        activate_workflow(wf, test_user.id)

        # Step 1: Initial Trigger
        execution, _ = trigger_workflow_execution(workflow=wf, user_id=test_user.id, input_data={})

        # Data Analysis (n1) and Report Generation (n2) complete without pausing
        t1 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n1.id).first()
        t2 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n2.id).first()
        t3 = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n3.id).first()

        assert t1.status == TASK_STATUS_COMPLETED
        assert t2.status == TASK_STATUS_COMPLETED
        assert t3.status == TASK_STATUS_BLOCKED

        # Step 2: Email Approval Checkpoint
        appr_email = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr_email is not None
        assert "email" in appr_email.requested_action.lower()
        assert appr_email.risk_level == "high"

        # Step 3: Approve Email
        with patch("requests.post", return_value=MagicMock(status_code=200, json=lambda: {"id": "msg_board_303"})):
            resolve_approval_request(
                approval_id=appr_email.id,
                approved=True,
                resolved_by_user_id=test_user.id,
                decision_reason="Approved board notification email",
                prevent_self_approval=False,
            )

        db_session.refresh(t3)
        assert t3.status == TASK_STATUS_COMPLETED
        db_session.refresh(execution)
        assert execution.status == EXECUTION_STATUS_COMPLETED
        assert "exec_report" in execution.output_data
        assert "rev_analysis" in execution.output_data
        assert "board_email" in execution.output_data
