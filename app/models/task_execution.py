"""
TaskExecution model.

Represents execution state of a single WorkflowNode during a WorkflowExecution.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

TASK_STATUS_PENDING = "pending"
TASK_STATUS_BLOCKED = "blocked"
TASK_STATUS_READY = "ready"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_RETRYING = "retrying"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_SKIPPED = "skipped"
TASK_STATUS_CANCELLED = "cancelled"

SUPPORTED_TASK_STATUSES = (
    TASK_STATUS_PENDING,
    TASK_STATUS_BLOCKED,
    TASK_STATUS_READY,
    TASK_STATUS_RUNNING,
    TASK_STATUS_RETRYING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_SKIPPED,
    TASK_STATUS_CANCELLED,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TaskExecution(db.Model):
    """An execution run instance of a workflow node."""

    __tablename__ = "task_executions"
    __table_args__ = (
        CheckConstraint(
            f"status IN {SUPPORTED_TASK_STATUSES}",
            name="ck_task_executions_status_valid",
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

    workflow_execution_id = db.Column(
        db.Integer, db.ForeignKey("workflow_executions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workflow_node_id = db.Column(
        db.Integer, db.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), index=True, nullable=True
    )
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=TASK_STATUS_PENDING)
    attempt_number = db.Column(db.Integer, nullable=False, default=0)

    input_data = db.Column(db.JSON, nullable=False, default=dict)
    output_data = db.Column(db.JSON, nullable=False, default=dict)
    error_data = db.Column(db.JSON, nullable=False, default=dict)

    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    workflow_node = db.relationship(
        "WorkflowNode",
        backref=db.backref("task_executions", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic"),
    )
    agent = db.relationship("Agent", backref=db.backref("task_executions", lazy="dynamic"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskExecution public_id={self.public_id} status={self.status}>"
