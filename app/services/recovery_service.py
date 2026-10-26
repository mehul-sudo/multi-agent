"""
Recovery and Worker Monitoring Service.

Detects stale jobs from worker crashes or lost messages, recovers recoverable tasks,
routes exhausted failures to dead-letter storage, and tracks worker heartbeats.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from flask import current_app

from app.extensions import db
from app.models.async_job import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_DEAD_LETTERED,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RECOVERING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_STARTED,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_TIMED_OUT,
    AsyncWorkflowJob,
)
from app.models.worker_health import WorkerHealth
from app.services.audit_service import log_audit_event
from app.utils.queues import ALLOWED_QUEUES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record_worker_heartbeat(
    worker_id: str,
    hostname: str,
    queues: List[str],
    active_tasks_count: int = 0,
    registered_tasks: Optional[List[str]] = None,
    status: str = "online",
    version: str = "1.0.0",
) -> WorkerHealth:
    """Record or update a worker node's heartbeat."""
    worker = WorkerHealth.query.filter_by(worker_id=worker_id).first()
    now = _utcnow()

    if not worker:
        worker = WorkerHealth(
            worker_id=worker_id,
            hostname=hostname,
            queues=queues or ["default"],
            active_tasks_count=active_tasks_count,
            registered_tasks=registered_tasks or [],
            status=status,
            started_at=now,
            last_heartbeat_at=now,
            version=version,
        )
        db.session.add(worker)
    else:
        worker.hostname = hostname
        worker.queues = queues or worker.queues
        worker.active_tasks_count = active_tasks_count
        worker.registered_tasks = registered_tasks or worker.registered_tasks
        worker.status = status
        worker.last_heartbeat_at = now
        worker.version = version

    db.session.commit()
    return worker


def detect_and_recover_stale_jobs(stale_threshold_seconds: Optional[int] = None) -> Dict[str, int]:
    """Identify stale jobs whose worker heartbeats expired, and attempt recovery or dead-lettering."""
    threshold_sec = stale_threshold_seconds or current_app.config.get("STALE_JOB_THRESHOLD_SECONDS", 300)
    cutoff = _utcnow() - timedelta(seconds=threshold_sec)

    stale_jobs = AsyncWorkflowJob.query.filter(
        AsyncWorkflowJob.status.in_([JOB_STATUS_STARTED, JOB_STATUS_RUNNING]),
        db.or_(
            AsyncWorkflowJob.last_heartbeat_at < cutoff,
            db.and_(AsyncWorkflowJob.last_heartbeat_at.is_(None), AsyncWorkflowJob.started_at < cutoff),
        ),
    ).all()

    recovered_count = 0
    dead_lettered_count = 0

    for job in stale_jobs:
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JOB_STATUS_RECOVERING
            job.error_message = f"Stale job detected (no heartbeat for >{threshold_sec}s). Re-queuing recovery attempt {job.retry_count}."
            db.session.commit()

            try:
                from app.tasks.workflow_tasks import execute_async_workflow_task
                task_res = execute_async_workflow_task.apply_async(
                    args=[job.id],
                    queue=job.queue_name,
                    priority=job.priority,
                )
                job.celery_task_id = task_res.id
                job.status = JOB_STATUS_QUEUED
                db.session.commit()
                recovered_count += 1

                log_audit_event(
                    event_type="JOB_RECOVERED",
                    resource_type="async_job",
                    resource_id=job.public_id,
                    user_id=job.user_id,
                    event_data={"attempt": job.retry_count, "celery_task_id": job.celery_task_id},
                )
            except Exception as exc:
                job.status = JOB_STATUS_DEAD_LETTERED
                job.error_code = "RECOVERY_DISPATCH_FAILED"
                job.error_message = f"Failed to re-dispatch stale job: {str(exc)}"
                db.session.commit()
                dead_lettered_count += 1
        else:
            job.status = JOB_STATUS_DEAD_LETTERED
            job.error_code = "STALE_JOB_EXHAUSTED"
            job.error_message = f"Job heartbeats expired after {threshold_sec}s and reached maximum retries ({job.max_retries})."
            db.session.commit()
            dead_lettered_count += 1

            log_audit_event(
                event_type="JOB_DEAD_LETTERED",
                resource_type="async_job",
                resource_id=job.public_id,
                user_id=job.user_id,
                event_data={"reason": job.error_message},
            )

    return {"stale_found": len(stale_jobs), "recovered": recovered_count, "dead_lettered": dead_lettered_count}


def get_monitoring_overview() -> Dict[str, Any]:
    """Retrieve system-wide monitoring metrics for workers, queues, and jobs."""
    cutoff = _utcnow() - timedelta(seconds=120)

    # Workers
    all_workers = WorkerHealth.query.all()
    active_workers = []
    stale_workers_count = 0

    for w in all_workers:
        if w.last_heartbeat_at and w.last_heartbeat_at >= cutoff:
            active_workers.append(w)
        else:
            stale_workers_count += 1
            w.status = "stale"
    db.session.commit()

    # Job counts by status
    active_jobs_count = AsyncWorkflowJob.query.filter(
        AsyncWorkflowJob.status.in_([JOB_STATUS_STARTED, JOB_STATUS_RUNNING, JOB_STATUS_RECOVERING])
    ).count()

    queued_jobs_count = AsyncWorkflowJob.query.filter_by(status=JOB_STATUS_QUEUED).count()
    failed_jobs_count = AsyncWorkflowJob.query.filter_by(status=JOB_STATUS_FAILED).count()
    dead_lettered_jobs_count = AsyncWorkflowJob.query.filter_by(status=JOB_STATUS_DEAD_LETTERED).count()

    # Per-queue stats
    queue_stats = []
    for q_name in sorted(list(ALLOWED_QUEUES)):
        q_jobs = AsyncWorkflowJob.query.filter_by(queue_name=q_name)
        queue_stats.append(
            {
                "queue_name": q_name,
                "active_jobs": q_jobs.filter(
                    AsyncWorkflowJob.status.in_([JOB_STATUS_STARTED, JOB_STATUS_RUNNING])
                ).count(),
                "queued_jobs": q_jobs.filter_by(status=JOB_STATUS_QUEUED).count(),
                "retrying_jobs": q_jobs.filter_by(status=JOB_STATUS_RECOVERING).count(),
                "failed_jobs": q_jobs.filter_by(status=JOB_STATUS_FAILED).count(),
                "completed_jobs": q_jobs.filter_by(status=JOB_STATUS_SUCCEEDED).count(),
            }
        )

    return {
        "total_active_workers": len(active_workers),
        "stale_workers_count": stale_workers_count,
        "active_jobs_count": active_jobs_count,
        "queued_jobs_count": queued_jobs_count,
        "failed_jobs_count": failed_jobs_count,
        "dead_lettered_jobs_count": dead_lettered_jobs_count,
        "workers": active_workers,
        "queues": queue_stats,
    }
