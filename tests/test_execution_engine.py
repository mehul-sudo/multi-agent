"""
Unit and Integration Tests for Execution Engine, Context Passing, Retries & Idempotency.
"""

import pytest
from app.models.task_execution import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED
from app.models.workflow_execution import EXECUTION_STATUS_COMPLETED, EXECUTION_STATUS_FAILED
from app.services.agent_service import create_agent
from app.services.execution_service import trigger_workflow_execution
from app.services.workflow_service import (
    activate_workflow,
    add_dependency_to_workflow,
    add_node_to_workflow,
    create_workflow,
)


def test_full_workflow_execution_and_context_passing(app, db_session, test_user):
    """Verify execution runs tasks in order and passes outputs between nodes."""
    with app.app_context():
        agent = create_agent(
            test_user.id,
            {"name": "Research Agent", "agent_type": "document_research", "system_instructions": "Research docs."},
        )

        wf = create_workflow(test_user.id, {"name": "Execution Pipeline"})

        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Extract Info",
                "agent_id": agent.public_id,
                "output_key": "step1_data",
                "input_mapping": {"doc_title": "$input.title"},
            },
        )

        n2, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Generate Summary",
                "agent_id": agent.public_id,
                "output_key": "step2_data",
                "input_mapping": {"previous": "$context.step1_data"},
            },
        )

        add_dependency_to_workflow(
            wf, test_user.id, {"source_node_id": n1.public_id, "target_node_id": n2.public_id}
        )

        activate_workflow(wf, test_user.id)

        # Execute
        execution, is_new = trigger_workflow_execution(
            workflow=wf,
            user_id=test_user.id,
            input_data={"title": "Enterprise Automation Spec"},
            idempotency_key="unique-exec-key-101",
        )

        assert is_new is True
        assert execution.status == EXECUTION_STATUS_COMPLETED
        assert "step1_data" in execution.output_data
        assert "step2_data" in execution.output_data


def test_idempotency_key_reuse(app, db_session, test_user):
    """Verify triggering execution with the same idempotency key returns existing execution."""
    with app.app_context():
        agent = create_agent(test_user.id, {"name": "Worker", "system_instructions": "Work."})
        wf = create_workflow(test_user.id, {"name": "Idempotent Workflow"})
        add_node_to_workflow(wf, test_user.id, {"name": "Task 1", "agent_id": agent.public_id})
        activate_workflow(wf, test_user.id)

        key = "idempotent-test-key-555"

        exec1, is_new1 = trigger_workflow_execution(wf, test_user.id, idempotency_key=key)
        assert is_new1 is True

        exec2, is_new2 = trigger_workflow_execution(wf, test_user.id, idempotency_key=key)
        assert is_new2 is False
        assert exec1.public_id == exec2.public_id


def test_task_retry_limit_enforcement(app, db_session, test_user):
    """Verify task retries up to retry_limit when failing."""
    with app.app_context():
        agent = create_agent(test_user.id, {"name": "Failing Agent", "system_instructions": "Fail."})
        wf = create_workflow(test_user.id, {"name": "Retry Workflow"})

        node, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Failing Task",
                "agent_id": agent.public_id,
                "retry_limit": 2,
                "configuration": {"simulate_failure": True, "failure_reason": "API timeout"},
            },
        )

        activate_workflow(wf, test_user.id)

        execution, _ = trigger_workflow_execution(wf, test_user.id)
        assert execution.status == EXECUTION_STATUS_FAILED

        te = execution.task_executions[0]
        assert te.status == TASK_STATUS_FAILED
        assert te.attempt_number == 3  # Initial attempt + 2 retries
