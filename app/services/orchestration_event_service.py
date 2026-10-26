"""
OrchestrationEventService.

Logs structured, append-only events for every orchestration lifecycle step.
"""

from typing import Any, Dict, Optional

from app.extensions import db
from app.models.orchestration_event import OrchestrationEvent
from app.services.secret_service import redact_secrets


def emit_orchestration_event(
    event_type: str,
    orchestration_id: int,
    correlation_id: str,
    trace_id: str,
    organization_id: str = "default_org",
    task_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    actor: str = "system",
    metadata: Optional[Dict[str, Any]] = None,
) -> OrchestrationEvent:
    """Create and persist an immutable orchestration event record."""
    sanitized_metadata = redact_secrets(metadata or {})

    event = OrchestrationEvent(
        event_type=event_type,
        organization_id=organization_id,
        orchestration_id=orchestration_id,
        task_id=task_id,
        agent_id=agent_id,
        correlation_id=correlation_id,
        trace_id=trace_id,
        actor=actor,
        event_metadata=sanitized_metadata,
    )
    db.session.add(event)
    db.session.commit()
    return event
