"""
Tests for Capability Registry and Agent Matching Service.
"""

from app.services.agent_matching_service import find_best_agent_for_task


def test_capability_registration_and_listing(client, auth_headers):
    """Test registering system capabilities."""
    payload = {
        "name": "document_summarization",
        "description": "Summarize enterprise documents",
        "risk_level": "low",
    }
    res = client.post("/api/v1/capabilities", json=payload, headers=auth_headers)
    assert res.status_code == 201
    assert res.get_json()["capability"]["name"] == "document_summarization"

    list_res = client.get("/api/v1/capabilities", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.get_json()["capabilities"]) >= 1


def test_agent_matching_service(client, auth_headers):
    """Test matching an agent for required capabilities."""
    # Register an agent with specific capabilities
    payload = {
        "name": "Security Analyzer",
        "role": "Analyst",
        "system_instructions": "Analyze security threats.",
        "capabilities": ["security_analysis", "sql_analysis"],
    }
    client.post("/api/v1/agents", json=payload, headers=auth_headers)

    match_payload = {
        "required_capabilities": ["security_analysis"],
        "role": "Analyst",
    }
    res = client.post("/api/v1/capabilities/match", json=match_payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["matched"] is True
    assert data["agent"]["name"] == "Security Analyzer"
