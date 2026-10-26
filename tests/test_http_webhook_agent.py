"""
Unit tests for HttpWebhookAgent.
"""

import pytest
from app.agents.base import AgentContext
from app.agents.http_webhook_agent import HttpWebhookAgent


def test_http_webhook_agent_post_executes_without_approval(monkeypatch):
    """Outbound HTTP POST must execute directly without human approval."""
    agent = HttpWebhookAgent()

    class MockRaw:
        def read(self, *args, **kwargs):
            return b'{"status": "created", "event": "user_signup"}'

    class MockResponse:
        status_code = 201
        headers = {"Content-Type": "application/json"}
        raw = MockRaw()
        def json(self):
            return {"status": "created", "event": "user_signup"}

    monkeypatch.setattr("requests.request", lambda **kwargs: MockResponse())

    ctx = AgentContext(
        input_data={
            "url": "https://httpbin.org/post",
            "method": "POST",
            "data": {"event": "user_signup"},
        },
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "http_webhook"
    assert result.requires_approval is False
    assert result.output["statusCode"] == 201
    assert result.output["status"] == "completed"
    assert result.output["data"] == {"status": "created", "event": "user_signup"}


def test_http_webhook_agent_blocks_ssrf_localhost():
    agent = HttpWebhookAgent()
    ctx = AgentContext(
        input_data={
            "url": "http://127.0.0.1:8080/admin/delete",
            "method": "GET",
        },
    )

    result = agent.execute(ctx)
    assert result.success is False
    assert "SSRF Security Violation" in result.error or "prohibited" in result.error


def test_http_webhook_agent_blocks_ssrf_cloud_metadata():
    agent = HttpWebhookAgent()
    ctx = AgentContext(
        input_data={
            "url": "http://169.254.169.254/latest/meta-data/",
            "method": "GET",
        },
    )

    result = agent.execute(ctx)
    assert result.success is False
    assert "SSRF Security Violation" in result.error


def test_http_webhook_agent_delete_executes_without_approval(monkeypatch):
    """Outbound HTTP DELETE must execute directly without human approval."""
    agent = HttpWebhookAgent()

    class MockRaw:
        def read(self, *args, **kwargs):
            return b'{"status": "deleted"}'

    class MockResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        raw = MockRaw()
        def json(self):
            return {"status": "deleted"}

    monkeypatch.setattr("requests.request", lambda **kwargs: MockResponse())

    ctx = AgentContext(
        input_data={
            "url": "https://httpbin.org/delete",
            "method": "DELETE",
        },
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert result.requires_approval is False
    assert result.output["statusCode"] == 200
    assert result.output["status"] == "completed"


def test_http_webhook_agent_get_read_only_executes_without_approval(monkeypatch):
    """Read-only HTTP GET must execute directly without human approval."""
    agent = HttpWebhookAgent()

    class MockRaw:
        def read(self, *args, **kwargs):
            return b'{"status": "ok", "users_count": 42}'

    class MockResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        raw = MockRaw()
        def json(self):
            return {"status": "ok", "users_count": 42}

    monkeypatch.setattr("requests.request", lambda **kwargs: MockResponse())

    ctx = AgentContext(
        input_data={
            "url": "https://api.example.com/v1/health",
            "method": "GET",
        },
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert result.requires_approval is False
    assert result.output["statusCode"] == 200
    assert result.output["data"] == {"status": "ok", "users_count": 42}
    assert result.output["status"] == "completed"


def test_http_webhook_agent_missing_url_fails():
    agent = HttpWebhookAgent()
    ctx = AgentContext(input_data={"method": "GET"})
    result = agent.execute(ctx)
    assert result.success is False
    assert "URL" in result.error


def test_http_webhook_agent_404_error(monkeypatch):
    agent = HttpWebhookAgent()

    class MockRaw404:
        def read(self, *args, **kwargs):
            return b"Not Found"

    class Mock404Response:
        status_code = 404
        headers = {"Content-Type": "text/plain"}
        raw = MockRaw404()
        def json(self):
            raise ValueError("Not JSON")

    monkeypatch.setattr("requests.request", lambda **kwargs: Mock404Response())

    ctx = AgentContext(
        input_data={
            "url": "https://api.example.com/missing-resource",
            "method": "GET",
        },
    )
    result = agent.execute(ctx)
    assert result.success is False
    assert result.output["statusCode"] == 404
    assert result.output["status"] == "HTTP 404"
    assert result.output["body"] == "Not Found"
    assert "404" in result.output["warnings"][0]


def test_http_webhook_agent_json_parsed_once_structured():
    """Verify that a valid JSON response is returned as an actual Python dict/list, never double-stringified."""
    agent = HttpWebhookAgent()

    class MockJsonResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        content = b'{"args": {}, "json": {"event": "test_event"}, "url": "https://httpbin.org/post"}'
        text = '{"args": {}, "json": {"event": "test_event"}, "url": "https://httpbin.org/post"}'
        def json(self):
            return {"args": {}, "json": {"event": "test_event"}, "url": "https://httpbin.org/post"}

    import requests
    original_req = requests.request
    try:
        requests.request = lambda **kwargs: MockJsonResponse()
        ctx = AgentContext(
            input_data={
                "url": "https://httpbin.org/post",
                "method": "POST",
                "data": {"event": "test_event"},
            }
        )
        res = agent.execute(ctx)
        assert res.success is True
        assert res.output["statusCode"] == 200
        assert res.output["is_json"] is True
        # Must be a real dict, not a string
        assert isinstance(res.output["data"], dict)
        assert isinstance(res.output["response_body"], dict)
        assert res.output["data"]["json"]["event"] == "test_event"
        # Must not contain escaped literal backslashes
        assert "\\n" not in str(type(res.output["data"]))
    finally:
        requests.request = original_req


def test_http_webhook_agent_plain_text_preserved():
    """Verify that non-JSON responses remain plain text without double quotes or escaped formatting."""
    agent = HttpWebhookAgent()

    class MockTextResponse:
        status_code = 200
        headers = {"Content-Type": "text/plain"}
        content = b"Health check passed: system operational."
        text = "Health check passed: system operational."
        def json(self):
            raise ValueError("Not JSON")

    import requests
    original_req = requests.request
    try:
        requests.request = lambda **kwargs: MockTextResponse()
        ctx = AgentContext(
            input_data={
                "url": "https://api.example.com/healthz",
                "method": "GET",
            }
        )
        res = agent.execute(ctx)
        assert res.success is True
        assert res.output["is_json"] is False
        assert isinstance(res.output["data"], str)
        assert res.output["data"] == "Health check passed: system operational."
    finally:
        requests.request = original_req


def test_http_webhook_agent_4xx_5xx_body_preserved():
    """Verify that 4xx/5xx responses preserve the actual body and status code without fake success."""
    agent = HttpWebhookAgent()

    class Mock500Response:
        status_code = 503
        headers = {"Content-Type": "application/json"}
        content = b'{"error": "Service Unavailable", "retry_after": 30}'
        text = '{"error": "Service Unavailable", "retry_after": 30}'
        def json(self):
            return {"error": "Service Unavailable", "retry_after": 30}

    import requests
    original_req = requests.request
    try:
        requests.request = lambda **kwargs: Mock500Response()
        ctx = AgentContext(
            input_data={
                "url": "https://api.example.com/service",
                "method": "GET",
            }
        )
        res = agent.execute(ctx)
        assert res.success is False
        assert res.output["statusCode"] == 503
        assert res.output["status"] == "HTTP 503"
        assert isinstance(res.output["data"], dict)
        assert res.output["data"]["error"] == "Service Unavailable"
    finally:
        requests.request = original_req

