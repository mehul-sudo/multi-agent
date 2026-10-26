"""
Tests for Phase 10 Approval Gate Hardening, Self-Approval Prevention, and Expiry.
"""

from datetime import datetime, timedelta, timezone
import pytest
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.models.orchestration_session import OrchestrationSession
from app.services.approval_service import create_approval_request, resolve_approval_request


def test_self_approval_prevention(db_session, user_factory):
    requester = user_factory()
    orchestration = OrchestrationSession(
        user_id=requester.id,
        objective="Sensitive Financial Mutation",
        status="RUNNING",
    )

    db_session.add(orchestration)
    db_session.commit()

    req = create_approval_request(
        orchestration=orchestration,
        requested_action="execute_wire_transfer",
        explanation="Wire $50,000",
    )

    # Resolving approval as the requester with self-approval prevention enabled should fail
    with pytest.raises(ValueError, match="Self-approval is forbidden"):
        resolve_approval_request(
            approval_id=req.id,
            user_id=requester.id,
            approve=True,
            prevent_self_approval=True,
        )


def test_expired_approval_rejection(db_session, user_factory):
    user = user_factory()
    approver = user_factory()

    orchestration = OrchestrationSession(
        user_id=user.id,
        objective="Data Deletion",
        status="RUNNING",
    )

    db_session.add(orchestration)
    db_session.commit()

    req = create_approval_request(
        orchestration=orchestration,
        requested_action="delete_customer_database",
        explanation="Purge stale customer table",
    )
    # Set past expiration timestamp
    req.expiry_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    db_session.commit()

    # Attempting to resolve expired approval should raise ValueError
    with pytest.raises(ValueError, match="expired"):
        resolve_approval_request(
            approval_id=req.id,
            user_id=approver.id,
            approve=True,
        )

    # Check status transitioned to EXPIRED
    req_updated = db_session.get(ApprovalRequest, req.id)
    assert req_updated.status == "EXPIRED"
