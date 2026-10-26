"""
AuditEvent model.

Tracks administrative, lifecycle, and execution audit events across the application.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditEvent(db.Model):
    """System-wide audit event record."""

    __tablename__ = "audit_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), index=True, nullable=True)
    correlation_id = db.Column(db.String(64), index=True, nullable=True)

    event_type = db.Column(db.String(100), index=True, nullable=False)
    resource_type = db.Column(db.String(50), index=True, nullable=False)
    resource_id = db.Column(db.String(100), index=True, nullable=True)

    ip_address = db.Column(db.String(45), nullable=True)

    # Safe metadata JSON - MUST NOT contain passwords, keys, tokens or secrets
    event_data = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)


    # Relationships
    user = db.relationship("User", backref=db.backref("audit_events", lazy="dynamic"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent type={self.event_type} resource={self.resource_type}:{self.resource_id}>"
