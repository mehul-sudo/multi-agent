"""
Async Job Service.

Handles database transactions, idempotency deduplication, concurrency guards,
Celery task dispatching, cancellation, and retry policies for AsyncWorkflowJobs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import current_app
from sqlalchemy import or_

from app.celery_app import celery_app
from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE
from app.models.async_job import (
    FINAL_JOB_STATUSES,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_CANCEL_REQUESTED,
    JOB_STATUS_DEAD_LETTERED,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_STARTED,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_TIMED_OUT,
    AsyncWorkflowJob,
)
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.services.audit_service import log_audit_event
from app.services.llm_usage_service import check_agent_budget
from app.utils.errors import ResourceNotFoundError
from app.utils.pagination import paginate_query
from app.utils.queues import validate_queue_name


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def submit_async_job(
    user_id: int,
    workflow_public_id: str,
    data: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> Tuple[AsyncWorkflowJob, bool]:
    """Submit an asynchronous workflow job.

    Returns:
        (AsyncWorkflowJob, is_existing: bool)
    """
    workflow = Workflow.query.filter_by(public_id=workflow_public_id, user_id=user_id).first()
    if not workflow:
        raise ResourceNotFoundError(f"Workflow '{workflow_public_id}' not found or access denied.")

    if workflow.status != WORKFLOW_STATUS_ACTIVE:
        raise ValueError(f"Workflow '{workflow.name}' is {workflow.status} and cannot be executed.")

    idempotency_key = data.get("idempotency_key")
    if idempotency_key:
        existing_job = AsyncWorkflowJob.query.filter_by(
            user_id=user_id,
            workflow_id=workflow.id,
            idempotency_key=idempotency_key,
        ).first()

        if existing_job:
            log_audit_event(
                event_type="JOB_DEDUPLICATED",
                resource_type="async_job",
                resource_id=existing_job.public_id,
                user_id=user_id,
                event_data={"idempotency_key": idempotency_key},
            )
            return existing_job, True

    # Validate requested queue name
    queue_name = validate_queue_name(data.get("queue_name", "default"))
    priority = data.get("priority", 0)

    # Concurrency limit enforcement
    max_user_jobs = current_app.config.get("MAX_USER_CONCURRENT_JOBS", 10)
    user_active_jobs_count = AsyncWorkflowJob.query.filter(
        AsyncWorkflowJob.user_id == user_id,
        AsyncWorkflowJob.status.in_([JOB_STATUS_QUEUED, JOB_STATUS_STARTED, JOB_STATUS_RUNNING]),
    ).count()

    if user_active_jobs_count >= max_user_jobs:
        raise ValueError(
            f"User maximum active job limit ({max_user_jobs}) reached. Please wait for existing jobs to complete."
        )

    max_wf_jobs = current_app.config.get("MAX_WORKFLOW_CONCURRENT_JOBS", 5)
    wf_active_jobs_count = AsyncWorkflowJob.query.filter(
        AsyncWorkflowJob.workflow_id == workflow.id,
        AsyncWorkflowJob.status.in_([JOB_STATUS_QUEUED, JOB_STATUS_STARTED, JOB_STATUS_RUNNING]),
    ).count()

    if wf_active_jobs_count >= max_wf_jobs:
        raise ValueError(
            f"Workflow maximum concurrent job limit ({max_wf_jobs}) reached for workflow '{workflow.name}'."
        )

    wf_public_id = workflow.public_id

    # LLM budget checks for agents bound to workflow nodes
    for node in workflow.nodes:
        if node.agent:
            budget_err = check_agent_budget(node.agent)
            if budget_err:
                raise ValueError(f"Job rejected: {budget_err}")

    job = AsyncWorkflowJob(
        user_id=user_id,
        workflow_id=workflow.id,
        status=JOB_STATUS_QUEUED,
        priority=priority,
        queue_name=queue_name,
        requested_at=_utcnow(),
        retry_count=0,
        max_retries=data.get("max_retries", 3),
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        execution_metadata=data.get("metadata", {}),
    )

    db.session.add(job)
    db.session.commit()

    # Dispatch Celery task
    try:
        from app.tasks.workflow_tasks import execute_async_workflow_task
        task_res = execute_async_workflow_task.apply_async(
            args=[job.id],
            queue=queue_name,
            priority=priority,
        )
        job.celery_task_id = task_res.id
        db.session.commit()
    except Exception as exc:
        # If Celery dispatch fails, mark job failed
        job.status = JOB_STATUS_FAILED
        job.error_code = "DISPATCH_ERROR"
        job.error_message = f"Failed to dispatch task to message broker: {str(exc)}"
        db.session.commit()
        raise RuntimeError(job.error_message) from exc

    log_audit_event(
        event_type="JOB_SUBMITTED",
        resource_type="async_job",
        resource_id=job.public_id,
        user_id=user_id,
        event_data={
            "workflow_id": wf_public_id,
            "celery_task_id": job.celery_task_id,
            "queue_name": queue_name,
            "priority": priority,
        },
    )

    return job, False


def get_job_by_public_id(public_id: str, user_id: Optional[int] = None) -> Optional[AsyncWorkflowJob]:
    """Retrieve an AsyncWorkflowJob by its public_id."""
    query = AsyncWorkflowJob.query.filter_by(public_id=public_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def list_jobs(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    workflow_public_id: Optional[str] = None,
) -> dict:
    """List jobs owned by a user with filtering and pagination."""
    query = AsyncWorkflowJob.query.filter_by(user_id=user_id)

    if status:
        query = query.filter_by(status=status)

    if workflow_public_id:
        wf = Workflow.query.filter_by(public_id=workflow_public_id, user_id=user_id).first()
        if wf:
            query = query.filter_by(workflow_id=wf.id)
        else:
            query = query.filter(AsyncWorkflowJob.id == -1)

    query = query.order_by(AsyncWorkflowJob.created_at.desc())
    return paginate_query(query, page=page, page_size=page_size)


def cancel_job(job: AsyncWorkflowJob, user_id: int, reason: str = "Cancelled by user.") -> AsyncWorkflowJob:
    """Cancel an active or queued asynchronous job safely."""
    if job.status in FINAL_JOB_STATUSES:
        raise ValueError(f"Job is in state '{job.status}' and cannot be cancelled.")

    job.status = JOB_STATUS_CANCEL_REQUESTED
    job.cancellation_reason = reason
    job.cancelled_at = _utcnow()
    db.session.commit()

    if job.celery_task_id:
        try:
            celery_app.control.revoke(job.celery_task_id, terminate=True)
            log_audit_event(
                event_type="JOB_CELERY_REVOKED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=user_id,
                event_data={
                    "celery_task_id": job.celery_task_id,
                    "revocation": "success",
                },
            )
        except Exception as revoke_err:
            # Revocation is best-effort: the worker may already have finished or
            # the broker may be unreachable.  Log the failure so operators can
            # investigate, but do NOT abort the cancellation — the job status
            # has already been set to CANCEL_REQUESTED and will be honoured by
            # the worker's own cancellation check.
            log_audit_event(
                event_type="JOB_CELERY_REVOKE_FAILED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=user_id,
                event_data={
                    "celery_task_id": job.celery_task_id,
                    "error": str(revoke_err),
                    "revocation": "failed",
                },
            )

    job.status = JOB_STATUS_CANCELLED
    db.session.commit()

    log_audit_event(
        event_type="JOB_CANCELLED",
        resource_type="async_job",
        resource_id=job.public_id,
        user_id=user_id,
        event_data={"reason": reason, "celery_task_id": job.celery_task_id},
    )

    return job


def retry_job(
    job: AsyncWorkflowJob,
    user_id: int,
    reason: str = "Retried by user.",
    priority_override: Optional[int] = None,
) -> AsyncWorkflowJob:
    """Retry a failed or cancelled asynchronous job."""
    if job.status not in (JOB_STATUS_FAILED, JOB_STATUS_TIMED_OUT, JOB_STATUS_CANCELLED, JOB_STATUS_DEAD_LETTERED):
        raise ValueError(f"Cannot retry job in state '{job.status}'. Only failed, cancelled, or timed-out jobs can be retried.")

    if job.retry_count >= job.max_retries:
        raise ValueError(f"Maximum retry limit ({job.max_retries}) reached for this job.")

    job.retry_count += 1
    job.status = JOB_STATUS_QUEUED
    job.error_code = None
    job.error_message = None
    job.failure_category = None

    if priority_override is not None:
        job.priority = priority_override

    db.session.commit()

    try:
        from app.tasks.workflow_tasks import execute_async_workflow_task
        task_res = execute_async_workflow_task.apply_async(
            args=[job.id],
            queue=job.queue_name,
            priority=job.priority,
        )
        job.celery_task_id = task_res.id
        db.session.commit()
    except Exception as exc:
        job.status = JOB_STATUS_FAILED
        job.error_code = "DISPATCH_ERROR"
        job.error_message = f"Failed to re-dispatch task: {str(exc)}"
        db.session.commit()
        raise RuntimeError(job.error_message) from exc

    log_audit_event(
        event_type="JOB_RETRIED",
        resource_type="async_job",
        resource_id=job.public_id,
        user_id=user_id,
        event_data={"retry_count": job.retry_count, "reason": reason},
    )

    return job
