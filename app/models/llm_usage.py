"""
LLM Usage Log Model.

Tracks token usage, costs, durations, and provider metrics across tasks and workflows.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LLMUsageLog(db.Model):
    """LLM execution token usage and cost log."""

    __tablename__ = "llm_usage_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), index=True, nullable=True)
    workflow_execution_id = db.Column(db.Integer, db.ForeignKey("workflow_executions.id", ondelete="CASCADE"), index=True, nullable=True)
    task_execution_id = db.Column(db.Integer, db.ForeignKey("task_executions.id", ondelete="CASCADE"), index=True, nullable=True)

    provider = db.Column(db.String(50), index=True, nullable=False)
    model = db.Column(db.String(100), index=True, nullable=False)

    prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
    completion_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)

    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    estimated_cost_usd = db.Column(db.Float, nullable=True)

    success = db.Column(db.Boolean, nullable=False, default=True)
    error_category = db.Column(db.String(100), nullable=True)
    fallback_used = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("llm_usage_logs", lazy="dynamic"))
    agent = db.relationship("Agent", backref=db.backref("llm_usage_logs", lazy="dynamic"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LLMUsageLog provider={self.provider} model={self.model} total_tokens={self.total_tokens}>"
