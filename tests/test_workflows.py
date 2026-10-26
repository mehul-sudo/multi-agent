"""
Unit and Integration Tests for Workflow Design API & Service (Phase 5).
"""

import pytest
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, WORKFLOW_STATUS_DRAFT


def test_create_workflow(client, auth_headers):
    """Verify creating a draft workflow."""
    payload = {
        "name": "Customer Support Automation",
        "description": "Processes customer support tickets using multi-agent workflow.",
        "input_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
    }
    response = client.post("/api/workflows", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Customer Support Automation"
    assert data["status"] == WORKFLOW_STATUS_DRAFT
    assert data["version"] == 1


def test_add_nodes_and_dependencies(client, auth_headers):
    """Verify adding nodes and creating dependencies between them."""
    # 1. Create agent
    ag_res = client.post(
        "/api/agents",
        json={"name": "Worker Agent", "system_instructions": "Do work."},
        headers=auth_headers,
    )
    agent_id = ag_res.get_json()["public_id"]

    # 2. Create workflow
    wf_res = client.post(
        "/api/workflows",
        json={"name": "Multi-Node Workflow"},
        headers=auth_headers,
    )
    wf_id = wf_res.get_json()["public_id"]

    # 3. Add Node 1
    n1_res = client.post(
        f"/api/workflows/{wf_id}/nodes",
        json={"name": "Step 1", "agent_id": agent_id, "output_key": "step1_output"},
        headers=auth_headers,
    )
    assert n1_res.status_code == 201
    node1_id = n1_res.get_json()["public_id"]

    # 4. Add Node 2
    n2_res = client.post(
        f"/api/workflows/{wf_id}/nodes",
        json={"name": "Step 2", "agent_id": agent_id, "output_key": "step2_output"},
        headers=auth_headers,
    )
    assert n2_res.status_code == 201
    node2_id = n2_res.get_json()["public_id"]

    # 5. Add Dependency: Node 1 -> Node 2
    dep_res = client.post(
        f"/api/workflows/{wf_id}/dependencies",
        json={"source_node_id": node1_id, "target_node_id": node2_id, "dependency_type": "on_success"},
        headers=auth_headers,
    )
    assert dep_res.status_code == 201
    dep_id = dep_res.get_json()["public_id"]

    # 6. Verify Workflow details contains nodes and dependencies
    get_wf = client.get(f"/api/workflows/{wf_id}", headers=auth_headers)
    assert get_wf.status_code == 200
    wf_data = get_wf.get_json()
    assert len(wf_data["nodes"]) == 2
    assert len(wf_data["dependencies"]) == 1


def test_reject_self_dependency_and_duplicate(client, auth_headers):
    """Verify self-dependency and duplicate dependency edges are rejected."""
    wf_res = client.post("/api/workflows", json={"name": "Test Workflow"}, headers=auth_headers)
    wf_id = wf_res.get_json()["public_id"]

    n1_res = client.post(f"/api/workflows/{wf_id}/nodes", json={"name": "Node A"}, headers=auth_headers)
    n1_id = n1_res.get_json()["public_id"]

    n2_res = client.post(f"/api/workflows/{wf_id}/nodes", json={"name": "Node B"}, headers=auth_headers)
    n2_id = n2_res.get_json()["public_id"]

    # Test Self-dependency
    self_dep = client.post(
        f"/api/workflows/{wf_id}/dependencies",
        json={"source_node_id": n1_id, "target_node_id": n1_id},
        headers=auth_headers,
    )
    assert self_dep.status_code == 400

    # Add valid dep
    client.post(
        f"/api/workflows/{wf_id}/dependencies",
        json={"source_node_id": n1_id, "target_node_id": n2_id},
        headers=auth_headers,
    )

    # Test Duplicate dep
    dup_dep = client.post(
        f"/api/workflows/{wf_id}/dependencies",
        json={"source_node_id": n1_id, "target_node_id": n2_id},
        headers=auth_headers,
    )
    assert dup_dep.status_code == 400


def test_activate_empty_workflow_rejected(client, auth_headers):
    """Verify activating an empty workflow fails validation."""
    wf_res = client.post("/api/workflows", json={"name": "Empty Workflow"}, headers=auth_headers)
    wf_id = wf_res.get_json()["public_id"]

    act_res = client.post(f"/api/workflows/{wf_id}/activate", headers=auth_headers)
    assert act_res.status_code == 400
    assert act_res.get_json()["error"]["code"] == "VALIDATION_FAILED"


def test_delete_node_with_task_executions(client, auth_headers):
    """Verify deleting a node succeeds even when historical task_executions point to it."""
    from app.extensions import db
    from app.models.workflow import Workflow
    from app.models.workflow_execution import WorkflowExecution
    from app.models.workflow_node import WorkflowNode
    from app.models.task_execution import TaskExecution
    from app.models.user import User

    # 1. Create workflow and node
    wf_res = client.post("/api/workflows", json={"name": "Delete Node Test WF"}, headers=auth_headers)
    wf_id = wf_res.get_json()["public_id"]

    n_res = client.post(f"/api/workflows/{wf_id}/nodes", json={"name": "Node To Delete"}, headers=auth_headers)
    node_id = n_res.get_json()["public_id"]

    # 2. Add an execution and task execution in DB
    wf = Workflow.query.filter_by(public_id=wf_id).first()
    node = WorkflowNode.query.filter_by(public_id=node_id).first()

    exec_record = WorkflowExecution(
        workflow_id=wf.id,
        user_id=wf.user_id,
        status="completed",
        input_data={},
    )
    db.session.add(exec_record)
    db.session.flush()

    task_exec = TaskExecution(
        workflow_execution_id=exec_record.id,
        workflow_node_id=node.id,
        status="completed",
        input_data={},
    )
    db.session.add(task_exec)
    db.session.commit()

    # 3. Now delete the node via API (this previously threw NOT NULL constraint 500)
    del_res = client.delete(f"/api/workflows/{wf_id}/nodes/{node_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.get_json()["message"] == "Workflow node deleted successfully."

    # 4. Confirm node no longer exists
    get_wf = client.get(f"/api/workflows/{wf_id}", headers=auth_headers)
    assert get_wf.status_code == 200
    assert len(get_wf.get_json()["nodes"]) == 0


def test_delete_workflow_archive_and_force(client, auth_headers):
    """Verify delete workflow archives when force=false, and permanently hard deletes when force=true."""
    from app.extensions import db
    from app.models.workflow import Workflow
    from app.models.workflow_execution import WorkflowExecution
    from app.models.user import User

    # 1. Create workflow
    wf_res = client.post("/api/workflows", json={"name": "Delete WF Test"}, headers=auth_headers)
    wf_id = wf_res.get_json()["public_id"]

    client.post(f"/api/workflows/{wf_id}/nodes", json={"name": "Step 1"}, headers=auth_headers)

    wf = Workflow.query.filter_by(public_id=wf_id).first()

    exec_record = WorkflowExecution(
        workflow_id=wf.id,
        user_id=wf.user_id,
        status="completed",
        input_data={},
    )
    db.session.add(exec_record)
    db.session.commit()

    # 2. Delete with force=false -> Should archive safely
    del_res = client.delete(f"/api/workflows/{wf_id}?force=false", headers=auth_headers)
    assert del_res.status_code == 200
    assert "archived" in del_res.get_json()["message"].lower()

    # 3. Delete with force=true -> Should completely delete workflow and child records
    del_res2 = client.delete(f"/api/workflows/{wf_id}?force=true", headers=auth_headers)
    assert del_res2.status_code == 200
    assert "deleted" in del_res2.get_json()["message"].lower()

    # Confirm it's gone
    get_wf = client.get(f"/api/workflows/{wf_id}", headers=auth_headers)
    assert get_wf.status_code == 404


def test_delete_dependency_edge(client, auth_headers):
    """Verify deleting a dependency edge between nodes."""
    wf_res = client.post("/api/workflows", json={"name": "Dep Edge WF"}, headers=auth_headers)
    wf_id = wf_res.get_json()["public_id"]

    n1 = client.post(f"/api/workflows/{wf_id}/nodes", json={"name": "A"}, headers=auth_headers).get_json()["public_id"]
    n2 = client.post(f"/api/workflows/{wf_id}/nodes", json={"name": "B"}, headers=auth_headers).get_json()["public_id"]

    dep = client.post(
        f"/api/workflows/{wf_id}/dependencies",
        json={"source_node_id": n1, "target_node_id": n2},
        headers=auth_headers,
    ).get_json()["public_id"]

    # Delete dependency edge
    del_dep = client.delete(f"/api/workflows/{wf_id}/dependencies/{dep}", headers=auth_headers)
    assert del_dep.status_code == 200

    # Verify dependency count is 0
    wf_data = client.get(f"/api/workflows/{wf_id}", headers=auth_headers).get_json()
    assert len(wf_data["dependencies"]) == 0
