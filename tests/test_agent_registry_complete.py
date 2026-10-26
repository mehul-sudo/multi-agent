"""
Integration tests for Agent Registry and End-to-End Specialized Agent Dispatch.
"""

import pytest
from app.agents import (
    get_agent_instance,
    is_agent_registered,
    list_registered_agent_types,
)


def test_all_seven_agents_registered():
    """Verify that all 7 required enterprise agents are registered into AGENT_REGISTRY."""
    expected_agents = [
        "data_analysis",
        "document_research",
        "report_generation",
        "email",
        "database_bi",
        "http_webhook",
        "security_analysis",
    ]

    registered = list_registered_agent_types()
    for agent_type in expected_agents:
        assert agent_type in registered, f"Agent type '{agent_type}' missing from registry."
        assert is_agent_registered(agent_type) is True
        instance = get_agent_instance(agent_type)
        assert instance is not None
        assert instance.agent_type == agent_type


def test_api_list_agent_types_endpoint(client, auth_headers):
    """Test GET /api/agents/types REST endpoint."""
    response = client.get("/api/agents/types", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "agent_types" in data
    types_list = [item["agent_type"] for item in data["agent_types"]]
    assert "data_analysis" in types_list
    assert "email" in types_list
    assert "security_analysis" in types_list


def test_api_direct_agent_execution_endpoint(client, auth_headers):
    """Test POST /api/agents/<agent_type>/execute REST endpoint."""
    payload = {
        "input": {
            "content": "aws_key = 'AKIA1234567890123456'",
            "target": "credentials.py",
        }
    }
    response = client.post("/api/agents/security_analysis/execute", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["agent_type"] == "security_analysis"
    assert "findings" in data["output"]
    assert len(data["output"]["findings"]) >= 1
