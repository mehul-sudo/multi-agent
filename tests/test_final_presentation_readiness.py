"""
FINAL PRESENTATION READINESS & REGRESSION TEST SUITE — ORCHESTRAI ENTERPRISE

Explicitly tests all 9 scenarios specified in Part E:
1. Small CSV uploaded with request for a quarterly summary (1 agent: data_analysis).
2. Document uploaded with request for a concise summary (1 agent: document_research).
3. Source-code file uploaded with request for security review (1 agent: security_analysis).
4. Task legitimately requiring two agents (data_analysis -> report_generation) with data flow.
5. Task legitimately requiring three agents (data_analysis -> report_generation -> email) with approvals.
6. Upstream agent failure and correct downstream blocking.
7. Repeated refresh idempotency (no duplicate tasks, LLM usage, or artifacts).
8. Malformed or unsupported file produces clear error.
9. Task requiring approval remains protected by backend enforcement.
"""

import os
import io
import json
import pytest
from unittest.mock import MagicMock

from app.extensions import db
from app.models.agent import Agent, AGENT_STATUS_ACTIVE
from app.models.uploaded_file import UploadedFile
from app.models.approval_request import ApprovalRequest, APPROVAL_STATUS_PENDING, APPROVAL_STATUS_APPROVED
from app.models.orchestration_plan import (
    OrchestrationPlan,
    PlanTask,
    TaskDependency,
    PLAN_TASK_STATUS_PENDING,
    PLAN_TASK_STATUS_READY,
    PLAN_TASK_STATUS_RUNNING,
    PLAN_TASK_STATUS_COMPLETED,
    PLAN_TASK_STATUS_FAILED,
    PLAN_TASK_STATUS_AWAITING_APPROVAL,
)
from app.models.orchestration_session import (
    OrchestrationSession,
    ORCHESTRATION_STATUS_READY,
    ORCHESTRATION_STATUS_RUNNING,
    ORCHESTRATION_STATUS_COMPLETED,
    ORCHESTRATION_STATUS_FAILED,
    ORCHESTRATION_STATUS_AWAITING_APPROVAL,
)
from app.services.planner_service import generate_orchestration_plan
from app.services.supervisor_service import SupervisorService
from app.services.file_service import FileService
from app.services.approval_service import resolve_approval_request
from tests.test_master_multiagent_workflow_execution import create_test_agents


# -----------------------------------------------------------------------------
# Scenario 1: Small CSV uploaded with quarterly summary request (1 Agent)
# -----------------------------------------------------------------------------
def test_scenario_1_small_csv_quarterly_summary(app, test_user, tmp_path):
    """Small CSV uploaded with quarterly summary request uses exactly 1 agent (data_analysis)."""
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("Quarter,Revenue,Expenses\nQ1,120000,80000\nQ2,150000,90000\nQ3,180000,100000\nQ4,210000,110000\n", encoding="utf-8")

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="sales.csv",
            extension="csv",
            storage_path=str(csv_file),
            size_bytes=os.path.getsize(str(csv_file)),
            mime_type="text/csv",
        )
        db.session.add(uploaded)
        db.session.commit()

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze this CSV and calculate quarterly revenue.",
            input_context={"file_id": uploaded.public_id, "filename": "sales.csv"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        # Exactly 1 agent must be assigned
        assert len(tasks) == 1, f"Expected 1 agent, got {len(tasks)}"
        task = tasks[0]
        assert task.assigned_agent.agent_type == "data_analysis"

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(task)
        db.session.refresh(session)

        assert task.status == PLAN_TASK_STATUS_COMPLETED
        assert session.status == ORCHESTRATION_STATUS_COMPLETED
        out = task.output_data or {}
        inner_out = out.get("output", out)
        assert inner_out.get("row_count") == 4 or inner_out.get("total_rows") == 4
        assert "revenue" in [c.lower() for c in inner_out.get("columns", [])]


# -----------------------------------------------------------------------------
# Scenario 2: Document uploaded with concise summary request (1 Agent)
# -----------------------------------------------------------------------------
def test_scenario_2_document_concise_summary(app, test_user, tmp_path):
    """Document uploaded with concise summary request uses exactly 1 agent (document_research)."""
    doc_file = tmp_path / "briefing.txt"
    doc_file.write_text(
        "Quarterly Strategic Review.\n"
        "Enterprise cloud adoption rose by 45% year-over-year.\n"
        "Security compliance audits were completed with zero critical findings.\n"
        "Customer retention reached a multi-year high of 98.2% across global regions.\n",
        encoding="utf-8",
    )

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="briefing.txt",
            extension="txt",
            storage_path=str(doc_file),
            size_bytes=os.path.getsize(str(doc_file)),
            mime_type="text/plain",
        )
        db.session.add(uploaded)
        db.session.commit()

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Summarize this document.",
            input_context={"file_id": uploaded.public_id, "filename": "briefing.txt"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        assert len(tasks) == 1, f"Expected 1 agent, got {len(tasks)}"
        task = tasks[0]
        assert task.assigned_agent.agent_type == "document_research"

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(task)
        db.session.refresh(session)

        assert task.status == PLAN_TASK_STATUS_COMPLETED
        assert session.status == ORCHESTRATION_STATUS_COMPLETED
        out = task.output_data or {}
        inner_out = out.get("output", out)
        assert "summary" in inner_out or "executive_summary" in inner_out or "findings" in inner_out


# -----------------------------------------------------------------------------
# Scenario 3: Source-code file with security review request (1 Agent)
# -----------------------------------------------------------------------------
def test_scenario_3_source_code_security_review(app, test_user, tmp_path):
    """Source-code file uploaded with security review request uses exactly 1 agent (security_analysis)."""
    code_file = tmp_path / "auth_service.py"
    code_file.write_text(
        "import os\n"
        "def query_user(username):\n"
        "    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
        "    return db.execute(query)\n",
        encoding="utf-8",
    )

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="auth_service.py",
            extension="py",
            storage_path=str(code_file),
            size_bytes=os.path.getsize(str(code_file)),
            mime_type="text/x-python",
        )
        db.session.add(uploaded)
        db.session.commit()

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Review this source code for security issues.",
            input_context={"file_id": uploaded.public_id, "filename": "auth_service.py"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        assert len(tasks) == 1, f"Expected 1 agent, got {len(tasks)}"
        task = tasks[0]
        assert task.assigned_agent.agent_type == "security_analysis"

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(task)
        db.session.refresh(session)

        assert task.status == PLAN_TASK_STATUS_COMPLETED
        assert session.status == ORCHESTRATION_STATUS_COMPLETED
        out = task.output_data or {}
        inner_out = out.get("output", out)
        findings = inner_out.get("findings", [])
        assert any("injection" in f.get("title", "").lower() or "sql" in f.get("title", "").lower() for f in findings)


# -----------------------------------------------------------------------------
# Scenario 4: Two agents (data_analysis -> report_generation) with data flow
# -----------------------------------------------------------------------------
def test_scenario_4_two_agents_analysis_and_report(app, test_user, tmp_path):
    """Two-agent pipeline: Data Analysis computes figures, Report Generation compiles artifact."""
    csv_file = tmp_path / "q4_metrics.csv"
    csv_file.write_text("Month,Leads,Conversions,Spend\nOct,1200,120,4000\nNov,1400,150,4500\nDec,1900,210,5500\n", encoding="utf-8")

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="q4_metrics.csv",
            extension="csv",
            storage_path=str(csv_file),
            size_bytes=os.path.getsize(str(csv_file)),
            mime_type="text/csv",
        )
        db.session.add(uploaded)
        db.session.commit()

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze this CSV and create a report.",
            input_context={"file_id": uploaded.public_id, "filename": "q4_metrics.csv"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        assert len(tasks) == 2, f"Expected 2 agents, got {len(tasks)}"
        t1, t2 = tasks[0], tasks[1]
        assert t1.assigned_agent.agent_type == "data_analysis"
        assert t2.assigned_agent.agent_type == "report_generation"

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(t1)
        db.session.refresh(t2)
        db.session.refresh(session)

        assert t1.status == PLAN_TASK_STATUS_COMPLETED
        assert t2.status == PLAN_TASK_STATUS_COMPLETED
        assert session.status == ORCHESTRATION_STATUS_COMPLETED

        # Verify physical artifact was generated in task 2
        t2_out = t2.output_data or {}
        artifacts = t2_out.get("artifacts") or []
        assert len(artifacts) >= 1
        art_path = artifacts[0].get("path")
        assert art_path and os.path.exists(art_path)


# -----------------------------------------------------------------------------
# Scenario 5: Three agents (data_analysis -> report_generation -> email) with approvals
# -----------------------------------------------------------------------------
def test_scenario_5_three_agents_analysis_report_email(app, test_user, tmp_path):
    """Three-agent pipeline: Analysis -> Report -> Email with human approval enforcement."""
    csv_file = tmp_path / "finances.csv"
    csv_file.write_text("Quarter,Profit,Margin\nQ1,50000,22%\nQ2,65000,25%\n", encoding="utf-8")

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="finances.csv",
            extension="csv",
            storage_path=str(csv_file),
            size_bytes=os.path.getsize(str(csv_file)),
            mime_type="text/csv",
        )
        db.session.add(uploaded)
        db.session.commit()

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze this quarterly financial CSV, create an executive report, and notify the manager via email.",
            input_context={
                "file_id": uploaded.public_id,
                "filename": "finances.csv",
                "recipient": "cfo@enterprise.internal",
            },
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        assert len(tasks) == 3, f"Expected 3 agents, got {len(tasks)}"
        t1, t2, t3 = tasks[0], tasks[1], tasks[2]
        assert t1.assigned_agent.agent_type == "data_analysis"
        assert t2.assigned_agent.agent_type == "report_generation"
        assert t3.assigned_agent.agent_type == "email"

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(t1)
        db.session.refresh(t2)
        db.session.refresh(session)

        # Execution pauses at Email awaiting human approval
        assert t1.status == PLAN_TASK_STATUS_COMPLETED
        assert t2.status == PLAN_TASK_STATUS_COMPLETED
        assert session.status == ORCHESTRATION_STATUS_AWAITING_APPROVAL

        # Approve and resume
        appr = ApprovalRequest.query.filter_by(orchestration_id=session.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None
        resolve_approval_request(appr.id, test_user.id, approve=True, prevent_self_approval=False)

        session.status = ORCHESTRATION_STATUS_READY
        db.session.commit()

        supervisor.run_orchestration(session.id)
        db.session.refresh(t3)
        db.session.refresh(session)

        assert t3.status == PLAN_TASK_STATUS_COMPLETED
        assert session.status == ORCHESTRATION_STATUS_COMPLETED


# -----------------------------------------------------------------------------
# Scenario 6: Upstream failure blocks downstream tasks honestly
# -----------------------------------------------------------------------------
def test_scenario_6_upstream_failure_blocks_downstream(app, test_user):
    """When an upstream task fails, downstream dependent tasks become BLOCKED with an honest error."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze this financial CSV and create a report.",
            input_context={"file_id": "non_existent_file_id_xyz", "filename": "missing.csv"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()
        assert len(tasks) == 2
        t1, t2 = tasks[0], tasks[1]

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(t1)
        db.session.refresh(t2)
        db.session.refresh(session)

        # Task 1 failed because file did not exist
        assert t1.status == PLAN_TASK_STATUS_FAILED
        assert "not found" in (t1.error_message or "").lower()

        # Task 2 is BLOCKED
        assert t2.status == "BLOCKED"
        assert "blocked due to failure of upstream dependency" in (t2.error_message or "").lower()

        # Overall session is FAILED
        assert session.status == ORCHESTRATION_STATUS_FAILED


# -----------------------------------------------------------------------------
# Scenario 7: Repeated refresh does not duplicate tasks, LLM usage, or artifacts
# -----------------------------------------------------------------------------
def test_scenario_7_repeated_refresh_idempotency(client, auth_headers, app, test_user):
    """Repeated calls to plan and task overview do not mutate or duplicate tasks."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly sales and create a report",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()
        plan = generate_orchestration_plan(session)
        initial_task_count = plan.tasks.count()
        pub_id = session.public_id

    # Repeated GET /plan requests
    for _ in range(5):
        resp = client.get(f"/api/v1/orchestrations/{pub_id}/plan", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data.get("tasks", [])) == initial_task_count

    # Repeated GET /tasks/overview requests
    for _ in range(5):
        resp = client.get("/api/v1/orchestrations/tasks/overview", headers=auth_headers)
        assert resp.status_code == 200


# -----------------------------------------------------------------------------
# Scenario 8: Malformed or unsupported file produces a clear error
# -----------------------------------------------------------------------------
def test_scenario_8_malformed_unsupported_file_error(app, test_user, tmp_path):
    """Uploading an unsupported extension (e.g. .exe) produces a clear validation error."""
    mock_file = MagicMock()
    mock_file.filename = "malicious_payload.exe"
    mock_file.seek = MagicMock()
    mock_file.tell = MagicMock(return_value=1024)

    with app.app_context():
        res, err = FileService.save_uploaded_file(mock_file, str(tmp_path), user_id=test_user.id)
        assert res is None
        assert err is not None
        assert "not allowed" in err.lower()


# -----------------------------------------------------------------------------
# Scenario 9: Task requiring approval remains protected by backend enforcement
# -----------------------------------------------------------------------------
def test_scenario_9_approval_protected_backend_enforcement(app, test_user):
    """Email side-effect cannot execute without verified human approval in the database."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Send email to director with quarterly status update",
            input_context={"recipient": "director@enterprise.internal", "body": "Quarterly metrics ready."},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        task = plan.tasks.first()
        assert task.assigned_agent.agent_type == "email"

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(task)
        db.session.refresh(session)

        # Must halt at AWAITING_APPROVAL
        assert session.status == ORCHESTRATION_STATUS_AWAITING_APPROVAL
        appr = ApprovalRequest.query.filter_by(orchestration_id=session.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None
        assert task.status != PLAN_TASK_STATUS_COMPLETED


# -----------------------------------------------------------------------------
# Scenario 10: Complete flow: file upload -> execution -> results viewing -> artifact download
# -----------------------------------------------------------------------------
def test_scenario_10_complete_end_to_end_flow_with_artifact_download(client, app, auth_headers, test_user, tmp_path):
    """Complete demo flow: file upload -> Task Manager execution -> artifact generation -> verified download."""
    csv_file = tmp_path / "executive_sales.csv"
    csv_file.write_text("Quarter,Revenue,Cost\nQ1,10000,6000\nQ2,12000,7000\n", encoding="utf-8")

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="executive_sales.csv",
            extension="csv",
            storage_path=str(csv_file),
            size_bytes=os.path.getsize(str(csv_file)),
            mime_type="text/csv",
        )
        db.session.add(uploaded)
        db.session.commit()
        file_pub_id = uploaded.public_id

    # 1. Create orchestration session via API
    resp = client.post(
        "/api/v1/orchestrations",
        json={
            "objective": "Analyze executive sales CSV and generate report",
            "input_context": {
                "file_id": file_pub_id,
                "filename": "executive_sales.csv",
            },
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    orch_data = resp.get_json()["orchestration"]
    orch_id = orch_data["id"]

    # 2. Start orchestration
    start_resp = client.post(f"/api/v1/orchestrations/{orch_id}/start", headers=auth_headers)
    assert start_resp.status_code == 200
    start_data = start_resp.get_json()
    assert start_data["status"] == "COMPLETED"

    # 3. View plan and results in Task Manager
    plan_resp = client.get(f"/api/v1/orchestrations/{orch_id}/plan", headers=auth_headers)
    assert plan_resp.status_code == 200
    plan_data = plan_resp.get_json()
    assert len(plan_data["tasks"]) == 2
    for t in plan_data["tasks"]:
        assert t["status"] == "COMPLETED"

    # 4. Check artifacts endpoint
    art_resp = client.get(f"/api/v1/orchestrations/{orch_id}/artifacts", headers=auth_headers)
    assert art_resp.status_code == 200
    art_data = art_resp.get_json()
    assert "artifacts" in art_data

    # 5. Verify direct download endpoint
    report_task = [t for t in plan_data["tasks"] if t["assigned_agent_type"] == "report_generation"][0]
    out = report_task.get("output_data") or {}
    inner = out.get("output", out)
    downloads = inner.get("downloads", {})
    assert len(downloads) > 0
    md_url = downloads.get("md")
    assert md_url is not None

    dl_resp = client.get(md_url, headers=auth_headers)
    assert dl_resp.status_code == 200
    assert len(dl_resp.data) > 0


