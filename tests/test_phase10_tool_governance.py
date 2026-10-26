"""
Tests for Phase 10 Agent Capability and Tool Governance.
"""

import pytest
from app.models.agent import Agent
from app.models.tool_policy import ToolPolicy
from app.services.tool_authorization_service import ToolAuthorizationService


def test_tool_authorization_allowed_tools(db_session, user_factory):
    user = user_factory()
    agent = Agent(
        user_id=user.id,
        name="Research Agent",
        system_instructions="Do research",
        allowed_tools=["read_document", "search_web"],
        capabilities=["read_document"],
        status="active",
    )
    db_session.add(agent)
    db_session.commit()

    # Allowed tool
    authorized, reason = ToolAuthorizationService.authorize_tool_invocation(
        agent=agent, tool_name="read_document", tool_input={"doc_id": "123"}
    )
    assert authorized is True
    assert reason is None

    # Disallowed tool
    authorized, reason = ToolAuthorizationService.authorize_tool_invocation(
        agent=agent, tool_name="execute_code", tool_input={"code": "print(1)"}
    )
    assert authorized is False
    assert "not in agent's allowed_tools list" in reason


def test_prompt_injection_pattern_denial(db_session, user_factory):
    user = user_factory()
    agent = Agent(
        user_id=user.id,
        name="DB Agent",
        system_instructions="Perform DB tasks",
        allowed_tools=["query_db"],
        status="active",
    )
    db_session.add(agent)
    db_session.commit()

    # Malicious injection payload
    authorized, reason = ToolAuthorizationService.authorize_tool_invocation(
        agent=agent, tool_name="query_db", tool_input={"query": "SELECT * FROM users; DROP TABLE users;"}
    )
    assert authorized is False
    assert "security policy violation" in reason
