"""
Test strict sequential execution, multi-stage context passing (A -> B -> C), and failure blocking in DAG execution.
"""

import pytest
from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.task_execution import (
    TASK_STATUS_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_ON_SUCCESS,
    WorkflowDependency,
)
from app.models.workflow_execution import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PARTIALLY_COMPLETED,
    EXECUTION_STATUS_QUEUED,
    WorkflowExecution,
)
from app.models.workflow_node import WorkflowNode
from app.services.execution_engine import (
    AgentExecutor,
    ExecutionResult,
    WorkflowExecutionEngine,
)


class MultiStageTestAgentExecutor(AgentExecutor):
    """Deterministic executor capturing passed inputs across stages."""

    def __init__(self, fail_node_name=None):
        self.recorded_inputs = {}
        self.fail_node_name = fail_node_name

    def execute(self, agent, instructions, inputs, config):
        task_name = config.get("task_name")
        self.recorded_inputs[task_name] = dict(inputs)

        if self.fail_node_name and task_name == self.fail_node_name:
            return ExecutionResult(False, {}, f"Explicit failure in node {task_name}")

        if task_name == "Stage A":
            return ExecutionResult(True, {"findings": "Stage A research insights", "data_count": 42}, None)
        elif task_name == "Stage B":
            return ExecutionResult(True, {"metrics": {"accuracy": 0.99}, "insights": ["Stage B insight"]}, None)
        elif task_name == "Stage C":
            return ExecutionResult(True, {"report_url": "https://example.com/stage_c.pdf"}, None)

        return ExecutionResult(True, {"status": "ok"}, None)


def test_sequential_dag_context_passing(app, db_session, test_user):
    """Verify Node B receives Node A's outputs, and Node C receives BOTH Node A and Node B's outputs."""
    with app.app_context():
        agent = Agent(
            name="Generic Stage Agent",
            agent_type="custom",
            system_instructions="Execute pipeline stages.",
            user_id=test_user.id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add(agent)
        db.session.commit()

        wf = Workflow(
            user_id=test_user.id,
            name="Multi-Stage Pipeline A -> B -> C",
            status=WORKFLOW_STATUS_ACTIVE,
            version=1,
        )
        db.session.add(wf)
        db.session.commit()

        node_a = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Stage A", priority=1)
        node_b = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Stage B", priority=2)
        node_c = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Stage C", priority=3)
        db.session.add_all([node_a, node_b, node_c])
        db.session.commit()

        dep_ab = WorkflowDependency(
            workflow_id=wf.id,
            source_node_id=node_a.id,
            target_node_id=node_b.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        dep_bc = WorkflowDependency(
            workflow_id=wf.id,
            source_node_id=node_b.id,
            target_node_id=node_c.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        db.session.add_all([dep_ab, dep_bc])
        db.session.commit()

        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=test_user.id,
            status=EXECUTION_STATUS_QUEUED,
            input_data={"initial_param": "test_pipeline"},
        )
        db.session.add(execution)
        db.session.commit()

        mock_executor = MultiStageTestAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=mock_executor)
        result_exec = engine.run_execution(execution.id)

        assert result_exec.status == EXECUTION_STATUS_COMPLETED

        # Stage B must have received Stage A's results
        inputs_b = mock_executor.recorded_inputs["Stage B"]
        assert "upstream_results" in inputs_b
        assert "Stage A" in inputs_b["upstream_results"]
        assert inputs_b["upstream_results"]["Stage A"]["findings"] == "Stage A research insights"

        # Stage C must have received BOTH Stage A and Stage B's outputs in previous_results
        inputs_c = mock_executor.recorded_inputs["Stage C"]
        prev_results_c = inputs_c["previous_results"]
        assert isinstance(prev_results_c, list)
        assert len(prev_results_c) == 2

        node_names_in_history = [item["node_name"] for item in prev_results_c]
        assert "Stage A" in node_names_in_history
        assert "Stage B" in node_names_in_history

        # Output fields accumulated into Stage C context
        assert inputs_c.get("findings") == "Stage A research insights"
        assert inputs_c.get("metrics") == {"accuracy": 0.99}


def test_sequential_dag_failure_blocking(app, db_session, test_user):
    """Verify that when Stage B fails, Stage C is blocked and never executed."""
    with app.app_context():
        agent = Agent(
            name="Generic Stage Agent 2",
            agent_type="custom",
            system_instructions="Execute pipeline stages.",
            user_id=test_user.id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add(agent)
        db.session.commit()

        wf = Workflow(
            user_id=test_user.id,
            name="Failing Pipeline A -> B -> C",
            status=WORKFLOW_STATUS_ACTIVE,
            version=1,
        )
        db.session.add(wf)
        db.session.commit()

        node_a = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Stage A", priority=1)
        node_b = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Stage B", priority=2)
        node_c = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Stage C", priority=3)
        db.session.add_all([node_a, node_b, node_c])
        db.session.commit()

        dep_ab = WorkflowDependency(
            workflow_id=wf.id,
            source_node_id=node_a.id,
            target_node_id=node_b.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        dep_bc = WorkflowDependency(
            workflow_id=wf.id,
            source_node_id=node_b.id,
            target_node_id=node_c.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        db.session.add_all([dep_ab, dep_bc])
        db.session.commit()

        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=test_user.id,
            status=EXECUTION_STATUS_QUEUED,
        )
        db.session.add(execution)
        db.session.commit()

        # Instruct executor to fail specifically on Stage B
        mock_executor = MultiStageTestAgentExecutor(fail_node_name="Stage B")
        engine = WorkflowExecutionEngine(agent_executor=mock_executor)
        result_exec = engine.run_execution(execution.id)

        # Execution should be PARTIALLY_COMPLETED (since A completed, B failed, C blocked)
        assert result_exec.status == EXECUTION_STATUS_PARTIALLY_COMPLETED

        # Stage C must NEVER have been executed
        assert "Stage C" not in mock_executor.recorded_inputs

        task_exec_b = [te for te in execution.task_executions if te.workflow_node_id == node_b.id][0]
        task_exec_c = [te for te in execution.task_executions if te.workflow_node_id == node_c.id][0]

        assert task_exec_b.status == TASK_STATUS_FAILED
        assert task_exec_c.status == TASK_STATUS_BLOCKED
        assert "Blocked" in task_exec_c.error_data.get("error", "")
