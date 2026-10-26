"""
WorkflowExecutionPlan model.

Represents a compiled multi-stage parallel execution plan for a workflow execution.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkflowExecutionPlan(db.Model):
    """A staged parallel execution plan generated for a workflow execution."""

    __tablename__ = "workflow_execution_plans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    workflow_id = db.Column(
        db.Integer, db.ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    execution_id = db.Column(
        db.Integer, db.ForeignKey("workflow_executions.id", ondelete="CASCADE"), index=True, nullable=True
    )

    # JSON representation of execution stages, e.g. [[node_id1, node_id2], [node_id3]]
    stages = db.Column(db.JSON, nullable=False, default=list)

    # JSON mapping of node_id (or node public_id) -> calculated inherited priority
    node_priorities = db.Column(db.JSON, nullable=False, default=dict)

    # JSON mapping of optional/conditional rules per dependency edge
    dependency_rules = db.Column(db.JSON, nullable=False, default=dict)

    status = db.Column(db.String(20), nullable=False, default="created")

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    workflow = db.relationship("Workflow", backref=db.backref("execution_plans", lazy="dynamic"))
    execution = db.relationship("WorkflowExecution", backref=db.backref("execution_plan", uselist=False))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkflowExecutionPlan public_id={self.public_id} workflow_id={self.workflow_id}>"
