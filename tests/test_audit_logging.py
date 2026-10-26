"""
Unit tests for Audit Logging Service (Phase 5).
"""

import pytest
from app.models.audit_event import AuditEvent
from app.services.audit_service import log_audit_event


def test_log_audit_event_and_redaction(app, db_session, test_user):
    """Verify audit log records events and redacts password/token/secret metadata keys."""
    with app.app_context():
        event = log_audit_event(
            event_type="TEST_EVENT",
            resource_type="agent",
            resource_id="agent-uuid-123",
            user_id=test_user.id,
            event_data={
                "action": "create",
                "password": "secretpassword",
                "jwt_token": "bearer 123",
                "safe_param": "visible_value",
            },
        )

        assert event is not None
        assert event.event_type == "TEST_EVENT"
        assert event.event_data["password"] == "[REDACTED]"
        assert event.event_data["jwt_token"] == "[REDACTED]"
        assert event.event_data["safe_param"] == "visible_value"
