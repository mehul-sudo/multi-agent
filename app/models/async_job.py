"""
Async Workflow Job Model.

Tracks persistent state for asynchronous, distributed workflow execution jobs.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db

# Job Status Constants
JOB_STATUS_QUEUED = "QUEUED"
JOB_STATUS_STARTED = "STARTED"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_PAUSED = "PAUSED"
JOB_STATUS_RETRYING = "RETRYING"
JOB_STATUS_SUCCEEDED = "SUCCEEDED"
JOB_STATUS_FAILED = "FAILED"
JOB_STATUS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
JOB_STATUS_CANCELLED = "CANCELLED"
JOB_STATUS_TIMED_OUT = "TIMED_OUT"
JOB_STATUS_RECOVERING = "RECOVERING"
JOB_STATUS_DEAD_LETTERED = "DEAD_LETTERED"

SUPPORTED_JOB_STATUSES = (
    JOB_STATUS_QUEUED,
    JOB_STATUS_STARTED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_PAUSED,
    JOB_STATUS_RETRYING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCEL_REQUESTED,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_TIMED_OUT,
    JOB_STATUS_RECOVERING,
    JOB_STATUS_DEAD_LETTERED,
)

FINAL_JOB_STATUSES = (
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_TIMED_OUT,
    JOB_STATUS_DEAD_LETTERED,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AsyncWorkflowJob(db.Model):
    """Persistent job record for background workflow execution."""

    __tablename__ = "async_workflow_jobs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), index=True, nullable=False)
    workflow_execution_id = db.Column(
        db.Integer, db.ForeignKey("workflow_executions.id", ondelete="SET NULL"), index=True, nullable=True
    )

    celery_task_id = db.Column(db.String(255), index=True, nullable=True)
    job_type = db.Column(db.String(50), nullable=False, default="workflow_execution")

    status = db.Column(db.String(30), index=True, nullable=False, default=JOB_STATUS_QUEUED)
    priority = db.Column(db.Integer, nullable=False, default=0)
    queue_name = db.Column(db.String(50), nullable=False, default="default")

    requested_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    last_heartbeat_at = db.Column(db.DateTime, nullable=True)

    retry_count = db.Column(db.Integer, nullable=False, default=0)
    max_retries = db.Column(db.Integer, nullable=False, default=3)
    progress_percentage = db.Column(db.Float, nullable=False, default=0.0)

    current_node_id = db.Column(db.String(50), nullable=True)
    result_data = db.Column(db.JSON, nullable=True)

    error_code = db.Column(db.String(100), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    failure_category = db.Column(db.String(100), nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)

    idempotency_key = db.Column(db.String(255), index=True, nullable=True)
    correlation_id = db.Column(db.String(255), index=True, nullable=True)
    worker_id = db.Column(db.String(100), nullable=True)

    execution_metadata = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, index=True, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("async_jobs", lazy="dynamic"))
    workflow = db.relationship("Workflow", backref=db.backref("async_jobs", lazy="dynamic"))
    workflow_execution = db.relationship("WorkflowExecution", backref=db.backref("async_jobs", lazy="dynamic"))
    attempts = db.relationship("ExecutionAttempt", backref="job", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AsyncWorkflowJob public_id={self.public_id} status={self.status} priority={self.priority}>"
