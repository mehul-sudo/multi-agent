"""
Audit Logging Service.

Provides helper functions for recording security, administrative, and workflow
audit events.
"""

from flask import request
from app.extensions import db
from app.models.audit_event import AuditEvent


def log_audit_event(
    event_type: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: int | None = None,
    event_data: dict | None = None,
) -> AuditEvent | None:
    """Record an audit event to the database.

    Args:
        event_type: String identifier for the action (e.g. AGENT_CREATED).
        resource_type: Target resource category (e.g. agent, workflow).
        resource_id: Public ID of the resource.
        user_id: Internal user ID of the actor.
        event_data: Safe metadata dictionary (no credentials/passwords).

    Returns:
        The created AuditEvent object or None if failed safely.
    """
    ip_address = None
    try:
        if request:
            ip_address = request.remote_addr
    except Exception:
        pass

    safe_data = {}
    if event_data:
        # Sanitize event data to exclude sensitive key patterns
        for key, value in event_data.items():
            key_lower = str(key).lower()
            if any(s in key_lower for s in ("password", "token", "secret", "authorization", "jwt", "key")):
                safe_data[key] = "[REDACTED]"
            else:
                safe_data[key] = value

    audit_record = AuditEvent(
        user_id=user_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        event_data=safe_data,
    )

    try:
        db.session.add(audit_record)
        db.session.commit()
        return audit_record
    except Exception:
        db.session.rollback()
        return None
