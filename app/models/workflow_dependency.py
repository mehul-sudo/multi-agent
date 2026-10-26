"""
WorkflowDependency model.

Represents a directed dependency edge between two WorkflowNodes.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.extensions import db

DEPENDENCY_TYPE_ON_SUCCESS = "on_success"
DEPENDENCY_TYPE_ON_FAILURE = "on_failure"
DEPENDENCY_TYPE_ALWAYS = "always"
SUPPORTED_DEPENDENCY_TYPES = (
    DEPENDENCY_TYPE_ON_SUCCESS,
    DEPENDENCY_TYPE_ON_FAILURE,
    DEPENDENCY_TYPE_ALWAYS,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkflowDependency(db.Model):
    """A dependency edge connecting a source node to a target node."""

    __tablename__ = "workflow_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "source_node_id",
            "target_node_id",
            name="uq_workflow_dependencies_source_target",
        ),
        CheckConstraint(
            "source_node_id != target_node_id",
            name="ck_workflow_dependencies_no_self_loop",
        ),
        CheckConstraint(
            f"dependency_type IN {SUPPORTED_DEPENDENCY_TYPES}",
            name="ck_workflow_dependencies_type_valid",
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

    workflow_id = db.Column(
        db.Integer, db.ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_node_id = db.Column(
        db.Integer, db.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_node_id = db.Column(
        db.Integer, db.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    dependency_type = db.Column(
        db.String(50), nullable=False, default=DEPENDENCY_TYPE_ON_SUCCESS
    )
    is_optional = db.Column(db.Boolean, nullable=False, default=False)
    condition = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    source_node = db.relationship("WorkflowNode", foreign_keys=[source_node_id], backref="outgoing_dependencies")
    target_node = db.relationship("WorkflowNode", foreign_keys=[target_node_id], backref="incoming_dependencies")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkflowDependency source={self.source_node_id} -> target={self.target_node_id}>"
