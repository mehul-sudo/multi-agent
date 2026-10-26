"""
Tests for Phase 10 Sliding-Window Rate Limiting.
"""

import pytest
from app.services.rate_limit_service import RateLimitService


def test_rate_limit_counter_and_blocking(db_session):
    test_key = "user_test_rate_limit_123"

    # Allow max 3 requests per window
    allowed1, remaining1, reset1 = RateLimitService.check_rate_limit(
        key=test_key, endpoint_category="test_ep", max_requests=3, window_seconds=60
    )
    assert allowed1 is True
    assert remaining1 == 2

    allowed2, remaining2, reset2 = RateLimitService.check_rate_limit(
        key=test_key, endpoint_category="test_ep", max_requests=3, window_seconds=60
    )
    assert allowed2 is True
    assert remaining2 == 1

    allowed3, remaining3, reset3 = RateLimitService.check_rate_limit(
        key=test_key, endpoint_category="test_ep", max_requests=3, window_seconds=60
    )
    assert allowed3 is True
    assert remaining3 == 0

    # 4th request exceeds limit -> Blocked
    allowed4, remaining4, reset4 = RateLimitService.check_rate_limit(
        key=test_key, endpoint_category="test_ep", max_requests=3, window_seconds=60
    )
    assert allowed4 is False
    assert remaining4 == 0
    assert reset4 > 0
