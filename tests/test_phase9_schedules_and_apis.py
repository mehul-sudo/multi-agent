"""
Phase 9 Tests — Schedule Management APIs, Timezone, Misfire Policies & Duplicate Prevention.
"""

from datetime import datetime, timedelta, timezone
import pytest
from app.extensions import db
from app.models.workflow_schedule import (
    SCHEDULE_STATUS_ACTIVE,
    SCHEDULE_STATUS_CANCELLED,
    SCHEDULE_STATUS_PAUSED,
    WorkflowSchedule,
)
from app.services.schedule_service import (
    calculate_next_run,
    create_schedule,
    process_due_schedules,
)
from app.services.workflow_service import activate_workflow, add_node_to_workflow, create_workflow


def test_schedule_pause_resume_cancel_apis(client, auth_headers, test_user):
    # 1. Create active workflow
    wf_res = client.post(
        "/api/workflows",
        headers=auth_headers,
        json={"name": "Sched Test WF"},
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.get_json()["public_id"]

    node_res = client.post(
        f"/api/workflows/{wf_id}/nodes",
        headers=auth_headers,
        json={"name": "Task Node"},
    )
    assert node_res.status_code == 201

    act_res = client.post(f"/api/workflows/{wf_id}/activate", headers=auth_headers)
    assert act_res.status_code == 200

    # 2. Create schedule
    sched_res = client.post(
        f"/api/v1/workflows/{wf_id}/schedules",
        headers=auth_headers,
        json={
            "schedule_type": "cron",
            "cron_expression": "*/15 * * * *",
            "timezone": "America/New_York",
        },
    )
    assert sched_res.status_code == 201
    sched = sched_res.get_json()
    sched_id = sched["public_id"]
    assert sched["status"] == "active"
    assert sched["is_enabled"] is True

    # 3. Pause schedule
    pause_res = client.post(f"/api/v1/schedules/{sched_id}/pause", headers=auth_headers)
    assert pause_res.status_code == 200
    paused = pause_res.get_json()
    assert paused["status"] == "paused"
    assert paused["is_enabled"] is False

    # 4. Resume schedule
    resume_res = client.post(f"/api/v1/schedules/{sched_id}/resume", headers=auth_headers)
    assert resume_res.status_code == 200
    resumed = resume_res.get_json()
    assert resumed["status"] == "active"
    assert resumed["is_enabled"] is True

    # 5. Cancel schedule
    cancel_res = client.post(f"/api/v1/schedules/{sched_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 200
    cancelled = cancel_res.get_json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["is_enabled"] is False
    assert cancelled["next_run_at"] is None


def test_schedule_timezone_aware_next_run():
    base_time = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)

    # America/New_York
    next_ny = calculate_next_run(
        schedule_type="cron",
        cron_expr="0 9 * * *",  # 9 AM NY time
        start_from=base_time,
        tz_name="America/New_York",
    )
    assert next_ny is not None

    # Asia/Kolkata
    next_ist = calculate_next_run(
        schedule_type="cron",
        cron_expr="0 9 * * *",
        start_from=base_time,
        tz_name="Asia/Kolkata",
    )
    assert next_ist is not None


def test_idempotent_schedule_creation(app):
    with app.app_context():
        user_id = 1
        wf = create_workflow(user_id, {"name": "Idempotency WF"})
        s1 = create_schedule(
            user_id,
            wf.public_id,
            {"schedule_type": "cron", "cron_expression": "0 * * * *", "idempotency_key": "key_123"},
        )
        s2 = create_schedule(
            user_id,
            wf.public_id,
            {"schedule_type": "cron", "cron_expression": "0 * * * *", "idempotency_key": "key_123"},
        )
        assert s1.id == s2.id


def test_schedule_misfire_policy_skip(app):
    with app.app_context():
        user_id = 1
        wf = create_workflow(user_id, {"name": "Misfire WF"})
        node, _ = add_node_to_workflow(wf, user_id, {"name": "Task Node"})
        activate_workflow(wf, user_id)

        # Create schedule with next_run_at 10 minutes in the past
        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        sched = create_schedule(
            user_id,
            wf.public_id,
            {
                "schedule_type": "cron",
                "cron_expression": "*/5 * * * *",
                "misfire_policy": "skip",
            },
        )
        sched.next_run_at = past_time
        db.session.commit()

        dispatched = process_due_schedules()
        db.session.refresh(sched)
        assert sched.next_run_at > past_time


def test_workflow_execution_plan_api_endpoint(client, auth_headers):
    wf_res = client.post(
        "/api/workflows",
        headers=auth_headers,
        json={"name": "Execution Plan API WF"},
    )
    wf_id = wf_res.get_json()["public_id"]

    plan_res = client.get(f"/api/workflows/{wf_id}/execution-plan", headers=auth_headers)
    assert plan_res.status_code == 200
    plan_data = plan_res.get_json()
    assert plan_data["workflow_id"] == wf_id
    assert "stages" in plan_data
    assert "node_priorities" in plan_data
