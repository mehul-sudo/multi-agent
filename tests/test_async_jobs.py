"""
Tests for Async Jobs API, job creation, state machine transitions, cancellation, retries, and security.
"""

import pytest
from app.models.async_job import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_SUCCEEDED,
    AsyncWorkflowJob,
)
from app.services.agent_service import create_agent
from app.services.job_service import submit_async_job
from app.services.workflow_service import activate_workflow, add_node_to_workflow, create_workflow


@pytest.fixture
def active_workflow_id(app, db_session, test_user):
    """Fixture providing public_id of an active workflow."""
    with app.app_context():
        agent = create_agent(
            user_id=test_user.id,
            data={
                "name": "Async Worker Agent",
                "system_instructions": "Process tasks asynchronously.",
                "provider": "mock",
                "model": "mock-v1",
            },
        )

        wf = create_workflow(test_user.id, {"name": "Async Test Workflow"})
        add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Node 1",
                "agent_id": agent.public_id,
                "output_key": "res",
                "input_mapping": {"query": "$input.query"},
            },
        )

        activate_workflow(wf, test_user.id)
        return wf.public_id


def test_submit_async_workflow_job_success(client, auth_headers, active_workflow_id):
    """Verify submitting an async job to active workflow returns 202 and executes in eager mode."""
    res = client.post(
        f"/api/v1/workflows/{active_workflow_id}/jobs",
        json={
            "input_data": {"query": "Test Data"},
            "queue_name": "default",
            "priority": 1,
        },
        headers=auth_headers,
    )

    assert res.status_code in (200, 202)
    data = res.get_json()
    assert data["job_type"] == "workflow_execution"
    assert data["status"] in (JOB_STATUS_QUEUED, JOB_STATUS_SUCCEEDED)
    assert "public_id" in data


def test_submit_job_unauthenticated_rejected(client, active_workflow_id):
    """Unauthenticated job submission must return 401."""
    res = client.post(
        f"/api/v1/workflows/{active_workflow_id}/jobs",
        json={"input_data": {}},
    )
    assert res.status_code == 401


def test_submit_job_inactive_workflow_rejected(client, auth_headers, app, db_session, test_user):
    """Submitting job for draft/inactive workflow must be rejected with 400."""
    with app.app_context():
        draft_wf = create_workflow(test_user.id, {"name": "Draft Workflow"})
        wf_id = draft_wf.public_id

    res = client.post(
        f"/api/v1/workflows/{wf_id}/jobs",
        json={},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "BAD_REQUEST" in res.get_json()["error"]["code"]


def test_submit_job_idempotency_deduplication(client, auth_headers, active_workflow_id):
    """Submitting job with identical idempotency_key returns original job."""
    payload = {
        "input_data": {"test": 1},
        "idempotency_key": "idemp-key-12345",
    }

    res1 = client.post(
        f"/api/v1/workflows/{active_workflow_id}/jobs",
        json=payload,
        headers=auth_headers,
    )
    assert res1.status_code in (200, 202)
    job1_id = res1.get_json()["public_id"]

    res2 = client.post(
        f"/api/v1/workflows/{active_workflow_id}/jobs",
        json=payload,
        headers=auth_headers,
    )
    assert res2.status_code == 200
    job2_id = res2.get_json()["public_id"]

    assert job1_id == job2_id


def test_get_job_status_and_result(client, auth_headers, active_workflow_id):
    """Verify status and result endpoints for a created job."""
    submit_res = client.post(
        f"/api/v1/workflows/{active_workflow_id}/jobs",
        json={"input_data": {"x": 10}},
        headers=auth_headers,
    )
    job_id = submit_res.get_json()["public_id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert status_res.status_code == 200
    assert status_res.get_json()["public_id"] == job_id

    result_res = client.get(f"/api/v1/jobs/{job_id}/result", headers=auth_headers)
    assert result_res.status_code == 200
    assert "result_data" in result_res.get_json()


def test_cancel_job(client, auth_headers, app, db_session, test_user, active_workflow_id):
    """Verify cancelling an active job."""
    with app.app_context():
        job, _ = submit_async_job(
            user_id=test_user.id,
            workflow_public_id=active_workflow_id,
            data={"queue_name": "default"},
        )
        # Artificially set job to QUEUED state for cancellation test
        AsyncWorkflowJob.query.filter_by(id=job.id).update({"status": JOB_STATUS_QUEUED})
        db_session.commit()
        job_id = job.public_id

    cancel_res = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        json={"reason": "User cancelled execution."},
        headers=auth_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["status"] == JOB_STATUS_CANCELLED


def test_retry_failed_job(client, auth_headers, app, db_session, test_user, active_workflow_id):
    """Verify retrying a failed job."""
    with app.app_context():
        job, _ = submit_async_job(
            user_id=test_user.id,
            workflow_public_id=active_workflow_id,
            data={"queue_name": "default"},
        )
        AsyncWorkflowJob.query.filter_by(id=job.id).update({
            "status": JOB_STATUS_FAILED,
            "error_code": "SIMULATED_FAIL",
        })
        db_session.commit()
        job_id = job.public_id

    retry_res = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        json={"reason": "Manual retry"},
        headers=auth_headers,
    )
    assert retry_res.status_code == 200
    assert retry_res.get_json()["retry_count"] == 1


def test_cross_user_job_access_rejected(client, app, db_session, active_workflow_id, test_user, other_auth_headers):
    """A user cannot query or modify another user's job."""
    with app.app_context():
        job, _ = submit_async_job(
            user_id=test_user.id,
            workflow_public_id=active_workflow_id,
            data={},
        )
        job_id = job.public_id

    res = client.get(f"/api/v1/jobs/{job_id}", headers=other_auth_headers)
    assert res.status_code == 404

