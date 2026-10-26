"""
Phase 9 Tests — Execution Plan Generation, Priority Inheritance & Conditional/Optional Dependencies.
"""

import pytest
from app.extensions import db
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_execution import WorkflowExecution
from app.models.workflow_node import WorkflowNode
from app.services.execution_engine import WorkflowExecutionEngine
from app.services.execution_plan_service import (
    generate_execution_plan,
    get_execution_plan_for_workflow,
)
from app.services.graph_validation_service import validate_workflow_graph
from app.services.workflow_service import (
    activate_workflow,
    add_dependency_to_workflow,
    add_node_to_workflow,
    create_workflow,
)


def test_execution_plan_stages_and_priority_inheritance(app, auth_headers):
    with app.app_context():
        user_id = 1
        wf = create_workflow(user_id, {"name": "Staged Workflow", "priority": 5})

        n1, _ = add_node_to_workflow(wf, user_id, {"name": "Node A", "priority": 2})
        n2, _ = add_node_to_workflow(wf, user_id, {"name": "Node B", "priority": 3})
        n3, _ = add_node_to_workflow(wf, user_id, {"name": "Node C", "priority": 1})

        # A -> B -> C
        add_dependency_to_workflow(
            wf, user_id, {"source_node_id": n1.public_id, "target_node_id": n2.public_id}
        )
        add_dependency_to_workflow(
            wf, user_id, {"source_node_id": n2.public_id, "target_node_id": n3.public_id}
        )

        plan = generate_execution_plan(wf)
        assert len(plan.stages) == 3
        assert plan.stages[0] == [n1.public_id]
        assert plan.stages[1] == [n2.public_id]
        assert plan.stages[2] == [n3.public_id]

        # Check priority inheritance calculation:
        # Node A: priority = 5 (wf) + 2 (base) = 7
        # Node B: priority = 5 + 3 (base) + 7 (parent) = 15
        # Node C: priority = 5 + 1 (base) + 15 (parent) = 21
        assert plan.node_priorities[n1.public_id] == 7
        assert plan.node_priorities[n2.public_id] == 15
        assert plan.node_priorities[n3.public_id] == 21


def test_graph_validation_invalid_condition_syntax(app):
    with app.app_context():
        user_id = 1
        wf = create_workflow(user_id, {"name": "Invalid Condition WF"})
        n1, _ = add_node_to_workflow(wf, user_id, {"name": "N1"})
        n2, _ = add_node_to_workflow(wf, user_id, {"name": "N2"})

        add_dependency_to_workflow(
            wf,
            user_id,
            {
                "source_node_id": n1.public_id,
                "target_node_id": n2.public_id,
                "condition": "invalid syntax ++ -- ***",
            },
        )

        val = validate_workflow_graph(wf)
        assert val["valid"] is False
        assert any(e["code"] == "INVALID_CONDITION_SYNTAX" for e in val["errors"])


def test_optional_dependency_execution(app):
    with app.app_context():
        user_id = 1
        wf = create_workflow(user_id, {"name": "Optional Dep WF"})
        n1, _ = add_node_to_workflow(wf, user_id, {"name": "Optional Source"})
        n2, _ = add_node_to_workflow(wf, user_id, {"name": "Target Node"})

        # n1 -> n2 optional dependency
        add_dependency_to_workflow(
            wf,
            user_id,
            {
                "source_node_id": n1.public_id,
                "target_node_id": n2.public_id,
                "is_optional": True,
            },
        )

        activate_workflow(wf, user_id)

        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=user_id,
            status="queued",
            input_data={},
        )
        db.session.add(execution)
        db.session.commit()

        engine = WorkflowExecutionEngine()
        res = engine.run_execution(execution.id)
        assert res.status == "completed"


def test_conditional_dependency_evaluation_during_execution(app):
    with app.app_context():
        user_id = 1
        wf = create_workflow(user_id, {"name": "Conditional WF"})
        n1, _ = add_node_to_workflow(
            wf, user_id, {"name": "Producer", "output_key": "prod", "configuration": {"result": {"score": 95}}}
        )
        n2, _ = add_node_to_workflow(wf, user_id, {"name": "High Score Consumer"})

        # Only run n2 if prod score > 50
        add_dependency_to_workflow(
            wf,
            user_id,
            {
                "source_node_id": n1.public_id,
                "target_node_id": n2.public_id,
                "condition": "node_outputs['prod']['score'] > 50",
            },
        )

        activate_workflow(wf, user_id)

        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=user_id,
            status="queued",
            input_data={},
        )
        db.session.add(execution)
        db.session.commit()

        engine = WorkflowExecutionEngine()
        res = engine.run_execution(execution.id)
        assert res.status == "completed"
