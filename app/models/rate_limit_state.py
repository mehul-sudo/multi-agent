"""
Rate Limit State model.

Stores sliding window request counts for rate limiting enforcement
per key (user_id, IP address, organization_id, endpoint).
"""

from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RateLimitState(db.Model):
    """Database-backed sliding window rate limit counter."""

    __tablename__ = "rate_limit_state"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(255), nullable=False, index=True)
    endpoint = db.Column(db.String(128), nullable=False, index=True)

    request_count = db.Column(db.Integer, nullable=False, default=1)
    window_start = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    def __repr__(self) -> str:
        return (
            f"<RateLimitState key={self.key!r} endpoint={self.endpoint!r} count={self.request_count}>"
        )
