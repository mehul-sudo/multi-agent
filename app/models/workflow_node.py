"""
WorkflowNode model.

Represents a unit of work assigned to an Agent or system action within a Workflow.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkflowNode(db.Model):
    """A task node inside a workflow DAG."""

    __tablename__ = "workflow_nodes"

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
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)

    name = db.Column(db.String(100), nullable=False)
    task_type = db.Column(db.String(50), nullable=False, default="agent_task")

    instructions = db.Column(db.Text, nullable=True)

    input_mapping = db.Column(db.JSON, nullable=False, default=dict)
    output_key = db.Column(db.String(100), nullable=True)
    configuration = db.Column(db.JSON, nullable=False, default=dict)

    timeout_seconds = db.Column(db.Integer, nullable=False, default=300)
    retry_limit = db.Column(db.Integer, nullable=False, default=3)
    priority = db.Column(db.Integer, nullable=False, default=0)

    position = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    agent = db.relationship("Agent", backref=db.backref("nodes", lazy="dynamic"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkflowNode public_id={self.public_id} name={self.name!r}>"
