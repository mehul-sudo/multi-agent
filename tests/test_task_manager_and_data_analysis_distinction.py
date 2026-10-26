"""
Comprehensive verification test suite: Functional distinction between Task Manager and Data Analysis.

Verifies:
1. End-to-end multi-agent orchestration on a real sales dataset (Data Analysis -> Report Generation -> Email).
   - Data Analysis performs actual calculation and extraction (not Task Manager).
   - Report Generation consumes real statistical findings and generates physical file artifacts.
   - Email Agent enforces approval gate with session pausing at AWAITING_APPROVAL.
   - User approval automatically resumes execution to terminal COMPLETED.
2. Prerequisite failure propagation:
   - Failed upstream task blocks downstream dependent tasks with real diagnostic errors.
   - Blocked tasks never execute or produce fake deliverables.
   - Overall session terminates in FAILED status.
3. Task Manager lifecycle management vs domain agent separation:
   - Overview stats derived from persisted DB records.
   - Task statuses distinct from workflow session statuses.
   - Explicit prerequisite dependencies and attempt counters.
"""

import os
import csv
import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.models.uploaded_file import UploadedFile
from app.models.orchestration_plan import (
    PLAN_TASK_STATUS_AWAITING_APPROVAL,
    PLAN_TASK_STATUS_COMPLETED,
    PLAN_TASK_STATUS_FAILED,
    PLAN_TASK_STATUS_PENDING,
    PLAN_TASK_STATUS_READY,
    PLAN_TASK_STATUS_RUNNING,
    OrchestrationPlan,
    PlanTask,
    TaskDependency,
)
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_AWAITING_APPROVAL,
    ORCHESTRATION_STATUS_COMPLETED,
    ORCHESTRATION_STATUS_FAILED,
    ORCHESTRATION_STATUS_READY,
    OrchestrationSession,
)
from app.services.planner_service import generate_orchestration_plan
from app.services.supervisor_service import SupervisorService
from app.services.approval_service import resolve_approval_request
from tests.test_master_multiagent_workflow_execution import create_test_agents


@pytest.fixture
def sales_csv_file(tmp_path, test_user, app):
    """Create a temporary real sales CSV dataset and persist UploadedFile."""
    csv_file = tmp_path / "quarterly_sales_q1_2026.csv"
    rows = [
        ["date", "region", "product", "units_sold", "revenue"],
        ["2026-01-10", "North America", "Enterprise Cloud", "15", "150000.0"],
        ["2026-01-20", "Europe", "Security Suite", "25", "125000.0"],
        ["2026-02-05", "Asia Pacific", "Enterprise Cloud", "30", "300000.0"],
        ["2026-02-18", "North America", "Automation Engine", "10", "80000.0"],
        ["2026-03-01", "Latin America", "Security Suite", "8", "40000.0"],
        ["2026-03-15", "Europe", "Enterprise Cloud", "20", "200000.0"],
        ["2026-03-25", "Asia Pacific", "Automation Engine", "12", "96000.0"],
    ]
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    with app.app_context():
        record = UploadedFile(
            owner_id=test_user.id,
            filename="quarterly_sales_q1_2026.csv",
            extension=".csv",
            storage_path=str(csv_file),
            size_bytes=os.path.getsize(csv_file),
            mime_type="text/csv",
        )
        db.session.add(record)
        db.session.commit()
        return record.public_id, str(csv_file)


def test_end_to_end_sales_csv_orchestration_with_approval_and_real_data(
    app, test_user, sales_csv_file, monkeypatch
):
    """
    Full End-to-End Orchestration:
    1. Sales CSV uploaded -> Data Analysis computes empirical metrics (7 rows, $991,000 revenue sum).
    2. Report Generation receives empirical findings, generates formal physical deliverable.
    3. Email Agent requires approval -> pauses at AWAITING_APPROVAL.
    4. Approving request resumes automatically -> all tasks reach COMPLETED.
    """
    file_id, _ = sales_csv_file

    with app.app_context():
        create_test_agents(test_user.id)

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly sales figures, generate an executive report, and notify the manager",
            input_context={
                "file_id": file_id,
                "recipient": "director@enterprise.local",
                "subject": "Q1 Quarterly Sales Executive Assessment",
            },
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        # Step 1: Supervisor/Planner generates DAG
        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()
        assert len(tasks) == 3, f"Expected 3 tasks, got {len(tasks)}"

        t_analysis = next(t for t in tasks if t.assigned_agent.agent_type == "data_analysis")
        t_report = next(t for t in tasks if t.assigned_agent.agent_type == "report_generation")
        t_email = next(t for t in tasks if t.assigned_agent.agent_type == "email")

        from app.agents.email_agent import EmailAgent

        # Step 2: First Execution Run (Mocking email dispatch so tests are safe and deterministic)
        with patch.object(EmailAgent, "_dispatch_email", return_value=(True, "email_msg_sales_999", None)):
            supervisor = SupervisorService()
            updated_sess = supervisor.run_orchestration(session.id)

        # Refresh objects
        db.session.refresh(t_analysis)
        db.session.refresh(t_report)
        db.session.refresh(t_email)
        db.session.refresh(updated_sess)

        # Step 3: Verify Data Analysis executed genuinely
        assert t_analysis.status == PLAN_TASK_STATUS_COMPLETED
        assert t_analysis.attempt_count >= 1
        an_out = t_analysis.output_data.get("output", t_analysis.output_data)
        assert an_out.get("row_count") == 7
        assert an_out.get("column_count") == 5
        assert "revenue" in an_out.get("statistics", {}) or "Revenue" in an_out.get("statistics", {})
        rev_key = "revenue" if "revenue" in an_out.get("statistics", {}) else "Revenue"
        rev_sum = an_out["statistics"][rev_key]["sum"]
        assert rev_sum == 991000.0, f"Expected revenue sum 991000.0, got {rev_sum}"

        # Step 4: Verify Report Generation consumed real data
        assert t_report.status == PLAN_TASK_STATUS_COMPLETED, f"t_report failed with: {t_report.error_message}"
        rep_out = t_report.output_data.get("output", t_report.output_data)
        rep_artifacts = t_report.output_data.get("artifacts") or rep_out.get("artifacts") or []
        assert len(rep_artifacts) > 0, "Report Generation must produce physical artifacts"

        # Step 5: Verify Email Agent paused at approval gate
        assert t_email.status == PLAN_TASK_STATUS_AWAITING_APPROVAL
        assert updated_sess.status == ORCHESTRATION_STATUS_AWAITING_APPROVAL

        approval_req = ApprovalRequest.query.filter_by(
            orchestration_id=session.id,
            task_id=t_email.id,
            status=APPROVAL_STATUS_PENDING,
        ).first()
        assert approval_req is not None, "Pending approval request must be persisted in DB"

        # Step 6: Human resolves approval request
        with patch.object(EmailAgent, "_dispatch_email", return_value=(True, "email_msg_sales_approved_100", None)):
            appr_res = resolve_approval_request(
                approval_id=approval_req.id,
                user_id=test_user.id,
                approve=True,
                comments="Authorized sales email release to manager.",
                prevent_self_approval=False,
            )
            assert appr_res.status == "APPROVED"

            # Resuming orchestration completes all tasks automatically
            final_sess = supervisor.run_orchestration(session.id)

        db.session.refresh(t_email)
        db.session.refresh(final_sess)

        assert t_email.status == PLAN_TASK_STATUS_COMPLETED
        assert final_sess.status == ORCHESTRATION_STATUS_COMPLETED
        assert final_sess.result_summary["status"] == "SUCCESS"
        assert final_sess.result_summary["completed_tasks"] == 3


def test_prerequisite_failure_blocks_downstream_tasks_with_real_error(app, test_user):
    """
    If an upstream task fails:
    1. The failed task is marked FAILED with real diagnostic error.
    2. Dependent tasks are marked BLOCKED with explicit upstream blocker message.
    3. The overall session terminates in FAILED status.
    4. Downstream tasks never execute or fabricate output deliverables.
    """
    with app.app_context():
        create_test_agents(test_user.id)

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly sales figures, generate an executive report, and notify the manager",
            input_context={
                "file_id": "non_existent_file_uuid_404",  # Intentional invalid file
                "recipient": "director@enterprise.local",
            },
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()
        assert len(tasks) == 3

        t_analysis = tasks[0]
        t_report = tasks[1]
        t_email = tasks[2]

        supervisor = SupervisorService()
        failed_sess = supervisor.run_orchestration(session.id)

        db.session.refresh(t_analysis)
        db.session.refresh(t_report)
        db.session.refresh(t_email)
        db.session.refresh(failed_sess)

        # 1. Analysis task failed with genuine error
        assert t_analysis.status == PLAN_TASK_STATUS_FAILED
        assert "not found" in (t_analysis.error_message or "").lower()

        # 2. Report task was blocked due to analysis failure
        assert t_report.status == "BLOCKED"
        assert f"Blocked due to failure of upstream dependency '{t_analysis.task_key}'" in t_report.error_message
        assert not t_report.output_data or len(t_report.output_data.get("artifacts", [])) == 0

        # 3. Email task was also blocked
        assert t_email.status == "BLOCKED"

        # 4. Overall session failed
        assert failed_sess.status == ORCHESTRATION_STATUS_FAILED
        assert "1 task(s) failed, 2 task(s) blocked" in failed_sess.failure_reason


def test_task_manager_api_endpoints_and_lifecycle_isolation(client, auth_headers, test_user, app):
    """
    Verify GET /api/v1/orchestrations/<id>/tasks and overview endpoint
    strictly track lifecycle metadata without conflating with Data Analysis.
    """
    with app.app_context():
        create_test_agents(test_user.id)

        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze quarterly sales figures, generate an executive report, and notify the manager",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        # Set distinct lifecycle states on tasks
        tasks[0].status = PLAN_TASK_STATUS_COMPLETED
        tasks[0].attempt_count = 1
        tasks[1].status = PLAN_TASK_STATUS_RUNNING
        tasks[1].attempt_count = 2
        tasks[2].status = PLAN_TASK_STATUS_PENDING
        tasks[2].attempt_count = 0
        db.session.commit()

        sess_pub_id = session.public_id

    # 1. Check tasks list endpoint
    res = client.get(f"/api/v1/orchestrations/{sess_pub_id}/tasks", headers=auth_headers)
    assert res.status_code == 200
    task_items = res.get_json()["tasks"]
    assert len(task_items) == 3

    t1, t2, t3 = task_items[0], task_items[1], task_items[2]
    assert t1["status"] == PLAN_TASK_STATUS_COMPLETED
    assert t1["attempt_count"] == 1
    assert t1["priority"] == 1

    assert t2["status"] == PLAN_TASK_STATUS_RUNNING
    assert t2["attempt_count"] == 2
    assert t2["dependencies"] == [t1["task_key"]]

    assert t3["status"] == PLAN_TASK_STATUS_PENDING
    assert t3["attempt_count"] == 0
    assert t3["dependencies"] == [t2["task_key"]]

    # 2. Check overview endpoint
    res_overview = client.get(f"/api/v1/orchestrations/tasks/overview?orchestration_id={sess_pub_id}", headers=auth_headers)
    assert res_overview.status_code == 200
    stats = res_overview.get_json()
    assert stats["total"] == 3
    assert stats["completed"] == 1
    assert stats["in_progress"] == 1
    assert stats["pending_queued"] == 1
