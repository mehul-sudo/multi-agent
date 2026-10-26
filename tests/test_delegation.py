"""
Tests for Governed Task Delegation and Loop Prevention.
"""

import pytest

from app.extensions import db
from app.models.agent import Agent
from app.models.orchestration_plan import OrchestrationPlan, PlanTask
from app.models.orchestration_session import OrchestrationSession
from app.services.delegation_service import DelegationDepthExceededError, DelegationLoopError, delegate_subtask


def test_delegation_depth_limit(app, test_user):
    """Test enforcing maximum delegation depth limit."""
    with app.app_context():
        agent = Agent(user_id=test_user.id, name="Parent Agent", system_instructions="Parent", max_delegation_depth=1)
        db.session.add(agent)
        db.session.flush()

        session = OrchestrationSession(user_id=test_user.id, objective="Delegation depth test.")
        db.session.add(session)
        db.session.flush()

        plan = OrchestrationPlan(orchestration_id=session.id, objective="Plan")
        db.session.add(plan)
        db.session.flush()

        task = PlanTask(plan_id=plan.id, task_key="parent_task", name="Parent Task", delegation_depth=1)
        db.session.add(task)
        db.session.flush()

        # Depth 1 + 1 = 2 > max_delegation_depth (1) -> Error
        with pytest.raises(DelegationDepthExceededError):
            delegate_subtask(
                orchestration_id=session.id,
                parent_task=task,
                parent_agent=agent,
                requested_capability="web_research",
                subtask_name="Subtask",
                subtask_input={},
                delegation_reason="Depth test",
            )
