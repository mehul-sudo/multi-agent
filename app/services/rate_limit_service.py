"""
Rate Limiting Service.

Provides sliding-window rate limiting per user ID, IP address, organization ID,
and API endpoint. Returns rate limit headers (Limit, Remaining, Reset) and HTTP 429.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.extensions import db
from app.models.rate_limit_state import RateLimitState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RateLimitService:
    """Service for checking and recording rate limit counts."""

    DEFAULT_LIMITS = {
        "global": (100, 60),           # 100 requests per 60s
        "auth_login": (10, 60),        # 10 attempts per 60s
        "workflow_execute": (20, 60),  # 20 executions per 60s
        "schedule_create": (30, 60),   # 30 schedule creations per 60s
        "tool_invoke": (50, 60),       # 50 tool invocations per 60s
    }

    @classmethod
    def check_rate_limit(
        cls,
        key: str,
        endpoint_category: str = "global",
        max_requests: Optional[int] = None,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """Check if a request key has exceeded its allowed rate limit limit.
        
        Returns:
            Tuple[bool, int, int]: (is_allowed, remaining_requests, reset_after_seconds)
        """
        if max_requests is None:
            max_requests, window_seconds = cls.DEFAULT_LIMITS.get(
                endpoint_category, cls.DEFAULT_LIMITS["global"]
            )

        now = _utcnow()
        window_start_threshold = now - timedelta(seconds=window_seconds)

        # Clean old windows
        RateLimitState.query.filter(
            RateLimitState.key == key,
            RateLimitState.endpoint == endpoint_category,
            RateLimitState.window_start < window_start_threshold,
        ).delete(synchronize_session=False)
        db.session.commit()

        # Query current active window record
        record = RateLimitState.query.filter_by(
            key=key, endpoint=endpoint_category
        ).first()

        if not record:
            record = RateLimitState(
                key=key,
                endpoint=endpoint_category,
                request_count=1,
                window_start=now,
            )
            db.session.add(record)
            db.session.commit()
            return True, max_requests - 1, window_seconds

        if record.request_count >= max_requests:
            elapsed = (now - record.window_start).total_seconds()
            reset_after = max(1, int(window_seconds - elapsed))
            return False, 0, reset_after

        record.request_count += 1
        db.session.commit()
        remaining = max_requests - record.request_count
        elapsed = (now - record.window_start).total_seconds()
        reset_after = max(1, int(window_seconds - elapsed))

        return True, remaining, reset_after
