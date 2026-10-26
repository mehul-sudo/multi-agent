"""Tests for the database foundation added in Phase 2.

These tests only exercise SQLAlchemy wiring and the database health
utility - no models exist yet. Everything here runs against SQLite
(file-less, in-memory) so no running PostgreSQL server is required.
"""

from app import create_app
from app.extensions import db
from app.services.db_health import is_database_available


def test_sqlalchemy_is_initialized_on_app(app):
    """The db extension should be bound to the app's extensions map."""
    assert "sqlalchemy" in app.extensions


def test_testing_config_uses_sqlite_by_default(app):
    """Testing config must not require a real DATABASE_URL/PostgreSQL."""
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    assert uri.startswith("sqlite:")


def test_sqlalchemy_track_modifications_disabled(app):
    assert app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False


def test_database_available_with_sqlite(app):
    """A trivial query should succeed against the SQLite test database."""
    with app.app_context():
        assert is_database_available() is True


BAD_DATABASE_URI = "postgresql://baduser:badpass@localhost:1/doesnotexist"


def test_database_unavailable_with_bad_uri():
    """The utility must report unavailable (not raise) on a bad connection,
    and must never leak internal exception details.
    """
    # Injected via create_app's overrides hook (applied before
    # db.init_app runs) rather than mutated after the fact, since
    # Flask-SQLAlchemy binds the engine to the app at init_app() time
    # and refuses to be re-initialized on the same app afterwards.
    app = create_app(
        env_name="testing",
        overrides={"SQLALCHEMY_DATABASE_URI": BAD_DATABASE_URI},
    )

    with app.app_context():
        assert is_database_available() is False


def test_app_starts_without_database_url(monkeypatch):
    """The app must still be creatable when DATABASE_URL is not set at all
    (e.g. a fresh checkout with no .env configured yet).
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = create_app(env_name="testing")
    assert app is not None
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:")


def test_health_endpoint_still_passes_without_database(client):
    """The plain health endpoint must not depend on the database at all."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_health_database_endpoint_ok_with_sqlite(client):
    """GET /api/health/database should report available against SQLite."""
    response = client.get("/api/health/database")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "available"}


def test_health_database_endpoint_does_not_leak_details():
    """When the database is unavailable, the response must stay generic -
    no credentials, connection strings, or stack traces.
    """
    app = create_app(
        env_name="testing",
        overrides={"SQLALCHEMY_DATABASE_URI": BAD_DATABASE_URI},
    )
    client = app.test_client()
    response = client.get("/api/health/database")

    assert response.status_code == 503
    body = response.get_json()
    assert body == {"status": "error", "database": "unavailable"}
    assert "baduser" not in str(body)
    assert "badpass" not in str(body)
