"""
Tests for Phase 10 Security Audit Logging and Secret Redaction.
"""

import pytest
from app.services.security_audit_service import SecurityAuditService


def test_log_security_event_and_redaction(db_session, user_factory):
    user = user_factory()
    event = SecurityAuditService.log_event(
        event_type="credential_access",
        resource_type="credential",
        resource_id="cred-101",
        user_id=user.id,
        event_data={
            "action": "decrypt",
            "password": "my-secret-password",
            "api_key": "sk_live_secret123456789",
        },
    )

    assert event.id is not None
    assert event.event_type == "credential_access"
    assert event.user_id == user.id

    # Verify secret fields were redacted
    assert event.event_data["password"] == "[REDACTED]"
    assert event.event_data["api_key"] == "[REDACTED]"
    assert event.event_data["action"] == "decrypt"


def test_get_audit_logs_tenant_isolation(db_session, user_factory):
    user1 = user_factory()
    user2 = user_factory()

    SecurityAuditService.log_event(
        event_type="login", resource_type="user", resource_id=str(user1.id), user_id=user1.id, organization_id=10
    )
    SecurityAuditService.log_event(
        event_type="login", resource_type="user", resource_id=str(user2.id), user_id=user2.id, organization_id=20
    )

    logs_org10, count10 = SecurityAuditService.get_audit_logs(organization_id=10)
    assert count10 == 1
    assert logs_org10[0].user_id == user1.id

    logs_org20, count20 = SecurityAuditService.get_audit_logs(organization_id=20)
    assert count20 == 1
    assert logs_org20[0].user_id == user2.id
