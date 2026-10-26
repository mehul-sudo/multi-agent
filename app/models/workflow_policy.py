"""
Workflow Security Policy model.

Defines governance rules for workflow execution limits, approval requirements,
allowed tools, maximum retry counts, token budgets, and execution windows.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkflowPolicy(db.Model):
    """Workflow-level or organization-wide security governance policy."""

    __tablename__ = "workflow_policies"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Scoping
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True
    )
    workflow_id = db.Column(
        db.Integer, db.ForeignKey("workflows.id"), nullable=True, index=True
    )
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Execution limits & controls
    max_duration_seconds = db.Column(db.Integer, nullable=True, default=3600)
    max_retry_count = db.Column(db.Integer, nullable=True, default=3)
    max_parallelism = db.Column(db.Integer, nullable=True, default=5)
    token_budget = db.Column(db.Integer, nullable=True, default=100000)

    # Security flags
    require_human_approval = db.Column(db.Boolean, nullable=False, default=False)
    allow_external_side_effects = db.Column(db.Boolean, nullable=False, default=True)
    allow_scheduled_execution = db.Column(db.Boolean, nullable=False, default=True)
    allow_automatic_execution = db.Column(db.Boolean, nullable=False, default=True)

    # Restrictions lists (JSON serialized lists)
    allowed_tools = db.Column(db.JSON, nullable=True)  # None means all allowed
    denied_tools = db.Column(db.JSON, nullable=True)
    allowed_agent_ids = db.Column(db.JSON, nullable=True)  # None means all allowed

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<WorkflowPolicy public_id={self.public_id} name={self.name!r}>"
