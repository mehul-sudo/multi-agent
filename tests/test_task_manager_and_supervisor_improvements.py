"""
Tests for Task Manager & Supervisor Improvements.

Validates:
1. Meaningful task decomposition for complex objectives (financial reports + emails).
2. Preservation of single tasks for genuinely simple objectives (no artificial inflation).
3. Task Overview counts derived from persisted backend records.
4. Task lifecycle actions: retry and cancel with permission and state transition enforcement.
5. Verification that failed agent executions are never marked COMPLETED.
"""

import pytest
from app.extensions import db
from app.models.orchestration_plan import (
    PLAN_TASK_STATUS_COMPLETED,
    PLAN_TASK_STATUS_FAILED,
    PLAN_TASK_STATUS_CANCELLED,
    PLAN_TASK_STATUS_PENDING,
    PLAN_TASK_STATUS_READY,
    PLAN_TASK_STATUS_RUNNING,
    OrchestrationPlan,
    PlanTask,
    TaskDependency,
)
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_READY,
    ORCHESTRATION_STATUS_FAILED,
    OrchestrationSession,
)
from app.services.planner_service import generate_orchestration_plan
from app.services.supervisor_service import SupervisorService
from tests.test_master_multiagent_workflow_execution import create_test_agents


def test_meaningful_task_decomposition_quarterly_financial_report(app, test_user):
    """'Generate a quarterly financial report and notify the manager' decomposes into data analysis, report generation, and email."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Generate a quarterly financial report and notify the manager",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        assert len(tasks) == 3, f"Expected 3 tasks, got {len(tasks)}"

        task_types = [t.assigned_agent.agent_type for t in tasks if t.assigned_agent]
        assert "data_analysis" in task_types
        assert "report_generation" in task_types
        assert "email" in task_types

        analysis_task = next(t for t in tasks if t.assigned_agent and t.assigned_agent.agent_type == "data_analysis")
        report_task = next(t for t in tasks if t.assigned_agent and t.assigned_agent.agent_type == "report_generation")
        email_task = next(t for t in tasks if t.assigned_agent and t.assigned_agent.agent_type == "email")

        # Report depends on analysis
        report_deps = [dep.parent_task_id for dep in report_task.upstream_dependencies.all()]
        assert analysis_task.id in report_deps

        # Email depends on report
        email_deps = [dep.parent_task_id for dep in email_task.upstream_dependencies.all()]
        assert report_task.id in email_deps


def test_meaningful_task_decomposition_financial_report_no_email(app, test_user):
    """'Generate a quarterly financial report' without email must include data analysis before report generation."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Generate a quarterly financial report",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()

        plan = generate_orchestration_plan(session)
        tasks = plan.tasks.all()

        assert len(tasks) == 2, f"Expected 2 tasks, got {len(tasks)}"

        analysis_task = tasks[0]
        report_task = tasks[1]

        assert analysis_task.assigned_agent.agent_type == "data_analysis"
        assert report_task.assigned_agent.agent_type == "report_generation"

        report_deps = [dep.parent_task_id for dep in report_task.upstream_dependencies.all()]
        assert analysis_task.id in report_deps


def test_genuinely_simple_goals_not_artificially_inflated(app, test_user):
    """Genuinely simple single-step goals must remain 1 task without artificial extra tasks."""
    with app.app_context():
        create_test_agents(test_user.id)

        # 1. Security scan
        s_security = OrchestrationSession(
            user_id=test_user.id,
            objective="Scan codebase for vulnerabilities and security flaws",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(s_security)
        db.session.commit()
        plan_sec = generate_orchestration_plan(s_security)
        assert plan_sec.tasks.count() == 1
        assert plan_sec.tasks.first().assigned_agent.agent_type == "security_analysis"

        # 2. Database query
        s_db = OrchestrationSession(
            user_id=test_user.id,
            objective="Query database for total registered users",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(s_db)
        db.session.commit()
        plan_db = generate_orchestration_plan(s_db)
        assert plan_db.tasks.count() == 1
        assert plan_db.tasks.first().assigned_agent.agent_type == "database_bi"

        # 3. Simple email
        s_email = OrchestrationSession(
            user_id=test_user.id,
            objective="Send email to team about scheduled maintenance",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(s_email)
        db.session.commit()
        plan_email = generate_orchestration_plan(s_email)
        assert plan_email.tasks.count() == 1
        assert plan_email.tasks.first().assigned_agent.agent_type == "email"


def test_task_overview_endpoint(client, auth_headers, test_user, app):
    """GET /api/v1/orchestrations/tasks/overview returns persisted task statistics."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Generate quarterly financial report and notify the manager",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()
        generate_orchestration_plan(session)

    res = client.get("/api/v1/orchestrations/tasks/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()

    assert "total" in data
    assert "pending_queued" in data
    assert "in_progress" in data
    assert "awaiting_approval" in data
    assert "completed" in data
    assert "failed" in data
    assert data["total"] >= 3


def test_task_lifecycle_retry_and_cancel_endpoints(client, auth_headers, test_user, app):
    """Test retry and cancel lifecycle actions on PlanTask records."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Generate financial report and notify the manager",
            input_context={"data": [{"quarter": "Q1", "revenue": 100}, {"quarter": "Q2", "revenue": 120}]},
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()
        plan = generate_orchestration_plan(session)

        tasks = plan.tasks.all()
        task1 = tasks[0]
        task2 = tasks[1]

        # Simulate task1 failed
        task1.status = PLAN_TASK_STATUS_FAILED
        task1.error_message = "Simulated calculation timeout"
        session.status = ORCHESTRATION_STATUS_FAILED
        db.session.commit()

        session_pub_id = session.public_id
        task1_pub_id = task1.public_id
        task2_pub_id = task2.public_id

    # 1. Cancel task 2 (which is pending)
    res_cancel = client.post(
        f"/api/v1/orchestrations/{session_pub_id}/tasks/{task2_pub_id}/cancel",
        headers=auth_headers,
    )
    assert res_cancel.status_code == 200
    data_cancel = res_cancel.get_json()
    assert data_cancel["task"]["status"] == PLAN_TASK_STATUS_CANCELLED

    # 2. Retry task 1 (which was failed)
    res_retry = client.post(
        f"/api/v1/orchestrations/{session_pub_id}/tasks/{task1_pub_id}/retry",
        headers=auth_headers,
    )
    assert res_retry.status_code == 200
    data_retry = res_retry.get_json()
    assert "reset for retry" in data_retry["message"]
    assert data_retry["task"]["status"] in (PLAN_TASK_STATUS_READY, PLAN_TASK_STATUS_RUNNING, PLAN_TASK_STATUS_COMPLETED)

    # 3. State transition enforcement: Cannot retry completed task
    with app.app_context():
        t1 = PlanTask.query.filter_by(public_id=task1_pub_id).first()
        t1.status = PLAN_TASK_STATUS_COMPLETED
        db.session.commit()

    res_retry_completed = client.post(
        f"/api/v1/orchestrations/{session_pub_id}/tasks/{task1_pub_id}/retry",
        headers=auth_headers,
    )
    assert res_retry_completed.status_code == 400
    assert "Cannot retry" in res_retry_completed.get_json()["error"]


def test_never_mark_task_completed_on_agent_failure(app, test_user):
    """Never mark a task completed unless its actual execution succeeded."""
    with app.app_context():
        create_test_agents(test_user.id)
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Analyze corrupted sales dataset",
            status=ORCHESTRATION_STATUS_READY,
        )
        db.session.add(session)
        db.session.commit()
        plan = generate_orchestration_plan(session)
        task = plan.tasks.first()

        # Mock domain agent failing
        class MockFailingAgent:
            def execute(self, ctx):
                from app.agents.base import AgentResult
                return AgentResult(
                    success=False,
                    agent_type="data_analysis",
                    task_id=getattr(ctx, "task_id", "test_task"),
                    error="File not found or corrupted.",
                )

        supervisor = SupervisorService()
        import app.agents
        original_get_agent = app.agents.get_agent_instance
        app.agents.get_agent_instance = lambda agent_type: MockFailingAgent()

        try:
            supervisor._execute_single_task(session, plan, task, auto_approve=True)
        finally:
            app.agents.get_agent_instance = original_get_agent

        db.session.refresh(task)
        assert task.status == PLAN_TASK_STATUS_FAILED
        assert "File not found or corrupted" in (task.error_message or "")
        assert task.status != PLAN_TASK_STATUS_COMPLETED
