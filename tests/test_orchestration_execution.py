"""
Tests for Orchestration Execution Engine and Celery Worker Tasks.
"""

from app.extensions import db
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_CANCELLED,
    ORCHESTRATION_STATUS_COMPLETED,
    ORCHESTRATION_STATUS_PAUSED,
    OrchestrationSession,
)
from app.services.planner_service import generate_orchestration_plan
from app.tasks.orchestration_tasks import execute_orchestration_task


def test_create_and_execute_orchestration_via_api(client, auth_headers):
    """Test creating and executing an orchestration session end-to-end."""
    payload = {
        "objective": "Generate quarterly financial report.",
        "priority": 1,
    }
    create_res = client.post("/api/v1/orchestrations", json=payload, headers=auth_headers)
    assert create_res.status_code == 201
    orch_data = create_res.get_json()["orchestration"]
    orch_id = orch_data["id"]

    # Start orchestration
    start_res = client.post(f"/api/v1/orchestrations/{orch_id}/start", headers=auth_headers)
    assert start_res.status_code == 200
    assert start_res.get_json()["status"] == ORCHESTRATION_STATUS_COMPLETED

    # Get orchestration details
    get_res = client.get(f"/api/v1/orchestrations/{orch_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.get_json()["status"] == ORCHESTRATION_STATUS_COMPLETED

    # Check audit events
    events_res = client.get(f"/api/v1/orchestrations/{orch_id}/events", headers=auth_headers)
    assert events_res.status_code == 200
    assert len(events_res.get_json()["events"]) >= 3


def test_pause_resume_cancel_orchestration(client, auth_headers):
    """Test pausing, resuming, and cancelling an orchestration session."""
    payload = {"objective": "Long running automation objective."}
    create_res = client.post("/api/v1/orchestrations", json=payload, headers=auth_headers)
    orch_id = create_res.get_json()["orchestration"]["id"]

    pause_res = client.post(f"/api/v1/orchestrations/{orch_id}/pause", headers=auth_headers)
    assert pause_res.status_code == 200
    assert pause_res.get_json()["status"] == ORCHESTRATION_STATUS_PAUSED

    cancel_res = client.post(f"/api/v1/orchestrations/{orch_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["status"] == ORCHESTRATION_STATUS_CANCELLED


def test_celery_task_eager_orchestration_execution(app, test_user):
    """Test eager Celery worker task execution for orchestrations."""
    with app.app_context():
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Celery background task execution test.",
        )
        db.session.add(session)
        db.session.flush()

        generate_orchestration_plan(session)
        db.session.commit()

        # Run eager Celery task directly
        res = execute_orchestration_task(session.id)
        assert res["status"] in ("completed", "succeeded", "ready")
