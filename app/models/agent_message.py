"""
AgentMessage model.

Persistent inter-agent communication messages.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db

MESSAGE_TYPE_TASK_REQUEST = "Task Request"
MESSAGE_TYPE_TASK_RESULT = "Task Result"
MESSAGE_TYPE_DELEGATION_REQUEST = "Delegation Request"
MESSAGE_TYPE_DELEGATION_RESPONSE = "Delegation Response"
MESSAGE_TYPE_PROGRESS_UPDATE = "Progress Update"
MESSAGE_TYPE_CLARIFICATION_REQUEST = "Clarification Request"
MESSAGE_TYPE_ERROR_REPORT = "Error Report"
MESSAGE_TYPE_REVIEW_REQUEST = "Review Request"
MESSAGE_TYPE_REVIEW_RESULT = "Review Result"
MESSAGE_TYPE_APPROVAL_REQUEST = "Approval Request"
MESSAGE_TYPE_APPROVAL_RESULT = "Approval Result"
MESSAGE_TYPE_CONFLICT_NOTICE = "Conflict Notice"
MESSAGE_TYPE_REPLANNING_REQUEST = "Replanning Request"
MESSAGE_TYPE_CANCELLATION_NOTICE = "Cancellation Notice"
MESSAGE_TYPE_COMPLETION_NOTICE = "Completion Notice"

SUPPORTED_MESSAGE_TYPES = (
    MESSAGE_TYPE_TASK_REQUEST,
    MESSAGE_TYPE_TASK_RESULT,
    MESSAGE_TYPE_DELEGATION_REQUEST,
    MESSAGE_TYPE_DELEGATION_RESPONSE,
    MESSAGE_TYPE_PROGRESS_UPDATE,
    MESSAGE_TYPE_CLARIFICATION_REQUEST,
    MESSAGE_TYPE_ERROR_REPORT,
    MESSAGE_TYPE_REVIEW_REQUEST,
    MESSAGE_TYPE_REVIEW_RESULT,
    MESSAGE_TYPE_APPROVAL_REQUEST,
    MESSAGE_TYPE_APPROVAL_RESULT,
    MESSAGE_TYPE_CONFLICT_NOTICE,
    MESSAGE_TYPE_REPLANNING_REQUEST,
    MESSAGE_TYPE_CANCELLATION_NOTICE,
    MESSAGE_TYPE_COMPLETION_NOTICE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentMessage(db.Model):
    """An inter-agent message entity."""

    __tablename__ = "agent_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), index=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("orchestration_plans.id"), index=True, nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=True)

    sender_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)
    receiver_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)

    message_type = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(255), nullable=True)

    payload = db.Column(db.JSON, nullable=False, default=dict)
    payload_schema = db.Column(db.JSON, nullable=False, default=dict)

    correlation_id = db.Column(db.String(100), index=True, nullable=False)
    reply_to_message_id = db.Column(db.Integer, db.ForeignKey("agent_messages.id"), nullable=True)

    priority = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="DELIVERED")  # PENDING, DELIVERED, PROCESSED, FAILED, EXPIRED

    delivery_attempts = db.Column(db.Integer, nullable=False, default=1)
    expiry_time = db.Column(db.DateTime, nullable=True)
    idempotency_key = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    sender_agent = db.relationship("Agent", foreign_keys=[sender_agent_id])
    receiver_agent = db.relationship("Agent", foreign_keys=[receiver_agent_id])
    reply_to_message = db.relationship("AgentMessage", remote_side=[id])

    def __repr__(self) -> str:
        return f"<AgentMessage type={self.message_type!r} sender={self.sender_agent_id} -> receiver={self.receiver_agent_id}>"
