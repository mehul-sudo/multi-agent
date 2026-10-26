"""
Tests for Human-in-the-loop Approvals System.
"""

import pytest

from app.extensions import db
from app.models.approval_request import APPROVAL_STATUS_APPROVED, APPROVAL_STATUS_PENDING, APPROVAL_STATUS_REJECTED
from app.models.orchestration_session import OrchestrationSession
from app.services.approval_service import create_approval_request, resolve_approval_request


def test_create_and_resolve_approval_request(app, test_user, user_factory):
    """A designated approver (different from the requester) can approve a request."""
    with app.app_context():
        approver = user_factory(username="approver1", email="approver1@example.com")
        session = OrchestrationSession(user_id=test_user.id, objective="Approval test.")
        db.session.add(session)
        db.session.commit()

        req = create_approval_request(
            orchestration=session,
            requested_action="Deploy changes",
            explanation="Requires human signoff.",
            assigned_approver_user_id=approver.id,
        )
        assert req.status == APPROVAL_STATUS_PENDING

        resolved = resolve_approval_request(
            approval_id=req.id, user_id=approver.id, approve=True, comments="Looks good."
        )
        assert resolved.status == APPROVAL_STATUS_APPROVED


def test_self_approval_is_forbidden_by_default(app, test_user):
    """The requester must not be able to approve their own request (secure default)."""
    with app.app_context():
        session = OrchestrationSession(user_id=test_user.id, objective="Self approval test.")
        db.session.add(session)
        db.session.commit()

        # No explicit approver -> defaults to the requester; resolving it as the
        # requester must be blocked by the self-approval guard.
        req = create_approval_request(
            orchestration=session,
            requested_action="Deploy changes",
            explanation="Requires human signoff.",
        )
        assert req.status == APPROVAL_STATUS_PENDING

        with pytest.raises(ValueError, match="Self-approval"):
            resolve_approval_request(approval_id=req.id, user_id=test_user.id, approve=True)

        # The request stays pending after the blocked self-approval attempt.
        refreshed = db.session.get(type(req), req.id)
        assert refreshed.status == APPROVAL_STATUS_PENDING


def test_approval_api_endpoints(client, auth_headers, other_auth_headers, test_user, other_user):
    """List and approve a request via the API where requester != approver.

    other_user owns the orchestration (the requester); test_user is the
    assigned approver and resolves it through the API.
    """
    payload = {"objective": "API Approval test."}
    create_res = client.post("/api/v1/orchestrations", json=payload, headers=other_auth_headers)
    orch_id = create_res.get_json()["orchestration"]["id"]

    # Assign the approval to test_user (distinct from the requester other_user).
    with client.application.app_context():
        session = OrchestrationSession.query.filter_by(public_id=orch_id).first()
        create_approval_request(
            session,
            requested_action="API action",
            explanation="Verification required.",
            assigned_approver_user_id=test_user.id,
        )

    list_res = client.get("/api/v1/approvals", headers=auth_headers)
    assert list_res.status_code == 200
    approvals = list_res.get_json()["approvals"]
    assert len(approvals) >= 1
    appr_id = approvals[0]["id"]

    approve_res = client.post(
        f"/api/v1/approvals/{appr_id}/approve", json={"comments": "Approved"}, headers=auth_headers
    )
    assert approve_res.status_code == 200
    assert approve_res.get_json()["status"] == APPROVAL_STATUS_APPROVED


def test_api_rejects_self_approval(client, auth_headers, test_user):
    """Approving one's own request via the API is rejected with HTTP 400."""
    payload = {"objective": "Self approval via API."}
    create_res = client.post("/api/v1/orchestrations", json=payload, headers=auth_headers)
    orch_id = create_res.get_json()["orchestration"]["id"]

    # Approval defaults to the requester (test_user) as approver.
    with client.application.app_context():
        session = OrchestrationSession.query.filter_by(public_id=orch_id).first()
        create_approval_request(
            session,
            requested_action="Self action",
            explanation="Should not be self-approvable.",
        )

    list_res = client.get("/api/v1/approvals", headers=auth_headers)
    appr_id = list_res.get_json()["approvals"][0]["id"]

    approve_res = client.post(
        f"/api/v1/approvals/{appr_id}/approve", json={"comments": "self"}, headers=auth_headers
    )
    assert approve_res.status_code == 400
    assert "Self-approval" in approve_res.get_json()["error"]
