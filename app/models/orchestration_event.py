"""
OrchestrationEvent model.

Append-only event audit log for multi-agent orchestration lifecycle events.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrchestrationEvent(db.Model):
    """An auditable orchestration lifecycle event."""

    __tablename__ = "orchestration_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    event_type = db.Column(db.String(50), index=True, nullable=False)
    organization_id = db.Column(db.String(100), index=True, nullable=True, default="default_org")

    orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), index=True, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)

    correlation_id = db.Column(db.String(100), index=True, nullable=False)
    trace_id = db.Column(db.String(100), index=True, nullable=False)

    actor = db.Column(db.String(100), nullable=False, default="system")
    event_metadata = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:
        return f"<OrchestrationEvent type={self.event_type!r} orch_id={self.orchestration_id}>"
