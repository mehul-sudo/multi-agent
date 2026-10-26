"""
Execution Attempt Model.

Tracks individual execution attempts made by Celery workers for an AsyncWorkflowJob.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ExecutionAttempt(db.Model):
    """Detailed log for each Celery worker attempt to execute a job."""

    __tablename__ = "execution_attempts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    job_id = db.Column(db.Integer, db.ForeignKey("async_workflow_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    celery_task_id = db.Column(db.String(255), nullable=True)

    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    worker_id = db.Column(db.String(100), nullable=True)

    status = db.Column(db.String(30), nullable=False, default="STARTED")

    started_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    last_heartbeat_at = db.Column(db.DateTime, nullable=True)

    failure_category = db.Column(db.String(100), nullable=True)
    retry_reason = db.Column(db.Text, nullable=True)
    error_code = db.Column(db.String(100), nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    recovery_status = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExecutionAttempt job_id={self.job_id} attempt_number={self.attempt_number} status={self.status}>"
