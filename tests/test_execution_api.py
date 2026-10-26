"""
Integration Tests for Execution Endpoints (Phase 5).
"""

import pytest


def test_execute_workflow_endpoint(client, auth_headers):
    """Verify POST /api/workflows/<id>/execute starts an execution."""
    # 1. Create agent
    ag_res = client.post(
        "/api/agents",
        json={"name": "Execution Test Agent", "system_instructions": "Process data."},
        headers=auth_headers,
    )
    agent_id = ag_res.get_json()["public_id"]

    # 2. Create workflow & add node
    wf_res = client.post("/api/workflows", json={"name": "API Execution Workflow"}, headers=auth_headers)
    wf_id = wf_res.get_json()["public_id"]

    client.post(
        f"/api/workflows/{wf_id}/nodes",
        json={"name": "Main Node", "agent_id": agent_id},
        headers=auth_headers,
    )

    # 3. Activate workflow
    client.post(f"/api/workflows/{wf_id}/activate", headers=auth_headers)

    # 4. Trigger execution via API
    exec_res = client.post(
        f"/api/workflows/{wf_id}/execute",
        json={"input_data": {"input_val": 42}, "idempotency_key": "api-exec-1"},
        headers=auth_headers,
    )
    assert exec_res.status_code == 201
    ex_data = exec_res.get_json()
    exec_id = ex_data["public_id"]
    assert ex_data["status"] == "completed"

    # 5. Get execution details
    get_ex = client.get(f"/api/executions/{exec_id}", headers=auth_headers)
    assert get_ex.status_code == 200
    assert get_ex.get_json()["public_id"] == exec_id

    # 6. List tasks for execution
    tasks_res = client.get(f"/api/executions/{exec_id}/tasks", headers=auth_headers)
    assert tasks_res.status_code == 200
    assert len(tasks_res.get_json()["tasks"]) == 1
