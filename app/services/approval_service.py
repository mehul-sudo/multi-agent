"""
ApprovalService.

Creates human-in-the-loop approval checkpoint requests, pauses execution branches,
and handles approval or rejection decisions for both Orchestrations and Workflows.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.approval_request import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REJECTED,
    ApprovalRequest,
)
from app.models.orchestration_plan import PLAN_TASK_STATUS_AWAITING_APPROVAL, PlanTask
from app.models.orchestration_session import ORCHESTRATION_STATUS_AWAITING_APPROVAL, OrchestrationSession
from app.models.task_execution import TASK_STATUS_BLOCKED, TASK_STATUS_FAILED, TaskExecution
from app.models.workflow_execution import (
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_PAUSED,
    WorkflowExecution,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_self_approval_allowed_in_current_env() -> bool:
    """Check if self-approval is permitted by development configuration.

    Production always forbids self-approval regardless of environment variables.
    Testing mode strictly forbids self-approval by default unless explicitly configured.
    Development mode allows self-approval so local developers can test single-user workflows.
    """
    try:
        from flask import current_app
        if current_app:
            if current_app.config.get("TESTING"):
                return bool(current_app.config.get("ALLOW_SELF_APPROVAL_IN_TESTING", False))
            if current_app.config.get("ENV") == "production":
                return False
    except Exception:
        pass

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    env_name = os.environ.get("FLASK_ENV", "development").lower()
    if env_name == "production":
        return False

    # Development mode: permit self-approval (controlled by ALLOW_SELF_APPROVAL_IN_DEVELOPMENT, default true)
    flag = os.environ.get("ALLOW_SELF_APPROVAL_IN_DEVELOPMENT", "true").lower()
    return flag in ("true", "1", "yes")



def create_approval_request(
    orchestration: Optional[OrchestrationSession] = None,
    requested_action: str = "",
    explanation: str = "",
    task: Optional[PlanTask] = None,
    workflow_execution: Optional[WorkflowExecution] = None,
    task_execution: Optional[TaskExecution] = None,
    risk_level: str = "medium",
    input_summary: Optional[Dict[str, Any]] = None,
    proposed_output: Optional[Dict[str, Any]] = None,
    requested_by_agent_id: Optional[int] = None,
    assigned_approver_user_id: Optional[int] = None,
) -> ApprovalRequest:
    """Create a human approval request and pause orchestration or workflow execution branch."""
    # Prevent duplicate pending approval requests for the same plan task or workflow task
    if task and orchestration:
        existing = ApprovalRequest.query.filter_by(
            orchestration_id=orchestration.id,
            task_id=task.id,
            status=APPROVAL_STATUS_PENDING,
        ).first()
        if existing:
            return existing

    if task_execution:
        existing = ApprovalRequest.query.filter_by(
            task_execution_id=task_execution.id,
            status=APPROVAL_STATUS_PENDING,
        ).first()
        if existing:
            return existing

    org_id = "default_org"
    approver_id = assigned_approver_user_id

    if orchestration:
        org_id = orchestration.organization_id or "default_org"
        approver_id = approver_id or orchestration.user_id
    elif workflow_execution:
        approver_id = approver_id or workflow_execution.user_id

    req = ApprovalRequest(
        organization_id=org_id,
        orchestration_id=orchestration.id if orchestration else None,
        task_id=task.id if task else None,
        workflow_execution_id=workflow_execution.id if workflow_execution else None,
        task_execution_id=task_execution.id if task_execution else None,
        requested_action=requested_action,
        risk_level=risk_level,
        explanation=explanation,
        input_summary=input_summary or {},
        proposed_output=proposed_output or {},
        requested_by_agent_id=requested_by_agent_id,
        assigned_approver_user_id=approver_id,
        status=APPROVAL_STATUS_PENDING,
    )
    db.session.add(req)

    # Update states for OrchestrationSession
    if orchestration:
        orchestration.status = ORCHESTRATION_STATUS_AWAITING_APPROVAL
        orchestration.requires_approval = True
        orchestration.approval_status = APPROVAL_STATUS_PENDING
        if task:
            task.status = PLAN_TASK_STATUS_AWAITING_APPROVAL

    # Update states for WorkflowExecution
    if workflow_execution:
        workflow_execution.status = EXECUTION_STATUS_PAUSED
        if task_execution:
            task_execution.status = TASK_STATUS_BLOCKED

    db.session.commit()
    return req


def resolve_approval_request(
    approval_id: int,
    user_id: Optional[int] = None,
    approve: Optional[bool] = None,
    comments: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    prevent_self_approval: bool = True,
    *,
    approved: Optional[bool] = None,
    resolved_by_user_id: Optional[int] = None,
    decision_reason: Optional[str] = None,
    engine: Optional[Any] = None,
) -> ApprovalRequest:
    """Approve or reject a pending approval request with expiry and self-approval checks.

    Self-approval is forbidden in production. In development/testing, it is controlled
    by ALLOW_SELF_APPROVAL_IN_DEVELOPMENT (defaults to True in dev).
    """
    if approved is not None and approve is None:
        approve = approved
    if approve is None:
        approve = True

    if resolved_by_user_id is not None and user_id is None:
        user_id = resolved_by_user_id
    if user_id is None:
        user_id = 1

    if decision_reason:
        if approve:
            comments = comments or decision_reason
        else:
            rejection_reason = rejection_reason or decision_reason

    req = db.session.get(ApprovalRequest, approval_id)
    if not req:
        raise ValueError(f"Approval request {approval_id} not found.")

    # Expiry check
    if req.expiry_time and req.expiry_time < _utcnow():
        req.status = "EXPIRED"
        db.session.commit()
        raise ValueError(f"Approval request {approval_id} has expired.")

    if req.status != APPROVAL_STATUS_PENDING:
        raise ValueError(f"Approval request {approval_id} is already in '{req.status}' state.")

    orchestration = db.session.get(OrchestrationSession, req.orchestration_id) if req.orchestration_id else None
    workflow_exec = db.session.get(WorkflowExecution, req.workflow_execution_id) if req.workflow_execution_id else None

    # Self-approval security enforcement
    allow_dev_self_approval = is_self_approval_allowed_in_current_env()
    requester_user_id = None
    if orchestration:
        requester_user_id = orchestration.user_id
    elif workflow_exec:
        requester_user_id = workflow_exec.user_id

    if prevent_self_approval and not allow_dev_self_approval and requester_user_id == user_id:
        raise ValueError(
            "Self-approval is forbidden by security policy. Requester cannot approve their own request."
        )

    if approve:
        req.status = APPROVAL_STATUS_APPROVED
        req.approval_comments = comments
        req.resolved_by_user_id = user_id
        req.resolved_at = _utcnow()

        if orchestration:
            orchestration.approval_status = APPROVAL_STATUS_APPROVED
            orchestration.status = "READY"

        if req.task_id:
            task = db.session.get(PlanTask, req.task_id)
            if task:
                task.status = "READY"

        db.session.commit()

        # If this approval request was created from an OrchestrationSession, resume orchestration!
        if orchestration and req.orchestration_id:
            try:
                from app.services.supervisor_service import SupervisorService
                supervisor = SupervisorService()
                supervisor.run_orchestration(orchestration.id)
            except Exception:
                pass

        # If this approval request was created from a WorkflowExecution, resume the workflow now!
        if req.workflow_execution_id and req.task_execution_id:
            from app.services.execution_engine import WorkflowExecutionEngine

            eng = engine or WorkflowExecutionEngine()
            eng.resume_execution_after_approval(
                execution_id=req.workflow_execution_id,
                task_execution_id=req.task_execution_id,
                approval=req,
            )

        # If this is a standalone agent approval request (from Agents Studio or Messaging Workspace)
        if not req.orchestration_id and not req.workflow_execution_id:
            try:
                agent_type = None
                if req.requested_by_agent:
                    agent_type = req.requested_by_agent.agent_type
                if not agent_type:
                    action_lower = (req.requested_action or "").lower()
                    for known in ("email", "http_webhook", "database_bi", "data_analysis", "document_research", "report_generation", "security_analysis"):
                        if known in action_lower:
                            agent_type = known
                            break
                if not agent_type and isinstance(req.input_summary, dict):
                    agent_type = req.input_summary.get("agent_type") or req.input_summary.get("type")

                if agent_type:
                    from app.agents import get_agent_instance, AgentContext
                    domain_agent = get_agent_instance(agent_type)
                    if domain_agent:
                        input_payload = dict(req.input_summary or {})
                        if agent_type == "email":
                            input_payload["mode"] = "send"

                        ctx = AgentContext(
                            user_id=req.assigned_approver_user_id or user_id or 1,
                            input_data=input_payload,
                            metadata={
                                "_backend_approval_verified": True,
                                "approval_granted": True,
                                "approval_id": req.id,
                            }
                        )
                        res = domain_agent.execute(ctx)
                        res_dict = res.to_dict()
                        if res_dict.get("output"):
                            req.proposed_output = res_dict["output"]
                        elif res_dict.get("error"):
                            req.proposed_output = {"error": res_dict["error"], "status": "failed"}
                        db.session.commit()
            except Exception:
                pass

    else:
        req.status = APPROVAL_STATUS_REJECTED
        req.rejection_reason = rejection_reason or "Rejected by user."
        req.resolved_by_user_id = user_id
        req.resolved_at = _utcnow()

        if orchestration:
            orchestration.approval_status = APPROVAL_STATUS_REJECTED
            orchestration.status = "REPLANNING"

        if req.task_id:
            task = db.session.get(PlanTask, req.task_id)
            if task:
                task.status = "FAILED"
                task.error_message = req.rejection_reason

        if req.workflow_execution_id and req.task_execution_id:
            task_exec = db.session.get(TaskExecution, req.task_execution_id)
            if task_exec:
                task_exec.status = TASK_STATUS_FAILED
                task_exec.error_data = {"error": req.rejection_reason, "rejected": True}
                task_exec.completed_at = _utcnow()
            db.session.commit()

            from app.services.execution_engine import WorkflowExecutionEngine
            eng = engine or WorkflowExecutionEngine()
            try:
                eng.resume_execution_after_rejection(
                    execution_id=req.workflow_execution_id,
                    task_execution_id=req.task_execution_id,
                    rejection_reason=req.rejection_reason,
                )
            except Exception:
                pass

        db.session.commit()

    return req
