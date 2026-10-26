"""
ApprovalRequest model.

Tracks human approval checkpoints and decisions.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db

APPROVAL_STATUS_PENDING = "PENDING"
APPROVAL_STATUS_APPROVED = "APPROVED"
APPROVAL_STATUS_REJECTED = "REJECTED"
APPROVAL_STATUS_EXPIRED = "EXPIRED"
APPROVAL_STATUS_CANCELLED = "CANCELLED"
APPROVAL_STATUS_ESCALATED = "ESCALATED"

SUPPORTED_APPROVAL_STATUSES = (
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_EXPIRED,
    APPROVAL_STATUS_CANCELLED,
    APPROVAL_STATUS_ESCALATED,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ApprovalRequest(db.Model):
    """A human-in-the-loop approval request."""

    __tablename__ = "approval_requests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    organization_id = db.Column(db.String(100), index=True, nullable=True, default="default_org")
    orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), index=True, nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=True)
    workflow_execution_id = db.Column(db.Integer, db.ForeignKey("workflow_executions.id", ondelete="CASCADE"), index=True, nullable=True)
    task_execution_id = db.Column(db.Integer, db.ForeignKey("task_executions.id", ondelete="CASCADE"), index=True, nullable=True)

    requested_action = db.Column(db.String(150), nullable=False)
    risk_level = db.Column(db.String(20), nullable=False, default="medium")  # low, medium, high, critical

    explanation = db.Column(db.Text, nullable=False)
    input_summary = db.Column(db.JSON, nullable=False, default=dict)
    proposed_output = db.Column(db.JSON, nullable=False, default=dict)

    requested_by_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), nullable=True)
    assigned_approver_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    status = db.Column(db.String(20), nullable=False, default=APPROVAL_STATUS_PENDING)
    expiry_time = db.Column(db.DateTime, nullable=True)

    approval_comments = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    requested_by_agent = db.relationship("Agent", foreign_keys=[requested_by_agent_id])
    assigned_approver = db.relationship("User", foreign_keys=[assigned_approver_user_id])
    resolved_by_user = db.relationship("User", foreign_keys=[resolved_by_user_id])
    workflow_execution = db.relationship("WorkflowExecution", foreign_keys=[workflow_execution_id], backref=db.backref("approval_requests", lazy="dynamic"))
    task_execution = db.relationship("TaskExecution", foreign_keys=[task_execution_id], backref=db.backref("approval_requests", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<ApprovalRequest public_id={self.public_id} status={self.status}>"

