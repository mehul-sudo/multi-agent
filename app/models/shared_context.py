"""
SharedContextRecord and ContextVersion models.

Scoped shared context and memory records (`GLOBAL`, `PLAN`, `TASK`, `AGENT_PRIVATE`).
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db

CONTEXT_SCOPE_GLOBAL = "GLOBAL"
CONTEXT_SCOPE_PLAN = "PLAN"
CONTEXT_SCOPE_TASK = "TASK"
CONTEXT_SCOPE_AGENT_PRIVATE = "AGENT_PRIVATE"

SUPPORTED_CONTEXT_SCOPES = (
    CONTEXT_SCOPE_GLOBAL,
    CONTEXT_SCOPE_PLAN,
    CONTEXT_SCOPE_TASK,
    CONTEXT_SCOPE_AGENT_PRIVATE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SharedContextRecord(db.Model):
    """A scoped key-value memory record for orchestration execution."""

    __tablename__ = "shared_context_records"

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
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)

    scope = db.Column(db.String(30), nullable=False, default=CONTEXT_SCOPE_GLOBAL)
    key = db.Column(db.String(150), index=True, nullable=False)

    value = db.Column(db.JSON, nullable=False, default=dict)
    value_type = db.Column(db.String(30), nullable=False, default="json")

    is_sensitive = db.Column(db.Boolean, nullable=False, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SharedContextRecord scope={self.scope} key={self.key!r} v={self.version}>"


class ContextVersion(db.Model):
    """Historical audit snapshot of a SharedContextRecord."""

    __tablename__ = "context_versions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    context_record_id = db.Column(db.Integer, db.ForeignKey("shared_context_records.id"), index=True, nullable=False)
    version = db.Column(db.Integer, nullable=False)

    value = db.Column(db.JSON, nullable=False, default=dict)
    updated_by_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    context_record = db.relationship("SharedContextRecord", backref=db.backref("history", lazy="dynamic", cascade="all, delete-orphan"))

    def __repr__(self) -> str:
        return f"<ContextVersion record_id={self.context_record_id} v={self.version}>"
