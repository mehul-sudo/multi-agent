"""
ProviderConfig model.

Managed database model for LLM provider configurations, models, pricing, limits,
and secret references (API key references).
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProviderConfig(db.Model):
    """Configuration for an LLM provider."""

    __tablename__ = "provider_configs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=True)  # Nullable for system-wide default providers
    provider_name = db.Column(db.String(50), nullable=False)  # openai, anthropic, gemini, mock, local
    display_name = db.Column(db.String(100), nullable=True)

    secret_key_ref = db.Column(db.String(255), nullable=True)  # Reference/alias to secret, NOT raw API key
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    available_models = db.Column(db.JSON, nullable=False, default=list)  # List of model names or model detail dicts
    default_model = db.Column(db.String(100), nullable=True)

    model_capabilities = db.Column(db.JSON, nullable=False, default=dict)  # streaming, structured_output, vision, tool_calling
    context_window_limits = db.Column(db.JSON, nullable=False, default=dict)
    rate_limits = db.Column(db.JSON, nullable=False, default=dict)  # requests_per_minute, tokens_per_minute
    cost_per_1k_tokens = db.Column(db.JSON, nullable=False, default=dict)  # prompt, completion

    fallback_priority = db.Column(db.Integer, nullable=False, default=10)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("provider_configs", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<ProviderConfig provider={self.provider_name} active={self.is_active}>"
