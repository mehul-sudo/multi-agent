"""
Unit and integration tests for Agent Registry, Agent Versioning, and Lifecycle.
"""

from app.models.agent import AGENT_STATUS_ACTIVE, AGENT_STATUS_DISABLED, Agent
from app.models.agent_version import AgentVersion


def test_agent_creation_and_versioning(client, auth_headers):
    """Test registering an agent and creating an immutable version snapshot."""
    payload = {
        "name": "Research Agent",
        "role": "Researcher",
        "system_instructions": "Conduct enterprise research.",
        "provider": "mock",
        "model": "mock-v1",
        "capabilities": ["web_research", "document_summarization"],
    }
    response = client.post("/api/v1/agents", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert "agent" in data
    assert data["agent"]["name"] == "Research Agent"
    assert data["agent"]["version"] == 1

    agent_id = data["agent"]["id"]

    # Verify version snapshot created
    resp_versions = client.get(f"/api/v1/agents/{agent_id}/versions", headers=auth_headers)
    assert resp_versions.status_code == 200
    versions_data = resp_versions.get_json()
    assert len(versions_data["versions"]) == 1
    assert versions_data["versions"][0]["version"] == 1


def test_agent_update_increments_version(client, auth_headers):
    """Test updating agent configuration increments the version number."""
    payload = {
        "name": "Writer Agent",
        "role": "Writer",
        "system_instructions": "Draft reports.",
    }
    create_res = client.post("/api/v1/agents", json=payload, headers=auth_headers)
    agent_id = create_res.get_json()["agent"]["id"]

    update_payload = {"system_instructions": "Draft comprehensive executive reports."}
    update_res = client.patch(f"/api/v1/agents/{agent_id}", json=update_payload, headers=auth_headers)
    assert update_res.status_code == 200
    assert update_res.get_json()["version"] == 2

    # Verify version history has 2 snapshots
    resp_versions = client.get(f"/api/v1/agents/{agent_id}/versions", headers=auth_headers)
    assert len(resp_versions.get_json()["versions"]) == 2


def test_agent_enable_disable_lifecycle(client, auth_headers):
    """Test enabling and disabling an agent."""
    payload = {
        "name": "Analyst Agent",
        "system_instructions": "Analyze metrics.",
    }
    create_res = client.post("/api/v1/agents", json=payload, headers=auth_headers)
    agent_id = create_res.get_json()["agent"]["id"]

    disable_res = client.post(f"/api/v1/agents/{agent_id}/disable", headers=auth_headers)
    assert disable_res.status_code == 200
    assert disable_res.get_json()["status"] == AGENT_STATUS_DISABLED

    enable_res = client.post(f"/api/v1/agents/{agent_id}/enable", headers=auth_headers)
    assert enable_res.status_code == 200
    assert enable_res.get_json()["status"] == AGENT_STATUS_ACTIVE
