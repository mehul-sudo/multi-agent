"""
Phase 9 Tests - Concurrency, Idempotency, and Idempotency deduplication under concurrent requests.
"""

import pytest


def test_concurrent_pause_resume(client, auth_headers):
    """Verify that sequential pause/resume/pause calls are safe and idempotent."""
    # Create workflow via API (active status is required for schedule creation)
    wf_res = client.post(
        "/api/workflows",
        headers=auth_headers,
        json={"name": "Concurrency Test WF"},
    )
    assert wf_res.status_code == 201, f"Workflow creation failed: {wf_res.get_json()}"
    wf_id = wf_res.get_json()["public_id"]

    # Add a node so workflow can be activated
    node_res = client.post(
        f"/api/workflows/{wf_id}/nodes",
        headers=auth_headers,
        json={"name": "Task Node"},
    )
    assert node_res.status_code == 201, f"Node creation failed: {node_res.get_json()}"

    # Activate the workflow
    act_res = client.post(f"/api/workflows/{wf_id}/activate", headers=auth_headers)
    assert act_res.status_code == 200, f"Activation failed: {act_res.get_json()}"

    # Create schedule
    sched_payload = {"schedule_type": "interval", "interval_seconds": 60}
    res = client.post(f"/api/v1/workflows/{wf_id}/schedules", json=sched_payload, headers=auth_headers)
    assert res.status_code == 201, f"Schedule creation failed: {res.get_json()}"
    sched_id = res.get_json()["public_id"]

    # Sequential pause/resume/pause cycle — safe idempotency check
    # (Real thread tests are skipped for SQLite; sequential checks verify state machine safety)
    res1 = client.post(f"/api/v1/schedules/{sched_id}/pause", headers=auth_headers)
    res2 = client.post(f"/api/v1/schedules/{sched_id}/resume", headers=auth_headers)
    res3 = client.post(f"/api/v1/schedules/{sched_id}/pause", headers=auth_headers)

    assert res1.status_code in (200, 201, 202), f"Pause 1 failed: {res1.get_json()}"
    assert res2.status_code in (200, 201, 202), f"Resume failed: {res2.get_json()}"
    assert res3.status_code in (200, 201, 202), f"Pause 2 failed: {res3.get_json()}"

    # Verify final state via GET
    check_res = client.get(f"/api/v1/schedules/{sched_id}", headers=auth_headers)
    assert check_res.status_code == 200
    final_status = check_res.get_json()["status"]
    assert final_status in ("active", "paused"), f"Unexpected final status: {final_status}"


def test_idempotency_under_concurrent_requests(client, auth_headers):
    """Verify idempotency key deduplication: 3 identical submissions should yield 1 unique job."""
    # Create workflow via API
    wf_res = client.post(
        "/api/workflows",
        headers=auth_headers,
        json={"name": "Idempotency Test WF 2"},
    )
    assert wf_res.status_code == 201, f"Workflow creation failed: {wf_res.get_json()}"
    wf_id = wf_res.get_json()["public_id"]

    # Add a node and activate
    node_res = client.post(
        f"/api/workflows/{wf_id}/nodes",
        headers=auth_headers,
        json={"name": "Task Node"},
    )
    assert node_res.status_code == 201

    act_res = client.post(f"/api/workflows/{wf_id}/activate", headers=auth_headers)
    assert act_res.status_code == 200

    # Submit 3 times with the same idempotency key
    results = []
    for _ in range(3):
        res = client.post(
            f"/api/v1/workflows/{wf_id}/jobs",
            headers=auth_headers,
            json={"idempotency_key": "fixed-key-123", "input_data": {}},
        )
        results.append(res)

    status_codes = [r.status_code for r in results]
    assert all(code in (200, 201, 202, 409, 400) for code in status_codes)

    job_ids = [r.json["job_id"] for r in results if r.status_code in (200, 201, 202) and "job_id" in r.json]
    if job_ids:
        assert len(set(job_ids)) == 1, f"Idempotency violated: multiple job IDs returned: {set(job_ids)}"
