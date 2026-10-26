"""
Tests for Resource Governance, Budget Enforcement, and Tenant Security Isolation.
"""

import pytest

from app.extensions import db
from app.models.orchestration_session import OrchestrationSession
from app.services.governance_service import BudgetExceededError, check_orchestration_limits


def test_orchestration_token_budget_limit_exceeded(app, test_user):
    """Test that exceeding orchestration token limits raises BudgetExceededError."""
    with app.app_context():
        session = OrchestrationSession(
            user_id=test_user.id,
            objective="Budget test",
            max_total_tokens=100,
            total_tokens_used=90,
        )
        db.session.add(session)
        db.session.commit()

        with pytest.raises(BudgetExceededError):
            check_orchestration_limits(session, estimated_tokens=20)


def test_cross_user_orchestration_access_rejected(client, auth_headers, other_auth_headers):
    """Test that users cannot access or manipulate other users' orchestration sessions."""
    payload = {"objective": "Owner objective."}
    create_res = client.post("/api/v1/orchestrations", json=payload, headers=auth_headers)
    orch_id = create_res.get_json()["orchestration"]["id"]

    # Other user attempts to get session
    get_res = client.get(f"/api/v1/orchestrations/{orch_id}", headers=other_auth_headers)
    assert get_res.status_code == 404

    # Other user attempts to pause session
    pause_res = client.post(f"/api/v1/orchestrations/{orch_id}/pause", headers=other_auth_headers)
    assert pause_res.status_code == 404
