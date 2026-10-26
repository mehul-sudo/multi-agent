"""
AgentVersion model.

Stores an immutable snapshot of an Agent's configuration for a specific version.
When an orchestration session starts, it binds to specific AgentVersion snapshots
so future modifications to the agent do not retroactively alter active sessions.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentVersion(db.Model):
    """An immutable snapshot of an Agent configuration."""

    __tablename__ = "agent_versions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=False)
    version = db.Column(db.Integer, nullable=False)

    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(150), nullable=True)
    description = db.Column(db.Text, nullable=True)
    system_instructions = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(50), nullable=False, default="Custom Specialized Agent")
    agent_type = db.Column(db.String(50), nullable=False, default="custom")

    provider = db.Column(db.String(50), nullable=False, default="mock")
    model = db.Column(db.String(100), nullable=False, default="mock-v1")
    temperature = db.Column(db.Float, nullable=False, default=0.7)
    max_tokens = db.Column(db.Integer, nullable=False, default=1000)

    fallback_provider = db.Column(db.String(50), nullable=True)
    fallback_model = db.Column(db.String(100), nullable=True)

    configuration = db.Column(db.JSON, nullable=False, default=dict)
    capabilities = db.Column(db.JSON, nullable=False, default=list)
    allowed_tools = db.Column(db.JSON, nullable=False, default=list)
    allowed_data_scopes = db.Column(db.JSON, nullable=False, default=list)
    budget_limits = db.Column(db.JSON, nullable=False, default=dict)

    priority = db.Column(db.Integer, nullable=False, default=1)
    max_concurrent_tasks = db.Column(db.Integer, nullable=False, default=5)
    timeout_seconds = db.Column(db.Integer, nullable=False, default=300)
    max_retries = db.Column(db.Integer, nullable=False, default=3)
    max_delegation_depth = db.Column(db.Integer, nullable=False, default=3)
    requires_human_approval = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    agent = db.relationship("Agent", backref=db.backref("versions", lazy="dynamic", cascade="all, delete-orphan"))

    def __repr__(self) -> str:
        return f"<AgentVersion agent_id={self.agent_id} version={self.version}>"
