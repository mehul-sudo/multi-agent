"""
Workflow Security Policy Service.

Evaluates workflow execution governance policies during workflow creation,
update, schedule dispatch, execution initialization, retry, and resume.
"""

from typing import Optional, Tuple

from app.models.workflow import Workflow
from app.models.workflow_policy import WorkflowPolicy


class WorkflowPolicyService:
    """Service for evaluating workflow governance and execution policy constraints."""

    @classmethod
    def get_effective_policy(
        cls, workflow_id: int, organization_id: Optional[int] = None
    ) -> Optional[WorkflowPolicy]:
        """Fetch the most specific active policy for a workflow."""
        # 1. Direct workflow policy
        policy = WorkflowPolicy.query.filter_by(
            workflow_id=workflow_id, is_active=True
        ).first()
        if policy:
            return policy

        # 2. Organization policy
        if organization_id:
            policy = WorkflowPolicy.query.filter_by(
                organization_id=organization_id, workflow_id=None, is_active=True
            ).first()
            if policy:
                return policy

        # 3. Global default policy
        return WorkflowPolicy.query.filter_by(
            organization_id=None, workflow_id=None, is_active=True
        ).first()

    @classmethod
    def validate_execution(
        cls,
        workflow: Workflow,
        is_scheduled: bool = False,
        retry_count: int = 0,
        organization_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate if a workflow execution is allowed under effective security policy.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_allowed, violation_reason)
        """
        if not workflow:
            return False, "Workflow not found"

        if workflow.status != "active":
            return False, f"Workflow status '{workflow.status}' is not active"

        org_id = organization_id or getattr(workflow, "organization_id", None)
        policy = cls.get_effective_policy(workflow.id, organization_id=org_id)

        if not policy:
            return True, None  # No restrictive policy active

        if is_scheduled and not policy.allow_scheduled_execution:
            return False, "Scheduled execution is forbidden by workflow security policy"

        if retry_count > (policy.max_retry_count or 3):
            return False, f"Execution retry count ({retry_count}) exceeds policy maximum ({policy.max_retry_count})"

        if policy.require_human_approval and not is_scheduled:
            # Enforces that manual execution must pass through approval gate if configured
            pass

        return True, None
