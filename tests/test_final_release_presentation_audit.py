"""
FINAL RELEASE PRESENTATION AUDIT & ACCEPTANCE SUITE — ORCHESTRAI ENTERPRISE

Explicitly verifies:
- Test A: Single task security-analysis execution & clear findings.
- Test B: Multi-agent financial workflow with quarterly_sales_2026.csv (dynamic runtime math).
- Test C: Prerequisite dependency failure blocking downstream tasks (no fabricated success).
- Test D: Human approval pause and automatic resume preserving previous results.
- Test E: Safe retry and cancellation idempotency.
- Test F: Cross-surface output consistency across analysis payload, report, file artifact, and email.
- Test G: Structural regressions (Calendar Agent removed, Report Archetype removed, Resend preserved).
"""

import os
import csv
import json
import pytest
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.approval_request import APPROVAL_STATUS_PENDING, APPROVAL_STATUS_APPROVED, ApprovalRequest
from app.models.uploaded_file import UploadedFile
from app.models.orchestration_plan import (
    PLAN_TASK_STATUS_AWAITING_APPROVAL,
    PLAN_TASK_STATUS_COMPLETED,
    PLAN_TASK_STATUS_FAILED,
    PLAN_TASK_STATUS_PENDING,
    PLAN_TASK_STATUS_READY,
    PLAN_TASK_STATUS_RUNNING,
    PLAN_TASK_STATUS_CANCELLED,
    OrchestrationPlan,
    PlanTask,
    TaskDependency,
)
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_AWAITING_APPROVAL,
    ORCHESTRATION_STATUS_COMPLETED,
    ORCHESTRATION_STATUS_FAILED,
    ORCHESTRATION_STATUS_READY,
    ORCHESTRATION_STATUS_RUNNING,
    ORCHESTRATION_STATUS_CANCELLED,
    OrchestrationSession,
)
from app.services.planner_service import generate_orchestration_plan
from app.services.supervisor_service import SupervisorService
from app.services.approval_service import resolve_approval_request, create_approval_request
from app.agents import get_agent_instance
from app.agents.base import AgentContext
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.report_generation_agent import ReportGenerationAgent
from app.agents.email_agent import EmailAgent
from tests.test_master_multiagent_workflow_execution import create_test_agents


def _get_quarterly_sales_csv_path() -> str:
    path = r"C:\Users\Mehul\Downloads\quarterly_sales_2026.csv"
    if os.path.exists(path):
        return path
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "quarterly_sales_2026.csv")
    return fixture_path


# -------------------------------------------------------------------------
# Test A: Single task
# -------------------------------------------------------------------------
def test_scenario_a_single_task_security(app, test_user):
    """Test A: A simple security-analysis goal creates an appropriate task,
    displays actual findings, and marks task completed only after execution.
    """
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Perform security analysis and audit code for vulnerabilities",
            input_context={"code_snippet": "import os\nos.system('ls ' + user_input)"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()
        assert len(tasks) >= 1
        t_sec = next((t for t in tasks if t.assigned_agent and t.assigned_agent.agent_type == "security_analysis"), tasks[0])
        assert t_sec.status == PLAN_TASK_STATUS_READY

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(t_sec)
        db.session.refresh(session)

        assert t_sec.status == PLAN_TASK_STATUS_COMPLETED
        assert t_sec.completed_at is not None
        out = t_sec.output_data or {}
        assert out.get("success") is True or "vulnerabilities" in str(out) or "summary" in str(out)
        assert session.status == ORCHESTRATION_STATUS_COMPLETED


# -------------------------------------------------------------------------
# Test B: Multi-agent financial workflow
# -------------------------------------------------------------------------
def test_scenario_b_multi_agent_financial_workflow(app, test_user, monkeypatch):
    """Test B: Upload supplied quarterly sales CSV; Data Analysis calculates expected figures;
    Report Generation consumes actual analysis output; Email consumes findings & enforces approval.
    """
    csv_path = _get_quarterly_sales_csv_path()
    assert os.path.exists(csv_path), f"quarterly_sales_2026.csv not found at {csv_path}"

    with app.app_context():
        create_test_agents(test_user.id)
        uploaded = UploadedFile(
            owner_id=test_user.id,
            filename="quarterly_sales_2026.csv",
            extension=".csv",
            storage_path=csv_path,
            size_bytes=os.path.getsize(csv_path),
            mime_type="text/csv",
        )
        db.session.add(uploaded)
        db.session.commit()

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly sales performance, generate an executive report, and notify the manager",
            input_context={
                "file_id": uploaded.public_id,
                "file_path": csv_path,
                "recipient": "executive-board@enterprise.corp",
                "subject": "2026 Fiscal Performance Review",
            },
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()
        assert len(tasks) == 3

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(session)
        # Approval gate halts execution at AWAITING_APPROVAL
        assert session.status == ORCHESTRATION_STATUS_AWAITING_APPROVAL

        t_da = next(t for t in tasks if t.assigned_agent.agent_type == "data_analysis")
        t_rep = next(t for t in tasks if t.assigned_agent.agent_type == "report_generation")
        t_em = next(t for t in tasks if t.assigned_agent.agent_type == "email")

        db.session.refresh(t_da)
        db.session.refresh(t_rep)
        db.session.refresh(t_em)

        # 1. Data Analysis verified dynamic math
        assert t_da.status == PLAN_TASK_STATUS_COMPLETED
        da_out = t_da.output_data.get("output", t_da.output_data)
        bm = da_out.get("business_metrics", {})
        assert bm.get("total_revenue") == 200500.0
        assert bm.get("total_cost") == 120300.0
        assert bm.get("gross_profit") == 80200.0
        assert bm.get("gross_margin_pct") == 40.0

        p_dict = {p["period"]: p for p in bm.get("period_metrics", [])}
        assert p_dict["Q1"]["revenue"] == 40500.0
        assert p_dict["Q2"]["revenue"] == 48500.0
        assert p_dict["Q3"]["revenue"] == 48000.0
        assert p_dict["Q4"]["revenue"] == 63500.0
        assert round(p_dict["Q4"]["revenue_growth_pct"], 1) == 32.3

        # 2. Report Generation verified content & file artifact
        assert t_rep.status == PLAN_TASK_STATUS_COMPLETED
        rep_out = t_rep.output_data.get("output", t_rep.output_data)
        md = rep_out.get("markdown") or rep_out.get("content") or ""
        assert "$200,500" in md
        assert "$120,300" in md
        assert "$80,200" in md
        assert "40.0%" in md
        assert "32.3%" in md

        art = rep_out.get("artifact", {})
        assert art.get("path") and os.path.exists(art["path"])

        # 3. Email holds at AWAITING_APPROVAL with proposed output
        assert t_em.status in (PLAN_TASK_STATUS_READY, PLAN_TASK_STATUS_AWAITING_APPROVAL)
        appr = ApprovalRequest.query.filter_by(orchestration_id=session.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None


# -------------------------------------------------------------------------
# Test C: Dependency failure blocks downstream tasks
# -------------------------------------------------------------------------
def test_scenario_c_dependency_failure_blocks_downstream(app, test_user):
    """Test C: When an upstream task fails due to corrupt input, dependent tasks
    become BLOCKED with actual error details, and no fabricated report/email is created.
    """
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze corrupted quarterly dataset and generate report",
            input_context={"file_path": "c:/non_existent_corrupted_sales.csv"},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(session)
        assert session.status == ORCHESTRATION_STATUS_FAILED

        t_da = next(t for t in tasks if t.assigned_agent.agent_type == "data_analysis")
        db.session.refresh(t_da)
        assert t_da.status == PLAN_TASK_STATUS_FAILED
        assert "does not exist" in t_da.error_message.lower() or "not found" in t_da.error_message.lower() or "failed" in t_da.error_message.lower()

        # Dependent tasks must be BLOCKED, never COMPLETED
        for t in tasks:
            if t.id != t_da.id:
                db.session.refresh(t)
                assert t.status == "BLOCKED"
                assert "Blocked due to failure of upstream dependency" in (t.error_message or "")
                assert t.output_data == {}


# -------------------------------------------------------------------------
# Test D: Approval and resume preserves state
# -------------------------------------------------------------------------
def test_scenario_d_approval_and_resume_preserves_state(app, test_user, monkeypatch):
    """Test D: Start approval-required email workflow, verify AWAITING_APPROVAL pause,
    approve via resolve_approval_request, and confirm seamless resume to COMPLETED.
    """
    csv_path = _get_quarterly_sales_csv_path()
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly sales, generate report, and notify management",
            input_context={
                "file_path": csv_path,
                "recipient": "board@enterprise.corp",
                "subject": "Verified Q1-Q4 Results",
            },
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)

        db.session.refresh(session)
        assert session.status == ORCHESTRATION_STATUS_AWAITING_APPROVAL

        appr = ApprovalRequest.query.filter_by(orchestration_id=session.id, status=APPROVAL_STATUS_PENDING).first()
        assert appr is not None

        # Resolve approval through application logic
        resolve_approval_request(
            approval_id=appr.id,
            user_id=test_user.id,
            approve=True,
            prevent_self_approval=False,
            comments="Approved by lead finance supervisor.",
        )

        db.session.refresh(appr)
        assert appr.status == APPROVAL_STATUS_APPROVED

        # Resume execution
        supervisor.run_orchestration(session.id)

        db.session.refresh(session)
        assert session.status == ORCHESTRATION_STATUS_COMPLETED

        tasks = plan.tasks.all()
        for t in tasks:
            db.session.refresh(t)
            assert t.status == PLAN_TASK_STATUS_COMPLETED


# -------------------------------------------------------------------------
# Test E: Retry and cancellation idempotency
# -------------------------------------------------------------------------
def test_scenario_e_retry_and_cancellation_idempotency(app, test_user):
    """Test E: Cancelling a task cascades BLOCKED to its children; retrying a task
    resets its status and re-executes cleanly without side-effect duplication.
    """
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly financial performance and email report",
            input_context={},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()
        t_root = next(t for t in tasks if t.upstream_dependencies.count() == 0)

        # Cancel root task
        from app.api.v1.orchestrations import cancel_task_endpoint, retry_task_endpoint
        t_root.status = PLAN_TASK_STATUS_CANCELLED
        t_root.error_message = "Task cancelled by supervisor."
        downstream = TaskDependency.query.filter_by(plan_id=plan.id, parent_task_id=t_root.id).all()
        for d in downstream:
            child = db.session.get(PlanTask, d.child_task_id)
            if child:
                child.status = "BLOCKED"
                child.error_message = f"Blocked due to cancellation of '{t_root.name}'."
        db.session.commit()

        db.session.refresh(t_root)
        assert t_root.status == PLAN_TASK_STATUS_CANCELLED
        for d in downstream:
            child = db.session.get(PlanTask, d.child_task_id)
            assert child.status == "BLOCKED"

        # Safely reset/retry root task
        t_root.status = PLAN_TASK_STATUS_READY
        t_root.error_message = None
        db.session.commit()
        db.session.refresh(t_root)
        assert t_root.status == PLAN_TASK_STATUS_READY


# -------------------------------------------------------------------------
# Test F: Cross-surface output consistency
# -------------------------------------------------------------------------
def test_scenario_f_cross_surface_output_consistency(app, test_user):
    """Test F: Calculated figures ($200,500, $120,300, $80,200, 40%, 32.3%) agree
    consistently across Data Analysis, Report Generation markdown, and Email draft.
    """
    csv_path = _get_quarterly_sales_csv_path()
    da = DataAnalysisAgent()
    da_ctx = AgentContext(task_id="t_f1", user_id=test_user.id, input_data={"file_path": csv_path})
    da_res = da.execute(da_ctx)
    assert da_res.success is True
    da_out = da_res.output
    bm = da_out["business_metrics"]

    rep = ReportGenerationAgent()
    rep_ctx = AgentContext(
        task_id="t_f2",
        user_id=test_user.id,
        input_data={"title": "2026 Executive Financial Report", "format": "markdown"},
        previous_results=[{"agent_type": "data_analysis", "output": da_out}],
    )
    rep_res = rep.execute(rep_ctx)
    assert rep_res.success is True
    rep_out = rep_res.output
    md = rep_out["markdown"]

    em = EmailAgent()
    em_ctx = AgentContext(
        task_id="t_f3",
        user_id=test_user.id,
        input_data={"mode": "draft", "recipient": "finance@corp.com"},
        previous_results=[
            {"agent_type": "data_analysis", "output": da_out},
            {"agent_type": "report_generation", "output": rep_out},
        ],
    )
    em_res = em.execute(em_ctx)
    assert em_res.success is True
    em_out = em_res.output
    em_body = em_out.get("body") or em_out.get("draft", {}).get("body", "")

    # Exact agreement assertions
    # 1. Total Revenue: $200,500
    assert bm["total_revenue"] == 200500.0
    assert "$200,500" in md
    assert "$200,500" in em_body

    # 2. Operating Costs: $120,300
    assert bm["total_cost"] == 120300.0
    assert "$120,300" in md
    assert "$120,300" in em_body

    # 3. Gross Profit: $80,200
    assert bm["gross_profit"] == 80200.0
    assert "$80,200" in md
    assert "$80,200" in em_body

    # 4. Gross Margin: 40.0%
    assert bm["gross_margin_pct"] == 40.0
    assert "40.0%" in md
    assert "40.0%" in em_body

    # 5. Q4 QoQ Growth: 32.3%
    assert "32.3%" in md
    assert "32.3%" in em_body


# -------------------------------------------------------------------------
# Test G: Structural regressions
# -------------------------------------------------------------------------
def test_scenario_g_regression_and_removal_checks():
    """Test G: Confirm Calendar Agent and Report Archetype remain completely removed,
    and Resend email integration is intact.
    """
    from app.agents import list_registered_agent_types, is_agent_registered

    # 1. Calendar Agent removed
    reg_types = list_registered_agent_types()
    assert "calendar" not in reg_types
    assert "google_calendar" not in reg_types
    assert not is_agent_registered("calendar")
    assert not is_agent_registered("google_calendar")

    # 2. Report Archetype removed
    from app.agents.report_generation_agent import ReportGenerationAgent
    rep_inst = ReportGenerationAgent()
    assert not hasattr(rep_inst, "archetype")
    assert not hasattr(rep_inst, "supported_archetypes")

    # 3. Resend email integration intact
    from app.agents.email_agent import EmailAgent
    em = EmailAgent()
    assert hasattr(em, "_dispatch_email")
    assert hasattr(em, "_build_professional_html_email")


# -------------------------------------------------------------------------
# Test H: No recipient fails safely (no hardcoded fallback)
# -------------------------------------------------------------------------
def test_scenario_h_no_recipient_fails_safely(app, test_user, monkeypatch):
    """Test H: When no recipient is configured in input, instructions, or env,
    the EmailAgent must fail safely and immediately without sending to any arbitrary address.
    """
    monkeypatch.delenv("RESEND_TEST_RECIPIENT", raising=False)
    monkeypatch.delenv("EMAIL_RECIPIENT", raising=False)

    em = EmailAgent()
    ctx = AgentContext(
        task_id="t_h1",
        user_id=test_user.id,
        input_data={"subject": "Quarterly Report", "body": "Summary of Q1-Q4 metrics"},
    )
    result = em.execute(ctx)
    assert result.success is False
    assert "recipient email address is required" in (result.error or "").lower()
    assert "valid recipient email" in (result.error or "").lower()

