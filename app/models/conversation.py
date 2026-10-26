"""
Conversation and ChatMessage models.

Provides persistent multi-turn chat history for Chat Assistant and specialized
agent workspaces, scoped by authenticated user and agent type.
"""

import uuid
from datetime import datetime, timezone
from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conversation(db.Model):
    """A persistent multi-turn conversation thread."""

    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    agent_type = db.Column(db.String(50), nullable=False, default="chat_assistant", index=True)
    title = db.Column(db.String(255), nullable=False, default="New Conversation")
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    messages = db.relationship(
        "ChatMessage",
        backref="conversation",
        lazy="joined",
        order_by="ChatMessage.created_at.asc()",
        cascade="all, delete-orphan",
    )
    user = db.relationship("User", backref=db.backref("conversations", lazy="dynamic"))

    def to_dict(self, include_messages=False):
        data = {
            "id": self.public_id,
            "public_id": self.public_id,
            "title": self.title,
            "agent_type": self.agent_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages] if self.messages else []
        return data


class ChatMessage(db.Model):
    """An individual message in a conversation."""

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), index=True, nullable=False)
    sender = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="completed")  # 'completed', 'error', 'pending'
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self):
        meta = self.metadata_json or {}
        return {
            "id": self.public_id,
            "public_id": self.public_id,
            "sender": self.sender,
            "text": self.content,
            "content": self.content,
            "status": self.status,
            "timestamp": self.created_at.strftime("%I:%M %p") if self.created_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "attachedFileName": meta.get("attachedFileName"),
            "file_id": meta.get("file_id"),
            "isTask": meta.get("isTask"),
            "orchestrationId": meta.get("orchestrationId"),
            "tasks": meta.get("tasks"),
            "sources": meta.get("sources"),
            "requiresApproval": meta.get("requiresApproval"),
            "approval": meta.get("approval"),
            "imageUrl": meta.get("imageUrl"),
            "imageMeta": meta.get("imageMeta"),
        }
