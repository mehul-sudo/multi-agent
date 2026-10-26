"""
Conversation Service.

Business logic for managing multi-turn chat threads and message persistence,
scoped by user ownership and agent workspace type.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.conversation import ChatMessage, Conversation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_conversation(
    user_id: int,
    agent_type: str = "chat_assistant",
    title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Conversation:
    """Create a new conversation thread for a user."""
    conv = Conversation(
        user_id=user_id,
        agent_type=agent_type or "chat_assistant",
        title=title or "New Conversation",
        metadata_json=metadata or {},
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.session.add(conv)
    db.session.commit()
    return conv


def get_or_create_active_conversation(
    user_id: int,
    agent_type: str = "chat_assistant",
    conversation_id: Optional[str] = None,
) -> Conversation:
    """Retrieve an existing conversation by public_id (or latest for user), or create a fresh one."""
    conv = None
    if conversation_id:
        conv = Conversation.query.filter_by(
            public_id=conversation_id,
            user_id=user_id,
        ).first()

    if not conv:
        # Check if the user has an existing active conversation for this agent_type
        conv = (
            Conversation.query.filter_by(user_id=user_id, agent_type=agent_type)
            .order_by(Conversation.updated_at.desc())
            .first()
        )

    if not conv:
        conv = create_conversation(user_id=user_id, agent_type=agent_type)

    return conv


def list_conversations(
    user_id: int,
    agent_type: Optional[str] = None,
    limit: int = 50,
) -> List[Conversation]:
    """List conversations for a user, ordered by most recently updated."""
    query = Conversation.query.filter_by(user_id=user_id)
    if agent_type:
        query = query.filter_by(agent_type=agent_type)
    return query.order_by(Conversation.updated_at.desc()).limit(limit).all()


def get_conversation(user_id: int, conversation_id: str) -> Optional[Conversation]:
    """Retrieve a conversation with strict user ownership enforcement."""
    return Conversation.query.filter_by(
        public_id=conversation_id,
        user_id=user_id,
    ).first()


def delete_conversation(user_id: int, conversation_id: str) -> bool:
    """Delete a conversation and all its messages."""
    conv = get_conversation(user_id, conversation_id)
    if not conv:
        return False
    db.session.delete(conv)
    db.session.commit()
    return True


def add_message(
    conversation_id: int,
    sender: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "completed",
) -> ChatMessage:
    """Add a message to a conversation and touch updated_at."""
    msg = ChatMessage(
        conversation_id=conversation_id,
        sender=sender,
        content=content or "",
        status=status,
        metadata_json=metadata or {},
        created_at=_utcnow(),
    )
    db.session.add(msg)

    conv = db.session.get(Conversation, conversation_id)
    if conv:
        conv.updated_at = _utcnow()
        if msg not in conv.messages:
            conv.messages.append(msg)
        if conv.title in ("New Conversation", "New Chat") and sender == "user" and content:
            auto_title_conversation(conv, content)

    db.session.commit()
    db.session.expire_all()
    return msg


def update_message(
    message_id: int,
    content: Optional[str] = None,
    status: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[ChatMessage]:
    """Update message content, status, or metadata."""
    msg = db.session.get(ChatMessage, message_id)
    if not msg:
        return None

    if content is not None:
        msg.content = content
    if status is not None:
        msg.status = status
    if metadata is not None:
        existing = dict(msg.metadata_json or {})
        existing.update(metadata)
        msg.metadata_json = existing

    db.session.commit()
    return msg


def auto_title_conversation(conversation: Conversation, prompt: str) -> None:
    """Generate a clean, readable conversation title from the first prompt."""
    cleaned = re.sub(r"[^\w\s-]", "", prompt).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    words = cleaned.split(" ")
    if len(words) > 6:
        title = " ".join(words[:6]).title() + "..."
    elif words and words[0]:
        title = " ".join(words).title()
    else:
        title = "Conversation"

    conversation.title = title[:60]
