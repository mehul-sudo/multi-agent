"""
Security and Edge Case Tests for Phase 5.
Verifies unauthenticated access, cross-user isolation, cross-workflow dependencies,
invalid state transitions, and input edge cases.
"""

import pytest


def test_unauthenticated_access_rejected(client):
    """Verify unauthenticated requests to Phase 5 endpoints return 401."""
    assert client.get("/api/agents").status_code == 401
    assert client.post("/api/agents", json={"name": "X"}).status_code == 401
    assert client.get("/api/workflows").status_code == 401
    assert client.post("/api/workflows", json={"name": "X"}).status_code == 401
    assert client.get("/api/executions").status_code == 401


def test_cross_user_agent_reference_rejected(client, auth_headers, other_auth_headers):
    """Verify User A cannot reference User B's agent in a workflow node."""
    # User B creates an agent
    ag_res = client.post(
        "/api/agents",
        json={"name": "User B Agent", "system_instructions": "Do work."},
        headers=other_auth_headers,
    )
    user_b_agent_id = ag_res.get_json()["public_id"]

    # User A creates a workflow
    wf_res = client.post("/api/workflows", json={"name": "User A Workflow"}, headers=auth_headers)
    user_a_wf_id = wf_res.get_json()["public_id"]

    # User A tries to add a node referencing User B's agent
    node_res = client.post(
        f"/api/workflows/{user_a_wf_id}/nodes",
        json={"name": "Node referencing B Agent", "agent_id": user_b_agent_id},
        headers=auth_headers,
    )
    assert node_res.status_code == 400
    assert node_res.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_cross_workflow_dependency_rejected(client, auth_headers):
    """Verify creating a dependency edge between nodes in different workflows is rejected."""
    # Workflow 1 & Node A
    wf1 = client.post("/api/workflows", json={"name": "WF 1"}, headers=auth_headers).get_json()["public_id"]
    nA = client.post(f"/api/workflows/{wf1}/nodes", json={"name": "Node A"}, headers=auth_headers).get_json()["public_id"]

    # Workflow 2 & Node B
    wf2 = client.post("/api/workflows", json={"name": "WF 2"}, headers=auth_headers).get_json()["public_id"]
    nB = client.post(f"/api/workflows/{wf2}/nodes", json={"name": "Node B"}, headers=auth_headers).get_json()["public_id"]

    # Try to add dependency in WF1 connecting Node A to Node B (which belongs to WF2)
    dep_res = client.post(
        f"/api/workflows/{wf1}/dependencies",
        json={"source_node_id": nA, "target_node_id": nB},
        headers=auth_headers,
    )
    assert dep_res.status_code == 400


def test_cross_user_workflow_execution_rejected(client, auth_headers, other_auth_headers):
    """Verify User A cannot execute User B's workflow."""
    # User B creates & activates a workflow
    ag = client.post("/api/agents", json={"name": "Ag", "system_instructions": "Work"}, headers=other_auth_headers).get_json()["public_id"]
    wf = client.post("/api/workflows", json={"name": "User B WF"}, headers=other_auth_headers).get_json()["public_id"]
    client.post(f"/api/workflows/{wf}/nodes", json={"name": "N1", "agent_id": ag}, headers=other_auth_headers)
    client.post(f"/api/workflows/{wf}/activate", headers=other_auth_headers)

    # User A tries to execute User B's workflow
    exec_res = client.post(f"/api/workflows/{wf}/execute", headers=auth_headers)
    assert exec_res.status_code == 404


def test_invalid_state_transitions(client, auth_headers):
    """Verify cancelling or retrying a completed execution returns 400 STATE_ERROR."""
    # Create workflow and execute
    ag = client.post("/api/agents", json={"name": "Ag", "system_instructions": "Work"}, headers=auth_headers).get_json()["public_id"]
    wf = client.post("/api/workflows", json={"name": "State Test WF"}, headers=auth_headers).get_json()["public_id"]
    client.post(f"/api/workflows/{wf}/nodes", json={"name": "N1", "agent_id": ag}, headers=auth_headers)
    client.post(f"/api/workflows/{wf}/activate", headers=auth_headers)

    ex_res = client.post(f"/api/workflows/{wf}/execute", headers=auth_headers)
    ex_id = ex_res.get_json()["public_id"]
    assert ex_res.get_json()["status"] == "completed"

    # Try cancelling completed execution
    cancel_res = client.post(f"/api/executions/{ex_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 400
    assert cancel_res.get_json()["error"]["code"] == "STATE_ERROR"

    # Try retrying completed execution
    retry_res = client.post(f"/api/executions/{ex_id}/retry", headers=auth_headers)
    assert retry_res.status_code == 400
    assert retry_res.get_json()["error"]["code"] == "STATE_ERROR"
