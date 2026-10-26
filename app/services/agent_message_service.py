"""
AgentMessageService.

Handles structured inter-agent communication, validation, delivery status,
and correlation ID tracking.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.agent_message import AgentMessage
from app.services.secret_service import redact_secrets


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def send_agent_message(
    orchestration_id: int,
    sender_agent_id: Optional[int],
    receiver_agent_id: Optional[int],
    message_type: str,
    subject: str,
    payload: Dict[str, Any],
    correlation_id: str,
    plan_id: Optional[int] = None,
    task_id: Optional[int] = None,
    reply_to_message_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> AgentMessage:
    """Send and record an inter-agent message."""
    if idempotency_key:
        existing = AgentMessage.query.filter_by(
            orchestration_id=orchestration_id,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return existing

    clean_payload = redact_secrets(payload)

    msg = AgentMessage(
        orchestration_id=orchestration_id,
        plan_id=plan_id,
        task_id=task_id,
        sender_agent_id=sender_agent_id,
        receiver_agent_id=receiver_agent_id,
        message_type=message_type,
        subject=subject,
        payload=clean_payload,
        correlation_id=correlation_id,
        reply_to_message_id=reply_to_message_id,
        idempotency_key=idempotency_key,
        status="DELIVERED",
        processed_at=_utcnow(),
    )
    db.session.add(msg)
    db.session.commit()
    return msg


def get_orchestration_messages(orchestration_id: int) -> List[AgentMessage]:
    """Retrieve message history for an orchestration session."""
    return AgentMessage.query.filter_by(orchestration_id=orchestration_id).order_by(AgentMessage.created_at.asc()).all()


def get_task_messages(task_id: int) -> List[AgentMessage]:
    """Retrieve messages associated with a specific task."""
    return AgentMessage.query.filter_by(task_id=task_id).order_by(AgentMessage.created_at.asc()).all()
