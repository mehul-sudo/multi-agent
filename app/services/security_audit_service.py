"""
Security Audit Logging Service.

Provides tenant-aware, correlation-id enabled audit event recording and querying.
Guarantees secret redaction so passwords, tokens, API keys, and credentials are
never persisted in audit log payloads.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from flask import request
from flask_jwt_extended import current_user

from app.extensions import db
from app.models.audit_event import AuditEvent
from app.services.secret_service import SecretService


class SecurityAuditService:
    """Service for logging security events and retrieving tenant-isolated audit logs."""

    @staticmethod
    def log_event(
        event_type: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Record an audit event with secret redaction and correlation metadata."""
        # Fallback to current request context if available
        if user_id is None and current_user:
            user_id = current_user.id

        if ip_address is None and request:
            try:
                ip_address = request.remote_addr
            except Exception:
                ip_address = None

        if correlation_id is None and request:
            try:
                correlation_id = getattr(request, "correlation_id", None) or request.headers.get("X-Correlation-ID")
            except Exception:
                correlation_id = None

        safe_data = event_data or {}
        # Apply secret redaction service to ensure zero password/token/key leaks
        redacted_data = SecretService.redact_dict(safe_data)

        event = AuditEvent(
            event_type=event_type,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            user_id=user_id,
            organization_id=organization_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            ip_address=ip_address,
            event_data=redacted_data,
        )
        db.session.add(event)
        db.session.commit()
        return event

    @staticmethod
    def get_audit_logs(
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        event_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[AuditEvent], int]:
        """Fetch audit log events with tenant scope filtering and pagination."""
        query = AuditEvent.query

        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        elif user_id:
            query = query.filter_by(user_id=user_id)

        if event_type:
            query = query.filter_by(event_type=event_type)

        if resource_type:
            query = query.filter_by(resource_type=resource_type)

        query = query.order_by(AuditEvent.created_at.desc())
        total = query.count()
        events = query.offset((page - 1) * per_page).limit(per_page).all()
        return events, total
