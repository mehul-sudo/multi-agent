"""
Tests for Scoped Shared Context and Agent Memory.
"""

import pytest

from app.extensions import db
from app.models.orchestration_session import OrchestrationSession
from app.models.shared_context import CONTEXT_SCOPE_AGENT_PRIVATE, CONTEXT_SCOPE_GLOBAL
from app.services.context_service import ContextAccessDeniedError, get_all_context_for_orchestration, get_context_entry, set_context_entry


def test_scoped_context_read_write_and_versioning(app, test_user):
    """Test creating, updating, and versioning context entries."""
    with app.app_context():
        session = OrchestrationSession(user_id=test_user.id, objective="Context test.")
        db.session.add(session)
        db.session.commit()

        rec1 = set_context_entry(session.id, key="summary", value="v1 content", scope=CONTEXT_SCOPE_GLOBAL)
        assert rec1.version == 1

        val1 = get_context_entry(session.id, key="summary", scope=CONTEXT_SCOPE_GLOBAL)
        assert val1 == "v1 content"

        rec2 = set_context_entry(session.id, key="summary", value="v2 updated content", scope=CONTEXT_SCOPE_GLOBAL)
        assert rec2.version == 2


def test_private_agent_context_isolation(app, test_user):
    """Test that agent-private context cannot be accessed by another agent."""
    with app.app_context():
        session = OrchestrationSession(user_id=test_user.id, objective="Private context test.")
        db.session.add(session)
        db.session.commit()

        set_context_entry(
            orchestration_id=session.id,
            key="agent_secret_memo",
            value="private_data",
            scope=CONTEXT_SCOPE_AGENT_PRIVATE,
            agent_id=10,
        )

        # Agent 10 can access
        val = get_context_entry(session.id, key="agent_secret_memo", scope=CONTEXT_SCOPE_AGENT_PRIVATE, requesting_agent_id=10)
        assert val == "private_data"

        # Agent 99 is denied
        with pytest.raises(ContextAccessDeniedError):
            get_context_entry(session.id, key="agent_secret_memo", scope=CONTEXT_SCOPE_AGENT_PRIVATE, requesting_agent_id=99)
