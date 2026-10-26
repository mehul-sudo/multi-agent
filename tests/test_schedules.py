"""
Tests for Workflow Schedules, cron expression validation, and scheduled task dispatches.
"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.schedule_service import calculate_next_run, process_due_schedules
from app.services.workflow_service import activate_workflow, add_node_to_workflow, create_workflow
from app.services.agent_service import create_agent


def test_cron_next_run_calculation():
    """Verify next run calculation for valid cron and interval specifications."""
    next_cron = calculate_next_run("cron", cron_expr="0 0 * * *")
    assert next_cron is not None

    next_interval = calculate_next_run("interval", interval_seconds=300)
    assert next_interval is not None


def test_create_workflow_schedule_api(client, auth_headers, app, db_session, test_user):
    """Verify creating a workflow schedule via API."""
    with app.app_context():
        agent = create_agent(
            user_id=test_user.id,
            data={"name": "Sched Agent", "system_instructions": "Do work.", "provider": "mock"},
        )
        wf = create_workflow(test_user.id, {"name": "Sched Workflow"})
        add_node_to_workflow(wf, test_user.id, {"name": "Node 1", "agent_id": agent.public_id})
        activate_workflow(wf, test_user.id)
        wf_id = wf.public_id

    res = client.post(
        f"/api/v1/workflows/{wf_id}/schedules",
        json={
            "schedule_type": "cron",
            "cron_expression": "*/5 * * * *",
            "timezone": "UTC",
            "input_data": {"mode": "auto"},
        },
        headers=auth_headers,
    )

    assert res.status_code == 201
    data = res.get_json()
    assert data["cron_expression"] == "*/5 * * * *"
    assert data["next_run_at"] is not None


def test_invalid_cron_expression_rejected(client, auth_headers, app, db_session, test_user):
    """Creating a schedule with invalid cron string must fail with 400."""
    with app.app_context():
        wf = create_workflow(test_user.id, {"name": "Invalid Cron WF"})
        wf_id = wf.public_id

    res = client.post(
        f"/api/v1/workflows/{wf_id}/schedules",
        json={
            "schedule_type": "cron",
            "cron_expression": "invalid_cron_format",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "VALIDATION_ERROR" in res.get_json()["error"]["code"]


def test_process_due_schedules_dispatches_jobs(app, db_session, test_user):
    """Verify that process_due_schedules creates jobs for due schedules."""
    with app.app_context():
        agent = create_agent(
            user_id=test_user.id,
            data={"name": "Due Agent", "system_instructions": "Work", "provider": "mock"},
        )
        wf = create_workflow(test_user.id, {"name": "Due WF"})
        add_node_to_workflow(wf, test_user.id, {"name": "N1", "agent_id": agent.public_id})
        activate_workflow(wf, test_user.id)

        from app.services.schedule_service import create_schedule
        sched = create_schedule(
            user_id=test_user.id,
            workflow_public_id=wf.public_id,
            data={"schedule_type": "interval", "interval_seconds": 60},
        )
        from app.models.workflow_schedule import WorkflowSchedule
        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        WorkflowSchedule.query.filter_by(id=sched.id).update({"next_run_at": past_time})
        db_session.commit()

        dispatched = process_due_schedules()
        assert dispatched >= 1


