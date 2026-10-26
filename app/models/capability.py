"""
Capability and AgentCapability models.

Defines registered agent capabilities (input/output JSON schemas, permissions, risk levels)
and agent-capability associations.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Capability(db.Model):
    """A registered system capability."""

    __tablename__ = "capabilities"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    name = db.Column(db.String(100), unique=True, index=True, nullable=False)
    display_name = db.Column(db.String(150), nullable=True)
    description = db.Column(db.Text, nullable=True)

    input_schema = db.Column(db.JSON, nullable=False, default=dict)
    output_schema = db.Column(db.JSON, nullable=False, default=dict)

    required_permissions = db.Column(db.JSON, nullable=False, default=list)
    risk_level = db.Column(db.String(20), nullable=False, default="low")  # low, medium, high, critical
    required_tools = db.Column(db.JSON, nullable=False, default=list)
    supported_data_types = db.Column(db.JSON, nullable=False, default=list)

    estimated_cost = db.Column(db.Float, nullable=False, default=0.0)
    estimated_execution_time = db.Column(db.Integer, nullable=False, default=10)
    requires_human_approval = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<Capability name={self.name!r} risk={self.risk_level}>"


class AgentCapability(db.Model):
    """Association between Agent and Capability."""

    __tablename__ = "agent_capabilities"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=False)
    capability_id = db.Column(db.Integer, db.ForeignKey("capabilities.id"), index=True, nullable=False)

    proficiency_score = db.Column(db.Float, nullable=False, default=1.0)
    is_primary = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    agent = db.relationship("Agent", backref=db.backref("agent_capabilities", lazy="dynamic", cascade="all, delete-orphan"))
    capability = db.relationship("Capability", backref=db.backref("agent_capabilities", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<AgentCapability agent_id={self.agent_id} capability_id={self.capability_id}>"
