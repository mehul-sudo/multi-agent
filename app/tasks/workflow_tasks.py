"""
Celery Task Definitions for Distributed Workflow Execution.

Defines bound, reliable Celery tasks with late acknowledgments, crash recovery,
retries with full jitter backoff, scheduled execution, and heartbeats.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from celery import Task
from flask import current_app

from app.celery_app import celery_app
from app.extensions import db
from app.llm.errors import LLMAuthenticationError, LLMConfigurationError, LLMInvalidRequestError
from app.models.async_job import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_CANCEL_REQUESTED,
    JOB_STATUS_DEAD_LETTERED,
    JOB_STATUS_FAILED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_TIMED_OUT,
    AsyncWorkflowJob,
)
from app.models.execution_attempt import ExecutionAttempt
from app.models.workflow_execution import EXECUTION_STATUS_COMPLETED
from app.services.audit_service import log_audit_event
from app.services.execution_engine import LLMAgentExecutor, WorkflowExecutionEngine
from app.services.execution_service import trigger_workflow_execution
from app.services.recovery_service import detect_and_recover_stale_jobs, record_worker_heartbeat
from app.services.schedule_service import process_due_schedules


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@celery_app.task(bind=True, acks_late=True, max_retries=3, name="app.tasks.execute_async_workflow_task")
def execute_async_workflow_task(self: Task, job_id: int) -> Dict[str, Any]:
    """Execute an asynchronous workflow job via Celery worker."""
    start_time = time.time()
    job = db.session.get(AsyncWorkflowJob, job_id)
    if not job:
        return {"status": "error", "message": f"Job ID {job_id} not found."}

    # Handle cancellation if requested prior to worker pickup
    if job.status == JOB_STATUS_CANCEL_REQUESTED:
        job.status = JOB_STATUS_CANCELLED
        job.completed_at = _utcnow()
        db.session.commit()
        log_audit_event(
            event_type="JOB_CANCELLED",
            resource_type="async_job",
            resource_id=job.public_id,
            user_id=job.user_id,
            event_data={"reason": "Cancelled before execution started."},
        )
        return {"status": "cancelled", "job_id": job.public_id}

    # Record execution attempt
    attempt = ExecutionAttempt(
        job_id=job.id,
        celery_task_id=self.request.id or job.celery_task_id,
        attempt_number=job.retry_count + 1,
        worker_id=self.request.hostname or "default_worker",
        status="RUNNING",
        started_at=_utcnow(),
        last_heartbeat_at=_utcnow(),
    )
    db.session.add(attempt)

    # Update job state
    job.status = JOB_STATUS_RUNNING
    job.worker_id = self.request.hostname or "default_worker"
    job.started_at = job.started_at or _utcnow()
    job.last_heartbeat_at = _utcnow()
    job.progress_percentage = 10.0
    db.session.commit()

    log_audit_event(
        event_type="WORKER_STARTED",
        resource_type="async_job",
        resource_id=job.public_id,
        user_id=job.user_id,
        event_data={"worker_id": job.worker_id, "attempt": attempt.attempt_number},
    )

    try:
        # Trigger or load workflow execution
        if job.workflow_execution_id:
            execution = job.workflow_execution
        else:
            execution, _ = trigger_workflow_execution(
                workflow=job.workflow,
                user_id=job.user_id,
                input_data=job.execution_metadata.get("input_data", {}),
            )
            job.workflow_execution_id = execution.id
            db.session.commit()

        # Run DAG execution engine
        engine = WorkflowExecutionEngine(agent_executor=LLMAgentExecutor())
        execution = engine.run_execution(execution.id)

        job.last_heartbeat_at = _utcnow()
        attempt.last_heartbeat_at = _utcnow()
        attempt.finished_at = _utcnow()
        attempt.duration_ms = int((time.time() - start_time) * 1000)

        if execution.status == EXECUTION_STATUS_COMPLETED:
            job.status = JOB_STATUS_SUCCEEDED
            job.progress_percentage = 100.0
            job.completed_at = _utcnow()
            job.result_data = execution.output_data or {}
            attempt.status = "SUCCEEDED"
            db.session.commit()

            log_audit_event(
                event_type="JOB_COMPLETED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=job.user_id,
                event_data={"duration_ms": attempt.duration_ms},
            )
            return {"status": "succeeded", "job_id": job.public_id}
        else:
            # Workflow failure
            job.status = JOB_STATUS_FAILED
            job.error_code = "WORKFLOW_EXECUTION_FAILED"
            job.error_message = execution.failure_reason or "One or more workflow tasks failed."
            job.completed_at = _utcnow()
            attempt.status = "FAILED"
            attempt.error_code = job.error_code
            attempt.failure_category = "WorkflowExecutionError"
            db.session.commit()

            log_audit_event(
                event_type="JOB_FAILED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=job.user_id,
                event_data={"error": job.error_message},
            )
            return {"status": "failed", "job_id": job.public_id, "error": job.error_message}

    except (ValueError, LLMAuthenticationError, LLMConfigurationError, LLMInvalidRequestError) as exc:
        # Non-retryable application/validation errors
        duration = int((time.time() - start_time) * 1000)
        job.status = JOB_STATUS_FAILED
        job.error_code = exc.__class__.__name__
        job.error_message = str(exc)
        job.completed_at = _utcnow()

        attempt.status = "FAILED"
        attempt.finished_at = _utcnow()
        attempt.duration_ms = duration
        attempt.error_code = job.error_code
        attempt.failure_category = exc.__class__.__name__
        db.session.commit()

        log_audit_event(
            event_type="JOB_FAILED",
            resource_type="async_job",
            resource_id=job.public_id,
            user_id=job.user_id,
            event_data={"error": str(exc), "retryable": False},
        )
        return {"status": "failed", "job_id": job.public_id, "error": str(exc)}

    except Exception as exc:
        # Transient worker/network failure - retry with exponential backoff if retry limit allows
        duration = int((time.time() - start_time) * 1000)
        attempt.status = "FAILED"
        attempt.finished_at = _utcnow()
        attempt.duration_ms = duration
        attempt.error_code = "TRANSIENT_ERROR"
        attempt.retry_reason = str(exc)

        if self.request.retries < self.max_retries and job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = "RETRYING"
            db.session.commit()

            # Backoff delay: 2 ** retries + random jitter
            delay = int((2 ** self.request.retries) + (time.time() % 1.5))

            log_audit_event(
                event_type="JOB_RETRIED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=job.user_id,
                event_data={"retry_count": job.retry_count, "error": str(exc)},
            )
            raise self.retry(exc=exc, countdown=delay)
        else:
            job.status = JOB_STATUS_DEAD_LETTERED
            job.error_code = "RETRIES_EXHAUSTED"
            job.error_message = f"Job failed after {job.retry_count} retries: {str(exc)}"
            job.completed_at = _utcnow()
            db.session.commit()

            log_audit_event(
                event_type="JOB_DEAD_LETTERED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=job.user_id,
                event_data={"error": job.error_message},
            )
            return {"status": "dead_lettered", "job_id": job.public_id, "error": job.error_message}

    finally:
        # Always release the SQLAlchemy session back to the pool after task
        # completion, regardless of success/failure/retry.  Without this,
        # long-lived worker processes accumulate idle connections that are
        # never returned to the pool, leading to connection exhaustion.
        db.session.remove()



@celery_app.task(name="app.tasks.check_scheduled_workflows_task")
def check_scheduled_workflows_task() -> Dict[str, Any]:
    """Celery Beat task running every minute to process due workflow schedules."""
    dispatched = process_due_schedules()
    return {"status": "ok", "dispatched_jobs_count": dispatched}


@celery_app.task(name="app.tasks.recover_stale_jobs_task")
def recover_stale_jobs_task() -> Dict[str, Any]:
    """Celery Beat task running periodically to recover stale jobs from crashed workers."""
    result = detect_and_recover_stale_jobs()
    return {"status": "ok", "recovery_stats": result}


@celery_app.task(name="app.tasks.worker_heartbeat_task")
def worker_heartbeat_task(worker_id: str, hostname: str, queues: list, active_tasks: int = 0) -> Dict[str, Any]:
    """Celery task sending worker heartbeat telemetry."""
    record_worker_heartbeat(
        worker_id=worker_id,
        hostname=hostname,
        queues=queues,
        active_tasks_count=active_tasks,
    )
    return {"status": "ok", "worker_id": worker_id}


# Configure Celery Beat schedule defaults
celery_app.conf.beat_schedule = {
    "process-workflow-schedules-every-minute": {
        "task": "app.tasks.check_scheduled_workflows_task",
        "schedule": 60.0,
    },
    "recover-stale-jobs-every-two-minutes": {
        "task": "app.tasks.recover_stale_jobs_task",
        "schedule": 120.0,
    },
}
