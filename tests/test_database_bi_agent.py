"""
Unit tests for DatabaseBIAgent.
"""

import pytest
from app import create_app
from app.agents.base import AgentContext
from app.agents.database_bi_agent import DatabaseBIAgent
from app.extensions import db


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def test_database_bi_agent_select_query(app_ctx):
    agent = DatabaseBIAgent()
    ctx = AgentContext(
        input_data={"query": "SELECT 1 AS count_val, 'healthy' AS status_str"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "database_bi"
    assert result.output["rowCount"] == 1
    assert result.output["rows"][0]["count_val"] == 1
    assert result.output["rows"][0]["status_str"] == "healthy"


def test_database_bi_agent_blocks_destructive_query(app_ctx):
    agent = DatabaseBIAgent()
    ctx = AgentContext(
        input_data={"query": "DROP TABLE users;"},
    )

    result = agent.execute(ctx)
    assert result.success is False
    assert "Only read-only SELECT" in result.error or "Prohibited keyword" in result.error


def test_database_bi_agent_schema_inspection(app_ctx):
    agent = DatabaseBIAgent()
    ctx = AgentContext(
        input_data={"operation": "inspect_schema"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert "tables" in result.output
    assert isinstance(result.output["tables"], list)
