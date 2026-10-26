"""
Workflow Execution Service.

High-level service managing execution instantiation, idempotency key checks,
retries, cancellations, and status queries.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.extensions import db
from app.models.task_execution import TASK_STATUS_CANCELLED, TASK_STATUS_FAILED, TaskExecution
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_execution import (
    EXECUTION_STATUS_CANCELLED,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_QUEUED,
    EXECUTION_STATUS_RUNNING,
    WorkflowExecution,
)
from app.services.audit_service import log_audit_event
from app.services.execution_engine import WorkflowExecutionEngine
from app.utils.pagination import paginate_query


def trigger_workflow_execution(
    workflow: Workflow,
    user_id: int,
    input_data: Dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Tuple[WorkflowExecution, bool]:
    """Start or retrieve an execution run for a workflow.

    Enforces:
      - Workflow must be active.
      - Idempotency key uniqueness within workflow/user scope.

    Returns:
        (WorkflowExecution, is_new: bool)
    """
    if workflow.status != WORKFLOW_STATUS_ACTIVE:
        raise ValueError(f"Workflow '{workflow.name}' is in '{workflow.status}' state and cannot be executed. Activate it first.")

    # Handle Idempotency Key check
    if idempotency_key:
        existing = WorkflowExecution.query.filter_by(
            workflow_id=workflow.id,
            user_id=user_id,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return existing, False

    execution = WorkflowExecution(
        workflow_id=workflow.id,
        user_id=user_id,
        triggered_by="manual",
        status=EXECUTION_STATUS_QUEUED,
        input_data=input_data or {},
        idempotency_key=idempotency_key,
    )
    db.session.add(execution)
    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_EXECUTION_STARTED",
        resource_type="execution",
        resource_id=execution.public_id,
        user_id=user_id,
        event_data={"workflow_id": workflow.public_id, "idempotency_key": idempotency_key},
    )

    # Run execution synchronously using execution engine
    engine = WorkflowExecutionEngine()
    engine.run_execution(execution.id)

    db.session.refresh(execution)
    return execution, True


def get_execution_by_public_id(public_id: str, user_id: int | None = None) -> WorkflowExecution | None:
    """Retrieve execution by public_id."""
    query = WorkflowExecution.query.filter_by(public_id=public_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def list_executions(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    workflow_public_id: str | None = None,
) -> dict:
    """List executions owned by user."""
    query = WorkflowExecution.query.filter_by(user_id=user_id)

    if status:
        query = query.filter_by(status=status)

    if workflow_public_id:
        workflow = Workflow.query.filter_by(public_id=workflow_public_id, user_id=user_id).first()
        if workflow:
            query = query.filter_by(workflow_id=workflow.id)
        else:
            query = query.filter(WorkflowExecution.id == -1)  # Empty result set

    query = query.order_by(WorkflowExecution.created_at.desc())
    return paginate_query(query, page=page, page_size=page_size)


def cancel_execution(execution: WorkflowExecution, user_id: int) -> Tuple[WorkflowExecution, bool, Optional[str]]:
    """Cancel a queued or running execution.

    Returns:
        (WorkflowExecution, success: bool, error_msg: str | None)
    """
    if execution.status in (EXECUTION_STATUS_COMPLETED, EXECUTION_STATUS_FAILED, EXECUTION_STATUS_CANCELLED):
        return execution, False, f"Execution is already in terminal state '{execution.status}' and cannot be cancelled."

    execution.status = EXECUTION_STATUS_CANCELLED
    execution.failure_reason = "Cancelled by user."

    # Update non-completed task executions to cancelled
    for te in execution.task_executions:
        if te.status not in ("completed", "failed", "skipped"):
            te.status = TASK_STATUS_CANCELLED

    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_EXECUTION_CANCELLED",
        resource_type="execution",
        resource_id=execution.public_id,
        user_id=user_id,
        event_data={"previous_status": execution.status},
    )

    return execution, True, None


def retry_execution(execution: WorkflowExecution, user_id: int) -> Tuple[WorkflowExecution, bool, Optional[str]]:
    """Retry a failed or partially completed execution safely."""
    if execution.status not in (EXECUTION_STATUS_FAILED, EXECUTION_STATUS_CANCELLED):
        return execution, False, f"Only failed or cancelled executions can be retried. Current status is '{execution.status}'."

    # Re-queue execution
    execution.status = EXECUTION_STATUS_QUEUED
    execution.failure_reason = None
    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_EXECUTION_RETRIED",
        resource_type="execution",
        resource_id=execution.public_id,
        user_id=user_id,
        event_data={},
    )

    engine = WorkflowExecutionEngine()
    engine.run_execution(execution.id)

    db.session.refresh(execution)
    return execution, True, None
