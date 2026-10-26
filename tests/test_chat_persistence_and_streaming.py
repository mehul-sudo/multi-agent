"""
Tests for Persistent Chat History, Multi-turn Threads, and Real-Time Streaming.

Validates:
1. Conversation thread CRUD operations (/api/v1/chat/conversations)
2. Database persistence of user messages and assistant responses
3. Multi-turn continuity across multiple message rounds
4. Server-Sent Events (SSE) streaming (/api/v1/chat/stream)
5. Zero references to Calendar Agent
"""

import json
import pytest
from app.models.conversation import Conversation, ChatMessage


def test_conversation_crud_endpoints(client, auth_headers):
    """Test creating, listing, getting, and deleting conversations."""
    # 1. Create a new conversation
    res = client.post("/api/v1/chat/conversations", json={
        "agent_type": "chat_assistant",
        "title": "Cybersecurity Architecture Thread",
    }, headers=auth_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert "conversation" in data
    conv = data["conversation"]
    conv_id = conv["id"]
    assert conv["title"] == "Cybersecurity Architecture Thread"
    assert conv["agent_type"] == "chat_assistant"

    # 2. List conversations
    res_list = client.get("/api/v1/chat/conversations?agent_type=chat_assistant", headers=auth_headers)
    assert res_list.status_code == 200
    list_data = res_list.get_json()
    assert "conversations" in list_data
    conv_ids = [c["id"] for c in list_data["conversations"]]
    assert conv_id in conv_ids

    # 3. Retrieve single conversation
    res_single = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert res_single.status_code == 200
    single_data = res_single.get_json()
    assert single_data["conversation"]["id"] == conv_id

    # 4. Delete conversation
    res_del = client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert res_del.status_code == 200

    # 5. Verify deletion
    res_gone = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert res_gone.status_code == 404


def test_chat_message_persistence_and_auto_title(client, auth_headers):
    """Test that POST /api/v1/chat creates conversation, saves messages, and auto-titles."""
    # Send a question
    res = client.post("/api/v1/chat", json={
        "message": "Who discovered cybersecurity?",
        "mode": "auto",
    }, headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "completed"
    assert "conversation_id" in data
    conv_id = data["conversation_id"]
    assert len(data["response"]) > 20

    # Verify conversation and messages in DB via API
    res_conv = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert res_conv.status_code == 200
    conv_data = res_conv.get_json()["conversation"]
    msgs = conv_data["messages"]
    assert len(msgs) == 2  # 1 user + 1 assistant
    assert msgs[0]["sender"] == "user"
    assert "Who discovered cybersecurity?" in msgs[0]["content"]
    assert msgs[1]["sender"] == "assistant"
    assert len(msgs[1]["content"]) > 20

    # Send a follow-up in the same conversation
    res_followup = client.post("/api/v1/chat", json={
        "message": "Tell me more about Bob Thomas and the Creeper virus.",
        "conversation_id": conv_id,
        "mode": "auto",
    }, headers=auth_headers)
    assert res_followup.status_code == 200
    followup_data = res_followup.get_json()
    assert followup_data["conversation_id"] == conv_id

    # Verify 4 messages in DB
    res_conv2 = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    msgs2 = res_conv2.get_json()["conversation"]["messages"]
    assert len(msgs2) == 4
    assert msgs2[2]["sender"] == "user"
    assert "Creeper" in msgs2[2]["content"]
    assert msgs2[3]["sender"] == "assistant"


def test_chat_streaming_persistence_and_events(app, client, auth_headers):
    """Test POST /api/v1/chat/stream returns valid SSE events and persists conversation."""
    res = client.post("/api/v1/chat/stream", json={
        "message": "Explain what a honeypot in cybersecurity is in 2 points.",
        "mode": "chat",
    }, headers=auth_headers)
    assert res.status_code == 200
    assert "text/event-stream" in res.content_type

    raw_events = res.data.decode("utf-8")
    lines = raw_events.strip().split("\n")
    event_payloads = []
    for line in lines:
        if line.startswith("data: "):
            try:
                event_payloads.append(json.loads(line[6:]))
            except Exception:
                pass

    event_types = [e["event_type"] for e in event_payloads]
    assert "conversation.started" in event_types
    assert "assistant.completed" in event_types

    # Find conversation_id
    started_evt = next(e for e in event_payloads if e["event_type"] == "conversation.started")
    conv_id = started_evt["data"].get("conversation_id")
    assert conv_id is not None

    # Verify completed event has text
    completed_evt = next(e for e in event_payloads if e["event_type"] == "assistant.completed")
    resp_text = completed_evt["data"].get("response", "")
    assert len(resp_text) > 10

    # Verify persisted in database
    res_conv = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert res_conv.status_code == 200
    msgs = res_conv.get_json()["conversation"]["messages"]
    assert len(msgs) >= 2


def test_calendar_agent_strict_absence(app):
    """Verify that Calendar Agent is strictly absent across database models, agents, and endpoints."""
    from app.agents.registry import list_registered_agent_types
    from app.models.agent import Agent, KNOWN_AGENT_TYPES

    with app.app_context():
        all_agents = Agent.query.all()
        calendar_names = [a.name.lower() for a in all_agents if "calendar" in a.name.lower()]
        calendar_types = [a.agent_type.lower() for a in all_agents if "calendar" in a.agent_type.lower()]
        assert len(calendar_names) == 0, f"Found calendar agents: {calendar_names}"
        assert len(calendar_types) == 0, f"Found calendar types: {calendar_types}"

        known_calendar = [t.lower() for t in KNOWN_AGENT_TYPES if "calendar" in t.lower()]
        assert len(known_calendar) == 0, f"Found calendar in KNOWN_AGENT_TYPES: {known_calendar}"

        registered_types = [t.lower() for t in list_registered_agent_types() if "calendar" in t.lower()]
        assert len(registered_types) == 0, f"Found registered calendar types: {registered_types}"
