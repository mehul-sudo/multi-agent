"""
Tests for Inter-Agent Communication Protocol.
"""

from app.extensions import db
from app.models.agent_message import MESSAGE_TYPE_TASK_REQUEST, MESSAGE_TYPE_TASK_RESULT
from app.models.orchestration_session import OrchestrationSession
from app.services.agent_message_service import get_orchestration_messages, send_agent_message


def test_send_and_retrieve_agent_messages(app, test_user):
    """Test sending and querying structured inter-agent messages."""
    with app.app_context():
        session = OrchestrationSession(user_id=test_user.id, objective="Communication test.")
        db.session.add(session)
        db.session.commit()

        msg1 = send_agent_message(
            orchestration_id=session.id,
            sender_agent_id=None,
            receiver_agent_id=1,
            message_type=MESSAGE_TYPE_TASK_REQUEST,
            subject="Execute Research",
            payload={"query": "enterprise automation"},
            correlation_id=session.correlation_id,
        )
        assert msg1.id is not None

        messages = get_orchestration_messages(session.id)
        assert len(messages) == 1
        assert messages[0].subject == "Execute Research"


def test_agent_messages_api_endpoint(client, auth_headers):
    """Test querying inter-agent messages via REST API."""
    create_res = client.post("/api/v1/orchestrations", json={"objective": "Msg API test"}, headers=auth_headers)
    orch_id = create_res.get_json()["orchestration"]["id"]

    # Start orchestration to generate message logs
    client.post(f"/api/v1/orchestrations/{orch_id}/start", headers=auth_headers)

    res = client.get(f"/api/v1/orchestrations/{orch_id}/messages", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "messages" in data
    assert len(data["messages"]) >= 2
