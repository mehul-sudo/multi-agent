"""
Workflow model.

Represents an automation workflow definition comprising nodes and dependencies.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

WORKFLOW_STATUS_DRAFT = "draft"
WORKFLOW_STATUS_ACTIVE = "active"
WORKFLOW_STATUS_ARCHIVED = "archived"
WORKFLOW_STATUS_DISABLED = "disabled"
SUPPORTED_WORKFLOW_STATUSES = (
    WORKFLOW_STATUS_DRAFT,
    WORKFLOW_STATUS_ACTIVE,
    WORKFLOW_STATUS_ARCHIVED,
    WORKFLOW_STATUS_DISABLED,
)


def _utcnow() -> datetime:
    """Return naive UTC datetime for storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Workflow(db.Model):
    """A multi-agent workflow definition."""

    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint(
            f"status IN {SUPPORTED_WORKFLOW_STATUSES}",
            name="ck_workflows_status_valid",
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

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), index=True, nullable=True)

    name = db.Column(db.String(100), nullable=False)

    description = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=WORKFLOW_STATUS_DRAFT)

    version = db.Column(db.Integer, nullable=False, default=1)
    priority = db.Column(db.Integer, nullable=False, default=1)

    input_schema = db.Column(db.JSON, nullable=False, default=dict)
    output_schema = db.Column(db.JSON, nullable=False, default=dict)

    # Use workflow_metadata attribute to avoid collision with SQLAlchemy's MetaData
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("workflows", lazy="dynamic"))
    nodes = db.relationship(
        "WorkflowNode",
        backref="workflow",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    dependencies = db.relationship(
        "WorkflowDependency",
        backref="workflow",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    executions = db.relationship(
        "WorkflowExecution",
        backref="workflow",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Workflow public_id={self.public_id} name={self.name!r} status={self.status}>"
