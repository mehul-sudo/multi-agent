"""
Unit tests for Workflow Graph Validation algorithm (DAG, cycle detection, topological sort).
"""

import pytest
from app.services.workflow_service import (
    activate_workflow,
    add_dependency_to_workflow,
    add_node_to_workflow,
    create_workflow,
    validate_workflow,
)


def test_valid_dag_topological_sort(app, db_session, test_user):
    """Verify valid DAG topological sort ordering."""
    with app.app_context():
        wf = create_workflow(test_user.id, {"name": "DAG Test Workflow"})

        node_a, _ = add_node_to_workflow(wf, test_user.id, {"name": "Node A", "priority": 10})
        node_b, _ = add_node_to_workflow(wf, test_user.id, {"name": "Node B", "priority": 5})
        node_c, _ = add_node_to_workflow(wf, test_user.id, {"name": "Node C", "priority": 1})

        # A -> B -> C
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_a.public_id, "target_node_id": node_b.public_id})
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_b.public_id, "target_node_id": node_c.public_id})

        val_res = validate_workflow(wf)
        assert val_res["valid"] is True
        assert val_res["errors"] == []
        assert val_res["topological_order"] == [node_a.public_id, node_b.public_id, node_c.public_id]
        assert val_res["graph_statistics"]["total_nodes"] == 3
        assert val_res["graph_statistics"]["total_dependencies"] == 2


def test_cycle_detection(app, db_session, test_user):
    """Verify cycle detection identifies cyclic dependency loops (A -> B -> C -> A)."""
    with app.app_context():
        wf = create_workflow(test_user.id, {"name": "Cyclic Workflow"})

        node_a, _ = add_node_to_workflow(wf, test_user.id, {"name": "Node A"})
        node_b, _ = add_node_to_workflow(wf, test_user.id, {"name": "Node B"})
        node_c, _ = add_node_to_workflow(wf, test_user.id, {"name": "Node C"})

        # A -> B -> C -> A
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_a.public_id, "target_node_id": node_b.public_id})
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_b.public_id, "target_node_id": node_c.public_id})
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_c.public_id, "target_node_id": node_a.public_id})

        val_res = validate_workflow(wf)
        assert val_res["valid"] is False
        assert any(e["code"] == "WORKFLOW_CYCLE_DETECTED" for e in val_res["errors"])


def test_isolated_node_warning(app, db_session, test_user):
    """Verify isolated node generates a warning, not a fatal validation error."""
    with app.app_context():
        wf = create_workflow(test_user.id, {"name": "Isolated Node Workflow"})

        node_a, _ = add_node_to_workflow(wf, test_user.id, {"name": "Connected A"})
        node_b, _ = add_node_to_workflow(wf, test_user.id, {"name": "Connected B"})
        node_c, _ = add_node_to_workflow(wf, test_user.id, {"name": "Isolated Node C"})

        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_a.public_id, "target_node_id": node_b.public_id})

        val_res = validate_workflow(wf)
        assert val_res["valid"] is True
        assert any(w["code"] == "ISOLATED_NODE" for w in val_res["warnings"])
