"""
Tool Security Policy model.

Defines tool execution policies, dangerous-tool classifications,
input/output schema validation constraints, quotas, and denylists.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ToolPolicy(db.Model):
    """Tool capability and governance policy."""

    __tablename__ = "tool_policies"

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

    tool_name = db.Column(db.String(128), nullable=False, index=True)

    # Scoping
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_dangerous = db.Column(db.Boolean, nullable=False, default=False)
    require_approval = db.Column(db.Boolean, nullable=False, default=False)

    # Invocation quota & timeout limits
    timeout_seconds = db.Column(db.Integer, nullable=False, default=60)
    max_invocations_per_hour = db.Column(db.Integer, nullable=True, default=1000)

    # Target constraints
    allowed_domains = db.Column(db.JSON, nullable=True)  # SSRF protection
    denied_patterns = db.Column(db.JSON, nullable=True)  # Input injection protection

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<ToolPolicy public_id={self.public_id} tool_name={self.tool_name!r}>"
