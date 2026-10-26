"""
Agent model.

Represents a specialized AI worker capable of performing specific enterprise tasks.
Belongs to a User account.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

AGENT_STATUS_ACTIVE = "active"
AGENT_STATUS_DISABLED = "disabled"
AGENT_STATUS_ARCHIVED = "archived"
SUPPORTED_AGENT_STATUSES = (AGENT_STATUS_ACTIVE, AGENT_STATUS_DISABLED, AGENT_STATUS_ARCHIVED)

KNOWN_AGENT_TYPES = (
    "email",
    "document_research",
    "report_generation",
    "security_analysis",
    "data_analysis",
    "database_bi",
    "http_webhook",
    "coordinator",
    "custom",
)



def _utcnow() -> datetime:
    """Return naive UTC datetime for storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Agent(db.Model):
    """An AI Agent entity."""

    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            f"status IN {SUPPORTED_AGENT_STATUSES}",
            name="ck_agents_status_valid",
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

    agent_type = db.Column(db.String(50), index=True, nullable=False, default="custom")

    system_instructions = db.Column(db.Text, nullable=False)

    # Phase 6 LLM configuration fields
    provider = db.Column(db.String(50), nullable=False, default="mock")
    model = db.Column(db.String(100), nullable=False, default="mock-v1")
    temperature = db.Column(db.Float, nullable=False, default=0.7)
    max_tokens = db.Column(db.Integer, nullable=False, default=1000)
    token_budget = db.Column(db.Integer, nullable=True)
    cost_budget = db.Column(db.Float, nullable=True)
    fallback_provider = db.Column(db.String(50), nullable=True)

    # Safe non-sensitive configuration JSON
    configuration = db.Column(db.JSON, nullable=False, default=dict)

    # List of agent capability strings or dicts
    capabilities = db.Column(db.JSON, nullable=False, default=list)

    # Phase 8 multi-agent orchestration fields
    display_name = db.Column(db.String(150), nullable=True)
    role = db.Column(db.String(50), nullable=False, default="Custom Specialized Agent")
    fallback_model = db.Column(db.String(100), nullable=True)

    priority = db.Column(db.Integer, nullable=False, default=1)
    max_concurrent_tasks = db.Column(db.Integer, nullable=False, default=5)
    timeout_seconds = db.Column(db.Integer, nullable=False, default=300)
    max_retries = db.Column(db.Integer, nullable=False, default=3)
    max_delegation_depth = db.Column(db.Integer, nullable=False, default=3)
    requires_human_approval = db.Column(db.Boolean, nullable=False, default=False)

    allowed_tools = db.Column(db.JSON, nullable=False, default=list)
    allowed_data_scopes = db.Column(db.JSON, nullable=False, default=list)
    budget_limits = db.Column(db.JSON, nullable=False, default=dict)

    status = db.Column(db.String(20), nullable=False, default=AGENT_STATUS_ACTIVE)

    version = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("agents", lazy="dynamic"))

    def create_version_snapshot(self):
        """Create an immutable AgentVersion record for the current state."""
        from app.models.agent_version import AgentVersion

        snapshot = AgentVersion(
            agent_id=self.id,
            version=self.version,
            name=self.name,
            display_name=self.display_name or self.name,
            description=self.description,
            system_instructions=self.system_instructions,
            role=self.role,
            agent_type=self.agent_type,
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            fallback_provider=self.fallback_provider,
            fallback_model=self.fallback_model,
            configuration=self.configuration or {},
            capabilities=self.capabilities or [],
            allowed_tools=self.allowed_tools or [],
            allowed_data_scopes=self.allowed_data_scopes or [],
            budget_limits=self.budget_limits or {
                "token_budget": self.token_budget,
                "cost_budget": self.cost_budget,
            },
            priority=self.priority,
            max_concurrent_tasks=self.max_concurrent_tasks,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            max_delegation_depth=self.max_delegation_depth,
            requires_human_approval=self.requires_human_approval,
        )
        return snapshot

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Agent public_id={self.public_id} name={self.name!r} status={self.status}>"

