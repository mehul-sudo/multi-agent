"""Tests for application creation and the /api/health endpoint.

These tests do not require a real database or LLM API - the app
factory in this phase does not depend on either.
"""


def test_app_creation_returns_flask_app(app):
    """create_app() should return a usable Flask app in testing mode."""
    assert app is not None
    assert app.config["TESTING"] is True


def test_health_endpoint_status_code(client):
    """GET /api/health should return HTTP 200."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_endpoint_json_body(client):
    """GET /api/health should return the expected JSON payload."""
    response = client.get("/api/health")
    data = response.get_json()

    assert data == {
        "status": "ok",
        "service": "multi-agent-ai-assistant",
        "version": "0.1.0",
    }


def test_health_endpoint_content_type(client):
    """The health endpoint should respond with JSON content type."""
    response = client.get("/api/health")
    assert response.content_type == "application/json"
