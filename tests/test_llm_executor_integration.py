"""
Integration tests for LLMAgentExecutor, usage tracking, structured output parsing, and workflow execution.
"""

import pytest
from app.models.llm_usage import LLMUsageLog
from app.models.task_execution import TASK_STATUS_COMPLETED
from app.models.workflow_execution import EXECUTION_STATUS_COMPLETED
from app.services.agent_service import create_agent, update_agent
from app.services.execution_engine import LLMAgentExecutor, WorkflowExecutionEngine
from app.services.execution_service import trigger_workflow_execution
from app.services.llm_usage_service import calculate_estimated_cost
from app.services.workflow_service import activate_workflow, add_node_to_workflow, create_workflow


def test_estimated_cost_calculation():
    """Verify cost calculation per model."""
    cost_gpt4 = calculate_estimated_cost("gpt-4o", prompt_tokens=1000, completion_tokens=1000)
    assert cost_gpt4 == 0.02  # $0.005 + $0.015 = $0.02

    cost_mock = calculate_estimated_cost("mock", prompt_tokens=1000, completion_tokens=1000)
    assert cost_mock == 0.0


def test_llm_agent_executor_structured_output_and_usage_log(app, db_session, test_user):
    """Verify LLMAgentExecutor parses structured output and records LLMUsageLog."""
    with app.app_context():
        agent = create_agent(
            user_id=test_user.id,
            data={
                "name": "Structured Agent",
                "system_instructions": "Return JSON data.",
                "provider": "mock",
                "model": "mock-v1",
            },
        )

        executor = LLMAgentExecutor()
        success, output, err = executor.execute(
            agent=agent,
            instructions="Output JSON summary",
            inputs={"topic": "AI"},
            config={"response_format": "json"},
        )

        assert success is True
        assert isinstance(output, dict)
        assert output.get("status") == "success"

        # Verify usage log entry created in DB
        log = LLMUsageLog.query.filter_by(agent_id=agent.id).first()
        assert log is not None
        assert log.provider == "mock"
        assert log.model == "mock-v1"
        assert log.total_tokens > 0


def test_full_llm_workflow_execution(app, db_session, test_user):
    """Verify workflow execution using production LLMAgentExecutor."""
    with app.app_context():
        agent = create_agent(
            user_id=test_user.id,
            data={
                "name": "LLM Worker Agent",
                "system_instructions": "Process enterprise tasks.",
                "provider": "mock",
                "model": "mock-v1",
            },
        )

        wf = create_workflow(test_user.id, {"name": "LLM Workflow"})
        n1, _ = add_node_to_workflow(
            wf,
            test_user.id,
            {
                "name": "Task 1",
                "agent_id": agent.public_id,
                "output_key": "out1",
                "input_mapping": {"arg1": "$input.query"},
            },
        )

        activate_workflow(wf, test_user.id)

        engine = WorkflowExecutionEngine(agent_executor=LLMAgentExecutor())
        execution, _ = trigger_workflow_execution(wf, test_user.id, input_data={"query": "Automate processes"})

        assert execution.status == EXECUTION_STATUS_COMPLETED
        assert "out1" in execution.output_data

        # Verify usage log linked workflow_execution_id and task_execution_id
        log = LLMUsageLog.query.filter_by(workflow_execution_id=execution.id).first()
        assert log is not None
        assert log.agent_id == agent.id
        assert log.task_execution_id is not None


def test_llm_agent_token_and_cost_budget_enforcement(app, db_session, test_user):
    """Verify that agent token budget and cost budget constraints block execution when exceeded."""
    with app.app_context():
        agent = create_agent(
            user_id=test_user.id,
            data={
                "name": "Budget Constrained Agent",
                "system_instructions": "Perform task.",
                "provider": "mock",
                "model": "mock-v1",
                "token_budget": 50,  # Small token budget
            },
        )

        executor = LLMAgentExecutor()

        # First execution succeeds and records usage
        success1, _, _ = executor.execute(agent=agent, instructions="Run task 1", inputs={}, config={})
        assert success1 is True

        # Artificially update usage log total_tokens to reach/exceed budget
        log = LLMUsageLog.query.filter_by(agent_id=agent.id).first()
        log.total_tokens = 100
        db_session.commit()

        # Second execution must fail due to exceeded budget
        success2, _, err_msg = executor.execute(agent=agent, instructions="Run task 2", inputs={}, config={})
        assert success2 is False
        assert "token budget exceeded" in err_msg

