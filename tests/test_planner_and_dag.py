"""
Tests for Planner Agent, DAG Validation, and Replanning.
"""

import pytest

from app.extensions import db
from app.models.orchestration_plan import OrchestrationPlan, PlanTask, TaskDependency
from app.models.orchestration_session import OrchestrationSession
from app.services.planner_service import PlanValidationError, generate_orchestration_plan, replan_orchestration, validate_plan_dag


def test_plan_generation_and_dag_validation(app, test_user):
    """Test generating a multi-step orchestration plan and validating DAG structure."""
    with app.app_context():
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Perform enterprise market research.",
        )
        db.session.add(session)
        db.session.flush()

        plan = generate_orchestration_plan(session)
        assert plan is not None
        assert plan.tasks.count() == 3
        assert plan.validation_status == "VALIDATED"


def test_circular_dependency_rejection(app, test_user):
    """Test that circular task dependencies in a plan trigger validation error."""
    with app.app_context():
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Circular test objective.",
        )
        db.session.add(session)
        db.session.flush()

        plan = OrchestrationPlan(orchestration_id=session.id, version=1, objective=session.objective)
        db.session.add(plan)
        db.session.flush()

        t1 = PlanTask(plan_id=plan.id, task_key="t1", name="Task 1")
        t2 = PlanTask(plan_id=plan.id, task_key="t2", name="Task 2")
        db.session.add_all([t1, t2])
        db.session.flush()

        # Create cycle: t1 -> t2 and t2 -> t1
        dep1 = TaskDependency(plan_id=plan.id, parent_task_id=t1.id, child_task_id=t2.id)
        dep2 = TaskDependency(plan_id=plan.id, parent_task_id=t2.id, child_task_id=t1.id)
        db.session.add_all([dep1, dep2])
        db.session.flush()

        with pytest.raises(PlanValidationError) as excinfo:
            validate_plan_dag(plan)
        assert "Circular dependency detected" in str(excinfo.value)
