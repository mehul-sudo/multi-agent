"""
WorkflowExecution model.

Represents a single execution run of a Workflow.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

EXECUTION_STATUS_QUEUED = "queued"
EXECUTION_STATUS_RUNNING = "running"
EXECUTION_STATUS_PAUSED = "paused"
EXECUTION_STATUS_COMPLETED = "completed"
EXECUTION_STATUS_FAILED = "failed"
EXECUTION_STATUS_CANCELLED = "cancelled"
EXECUTION_STATUS_PARTIALLY_COMPLETED = "partially_completed"

SUPPORTED_EXECUTION_STATUSES = (
    EXECUTION_STATUS_QUEUED,
    EXECUTION_STATUS_RUNNING,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_CANCELLED,
    EXECUTION_STATUS_PARTIALLY_COMPLETED,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkflowExecution(db.Model):
    """An execution run instance of a workflow."""

    __tablename__ = "workflow_executions"
    __table_args__ = (
        CheckConstraint(
            f"status IN {SUPPORTED_EXECUTION_STATUSES}",
            name="ck_workflow_executions_status_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)

    triggered_by = db.Column(db.String(50), nullable=False, default="manual")
    status = db.Column(db.String(30), nullable=False, default=EXECUTION_STATUS_QUEUED)

    input_data = db.Column(db.JSON, nullable=False, default=dict)
    output_data = db.Column(db.JSON, nullable=False, default=dict)
    context_data = db.Column(db.JSON, nullable=False, default=dict)

    idempotency_key = db.Column(db.String(100), index=True, nullable=True)

    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("workflow_executions", lazy="dynamic"))
    task_executions = db.relationship(
        "TaskExecution",
        backref="workflow_execution",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkflowExecution public_id={self.public_id} status={self.status}>"
