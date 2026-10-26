"""
Tests for stale job recovery, worker heartbeats, dead-letter queue processing, and admin monitoring.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.async_job import JOB_STATUS_DEAD_LETTERED, JOB_STATUS_RUNNING, AsyncWorkflowJob
from app.services.agent_service import create_agent
from app.services.job_service import submit_async_job
from app.services.recovery_service import (
    detect_and_recover_stale_jobs,
    get_monitoring_overview,
    record_worker_heartbeat,
)
from app.services.workflow_service import activate_workflow, add_node_to_workflow, create_workflow


def test_record_worker_heartbeat_and_overview(app, db_session):
    """Verify worker heartbeats and monitoring metrics."""
    with app.app_context():
        record_worker_heartbeat(
            worker_id="worker_node_1",
            hostname="host1.local",
            queues=["default", "high_priority"],
            active_tasks_count=2,
        )

        overview = get_monitoring_overview()
        assert overview["total_active_workers"] >= 1
        assert len(overview["queues"]) > 0


def test_stale_job_recovery(app, db_session, test_user):
    """Stale jobs without recent heartbeats are recovered or dead-lettered."""
    with app.app_context():
        agent = create_agent(user_id=test_user.id, data={"name": "Stale Agent", "system_instructions": "Work"})
        wf = create_workflow(test_user.id, {"name": "Stale WF"})
        add_node_to_workflow(wf, test_user.id, {"name": "Node 1", "agent_id": agent.public_id})
        activate_workflow(wf, test_user.id)

        job, _ = submit_async_job(user_id=test_user.id, workflow_public_id=wf.public_id, data={})
        
        # Simulate worker crash: job left in RUNNING with old heartbeat timestamp
        old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        AsyncWorkflowJob.query.filter_by(id=job.id).update({
            "status": JOB_STATUS_RUNNING,
            "started_at": old_time,
            "last_heartbeat_at": old_time,
            "retry_count": 0,
            "max_retries": 3,
        })
        db_session.commit()

        stats = detect_and_recover_stale_jobs(stale_threshold_seconds=60)
        assert stats["stale_found"] >= 1


def test_admin_monitoring_authorization_check(client, auth_headers, app, db_session, test_user):
    """Non-admin user cannot access admin monitoring endpoint (returns 403)."""
    # test_user is role='user' by default
    res = client.get("/api/v1/admin/workers", headers=auth_headers)
    assert res.status_code == 403


def test_admin_monitoring_for_admin_user(client, app, db_session, test_user):
    """User with role='admin' can access admin monitoring endpoint."""
    with app.app_context():
        u = db.session.get(test_user.__class__, test_user.id)
        u.role = "admin"
        db.session.commit()
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=u.public_id)

    admin_headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/admin/workers", headers=admin_headers)
    assert res.status_code == 200
    assert "total_active_workers" in res.get_json()

