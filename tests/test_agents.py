"""
Unit and Integration Tests for Agent API & Service (Phase 5).
"""

import pytest
from app.models.agent import Agent, AGENT_STATUS_ACTIVE, AGENT_STATUS_DISABLED, AGENT_STATUS_ARCHIVED


def test_create_agent_success(client, auth_headers):
    """Verify creating a valid agent returns 201 and correct fields."""
    payload = {
        "name": "Email Assistant",
        "description": "Handles sending and processing automated emails.",
        "agent_type": "email",
        "system_instructions": "Draft concise and professional email responses.",
        "configuration": {"smtp_port": 587},
        "capabilities": ["send_email", "parse_inbox"],
    }
    response = client.post("/api/agents", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Email Assistant"
    assert data["agent_type"] == "email"
    assert data["status"] == AGENT_STATUS_ACTIVE
    assert data["version"] == 1
    assert "public_id" in data


def test_create_agent_invalid_sensitive_config(client, auth_headers):
    """Verify creating an agent with sensitive password keys in config is rejected."""
    payload = {
        "name": "Malicious Agent",
        "system_instructions": "Try to log password.",
        "configuration": {"secret_password": "supersecretvalue"},
    }
    response = client.post("/api/agents", json=payload, headers=auth_headers)
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_list_agents_pagination_and_filter(client, auth_headers):
    """Verify listing agents supports pagination and filtering."""
    # Create 2 agents
    client.post(
        "/api/agents",
        json={"name": "Agent One", "agent_type": "email", "system_instructions": "Email task."},
        headers=auth_headers,
    )
    client.post(
        "/api/agents",
        json={"name": "Agent Two", "agent_type": "report_generation", "system_instructions": "Report task."},
        headers=auth_headers,
    )

    # Filter by agent_type
    res = client.get("/api/agents?agent_type=email", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Agent One"


def test_get_agent_success_and_cross_user_rejection(client, auth_headers, other_auth_headers):
    """Verify users cannot access agents owned by another user."""
    # Create agent under user 1
    res1 = client.post(
        "/api/agents",
        json={"name": "Private Agent", "system_instructions": "Private work."},
        headers=auth_headers,
    )
    agent_id = res1.get_json()["public_id"]

    # User 1 can access
    get_res = client.get(f"/api/agents/{agent_id}", headers=auth_headers)
    assert get_res.status_code == 200

    # User 2 access is rejected with 404/403
    cross_res = client.get(f"/api/agents/{agent_id}", headers=other_auth_headers)
    assert cross_res.status_code == 404


def test_update_agent(client, auth_headers):
    """Verify updating agent fields increases version."""
    res1 = client.post(
        "/api/agents",
        json={"name": "Original Agent", "system_instructions": "Initial instructions."},
        headers=auth_headers,
    )
    agent_id = res1.get_json()["public_id"]

    patch_res = client.patch(
        f"/api/agents/{agent_id}",
        json={"name": "Updated Agent Name"},
        headers=auth_headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.get_json()
    assert data["name"] == "Updated Agent Name"
    assert data["version"] == 2


def test_activate_and_disable_agent(client, auth_headers):
    """Verify activating and disabling an agent."""
    res1 = client.post(
        "/api/agents",
        json={"name": "Toggle Agent", "system_instructions": "Toggle instructions."},
        headers=auth_headers,
    )
    agent_id = res1.get_json()["public_id"]

    # Disable
    dis_res = client.post(f"/api/agents/{agent_id}/disable", headers=auth_headers)
    assert dis_res.status_code == 200
    assert dis_res.get_json()["status"] == AGENT_STATUS_DISABLED

    # Activate
    act_res = client.post(f"/api/agents/{agent_id}/activate", headers=auth_headers)
    assert act_res.status_code == 200
    assert act_res.get_json()["status"] == AGENT_STATUS_ACTIVE


def test_create_agent_invalid_provider_rejected(client, auth_headers):
    """Creating an agent with an unknown provider must be rejected with 400."""
    res = client.post(
        "/api/agents",
        json={
            "name": "Invalid Provider Agent",
            "system_instructions": "Test instructions",
            "provider": "nonexistent_provider",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "VALIDATION_ERROR" in res.get_json()["error"]["code"]

