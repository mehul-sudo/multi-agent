"""
Comprehensive tests for the /api/auth endpoints (Phase 4).

Tests cover all authentication scenarios:
  - POST /api/auth/login
  - POST /api/auth/refresh
  - POST /api/auth/logout
  - GET  /api/auth/me
  - POST /api/auth/change-password

Verifies:
  - Successful happy paths
  - Every documented error condition
  - Token type enforcement
  - Revoked token rejection
  - Password security (hash never returned, old hash invalidated)
  - Existing phase tests still pass (regression)
"""

import json
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token

from app import create_app
from app.extensions import db
from app.models.user import User
from app.security.password import hash_password, verify_password
from app.services import user_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_USER = {
    "username": "authuser",
    "email": "authuser@example.com",
    "password": "SecurePass1!",
    "first_name": "Auth",
    "last_name": "User",
}


def _register(client, **overrides):
    """Create a user via the /api/users endpoint."""
    payload = dict(VALID_USER, **overrides)
    return client.post("/api/users", json=payload)


def _login(client, email=None, password=None):
    """POST /api/auth/login."""
    return client.post(
        "/api/auth/login",
        json={
            "email": email or VALID_USER["email"],
            "password": password or VALID_USER["password"],
        },
    )


def _auth_headers(token: str) -> dict:
    """Return Authorization header dict for a token."""
    return {"Authorization": f"Bearer {token}"}


def _setup_user_and_login(client):
    """Register a user and return (access_token, refresh_token, public_id)."""
    reg = _register(client)
    assert reg.status_code == 201
    body = _login(client).get_json()
    return body["access_token"], body["refresh_token"], reg.get_json()["public_id"]


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_success_returns_200(self, client):
        _register(client)
        response = _login(client)
        assert response.status_code == 200

    def test_login_returns_access_and_refresh_tokens(self, client):
        _register(client)
        body = _login(client).get_json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert isinstance(body["access_token"], str)
        assert isinstance(body["refresh_token"], str)

    def test_login_returns_safe_user_info(self, client):
        _register(client)
        body = _login(client).get_json()
        user = body["user"]
        assert "public_id" in user
        assert "username" in user
        assert user["email"] == VALID_USER["email"]
        assert user["role"] == "user"
        assert user["is_active"] is True

    def test_login_never_returns_password_hash(self, client):
        _register(client)
        body = _login(client).get_json()
        raw = json.dumps(body)
        assert "password_hash" not in raw
        assert "password" not in body.get("user", {})
        assert VALID_USER["password"] not in raw

    def test_login_wrong_password_returns_401(self, client):
        _register(client)
        response = _login(client, password="WrongPassword1!")
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_nonexistent_email_returns_401(self, client):
        response = _login(client, email="nobody@example.com")
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_wrong_and_nonexistent_same_error_message(self, client):
        """Ensure no account-existence leakage through differing messages."""
        _register(client)
        wrong_pass = _login(client, password="WrongPassword1!").get_json()
        no_account = _login(client, email="nobody@example.com").get_json()
        assert wrong_pass["error"]["message"] == no_account["error"]["message"]

    def test_login_missing_email_returns_400(self, client):
        response = client.post("/api/auth/login", json={"password": "SecurePass1!"})
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_login_missing_password_returns_400(self, client):
        response = client.post(
            "/api/auth/login", json={"email": "authuser@example.com"}
        )
        assert response.status_code == 400

    def test_login_invalid_email_format_returns_400(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": "not-an-email", "password": "SecurePass1!"},
        )
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_login_malformed_json_returns_400(self, client):
        response = client.post(
            "/api/auth/login",
            data="not-json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_login_no_json_body_returns_400(self, client):
        response = client.post("/api/auth/login")
        assert response.status_code == 400

    def test_login_inactive_user_returns_401(self, client, app):
        """Inactive users must be rejected even with correct credentials."""
        _register(client)
        with app.app_context():
            user = user_service.find_by_email(VALID_USER["email"])
            user_service.deactivate_user(user)

        response = _login(client)
        assert response.status_code == 401

    def test_login_updates_last_login_at(self, client, app):
        _register(client)
        with app.app_context():
            user_before = user_service.find_by_email(VALID_USER["email"])
            assert user_before.last_login_at is None

        _login(client)

        with app.app_context():
            user_after = user_service.find_by_email(VALID_USER["email"])
            assert user_after.last_login_at is not None

    def test_login_email_case_insensitive(self, client):
        _register(client)
        response = client.post(
            "/api/auth/login",
            json={"email": VALID_USER["email"].upper(), "password": VALID_USER["password"]},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

class TestRefresh:
    def test_refresh_returns_new_access_token(self, client):
        _register(client)
        body = _login(client).get_json()
        refresh_token = body["refresh_token"]

        response = client.post(
            "/api/auth/refresh",
            headers=_auth_headers(refresh_token),
        )
        assert response.status_code == 200
        new_body = response.get_json()
        assert "access_token" in new_body
        # New token should differ from original
        assert new_body["access_token"] != body["access_token"]

    def test_refresh_with_access_token_rejected(self, client):
        """Refresh endpoint must reject access tokens (wrong type)."""
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/refresh",
            headers=_auth_headers(access_token),
        )
        assert response.status_code == 422
        body = response.get_json()
        # Flask-JWT-Extended 4.7.1 routes WrongTokenError through
        # invalid_token_loader (returning TOKEN_INVALID), not a separate
        # wrong-type callback. The 422 status is the key signal.
        assert body["error"]["code"] in ("TOKEN_WRONG_TYPE", "TOKEN_INVALID")

    def test_refresh_without_token_returns_401(self, client):
        response = client.post("/api/auth/refresh")
        assert response.status_code == 401

    def test_refresh_with_invalid_token_returns_422(self, client):
        response = client.post(
            "/api/auth/refresh",
            headers=_auth_headers("not.a.valid.jwt"),
        )
        assert response.status_code == 422

    def test_refresh_with_malformed_header_returns_401(self, client):
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": "NotBearer tokenvalue"},
        )
        assert response.status_code == 401

    def test_refresh_with_expired_token(self, client, app):
        """An expired refresh token must be rejected."""
        _register(client)
        with app.app_context():
            # Create a refresh token that expired 1 second ago
            expired_refresh = create_refresh_token(
                identity="someuser",
                expires_delta=timedelta(seconds=-1),
            )
        response = client.post(
            "/api/auth/refresh",
            headers=_auth_headers(expired_refresh),
        )
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_EXPIRED"


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_success(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/logout",
            headers=_auth_headers(access_token),
        )
        assert response.status_code == 200
        assert "message" in response.get_json()

    def test_logout_token_cannot_be_reused(self, client):
        """After logout, the same token must be rejected."""
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        client.post("/api/auth/logout", headers=_auth_headers(access_token))

        # Attempt to use the revoked token again
        response = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_REVOKED"

    def test_logout_without_token_returns_401(self, client):
        response = client.post("/api/auth/logout")
        assert response.status_code == 401

    def test_logout_with_refresh_token_rejected(self, client):
        """Logout endpoint requires an access token, not a refresh token."""
        _register(client)
        refresh_token = _login(client).get_json()["refresh_token"]

        response = client.post(
            "/api/auth/logout",
            headers=_auth_headers(refresh_token),
        )
        assert response.status_code == 422
        # Flask-JWT-Extended 4.7.1 routes WrongTokenError through
        # invalid_token_loader (TOKEN_INVALID). 422 status is the signal.
        assert response.get_json()["error"]["code"] in ("TOKEN_WRONG_TYPE", "TOKEN_INVALID")

    def test_logout_with_invalid_token_returns_422(self, client):
        response = client.post(
            "/api/auth/logout",
            headers=_auth_headers("bad.token.value"),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def test_me_returns_user_profile(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert response.status_code == 200

        body = response.get_json()
        assert body["email"] == VALID_USER["email"]
        assert body["username"] == VALID_USER["username"]
        assert body["role"] == "user"
        assert body["is_active"] is True

    def test_me_never_returns_password_hash(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.get("/api/auth/me", headers=_auth_headers(access_token))
        raw = json.dumps(response.get_json())
        assert "password_hash" not in raw
        assert "password" not in response.get_json()

    def test_me_without_token_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_MISSING"

    def test_me_with_invalid_token_returns_422(self, client):
        response = client.get(
            "/api/auth/me",
            headers=_auth_headers("not.a.jwt"),
        )
        assert response.status_code == 422

    def test_me_with_refresh_token_rejected(self, client):
        """Me endpoint requires an access token."""
        _register(client)
        refresh_token = _login(client).get_json()["refresh_token"]

        response = client.get("/api/auth/me", headers=_auth_headers(refresh_token))
        assert response.status_code == 422
        # Flask-JWT-Extended 4.7.1: WrongTokenError → TOKEN_INVALID
        assert response.get_json()["error"]["code"] in ("TOKEN_WRONG_TYPE", "TOKEN_INVALID")

    def test_me_with_malformed_auth_header_returns_401(self, client):
        _register(client)
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Token notbearer"},
        )
        assert response.status_code == 401

    def test_me_with_expired_token_returns_401(self, client, app):
        _register(client)
        with app.app_context():
            expired_access = create_access_token(
                identity="someuser",
                expires_delta=timedelta(seconds=-1),
            )
        response = client.get("/api/auth/me", headers=_auth_headers(expired_access))
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_me_with_revoked_token_returns_401(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]
        client.post("/api/auth/logout", headers=_auth_headers(access_token))

        response = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_REVOKED"


# ---------------------------------------------------------------------------
# POST /api/auth/change-password
# ---------------------------------------------------------------------------

class TestChangePassword:
    def test_change_password_success(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )
        assert response.status_code == 200
        assert "message" in response.get_json()

    def test_change_password_old_password_no_longer_works(self, client):
        """After changing password, the old password must be rejected."""
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )

        # Try logging in with the old password
        response = _login(client, password=VALID_USER["password"])
        assert response.status_code == 401

    def test_change_password_new_password_works(self, client):
        """After changing password, the new password must be accepted."""
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )

        response = _login(client, password="NewSecurePass2!")
        assert response.status_code == 200

    def test_change_password_hash_changes(self, client, app):
        """The stored password hash must differ after a change."""
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        with app.app_context():
            user = user_service.find_by_email(VALID_USER["email"])
            original_hash = user.password_hash

        client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )

        with app.app_context():
            user = user_service.find_by_email(VALID_USER["email"])
            assert user.password_hash != original_hash

    def test_change_password_revokes_current_token(self, client):
        """The access token used for the change must be revoked afterward."""
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )

        # Same token should now be rejected
        response = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert response.status_code == 401

    def test_change_password_wrong_current_password(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": "WrongOldPassword!",
                "new_password": "NewSecurePass2!",
            },
        )
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_change_password_too_short_new_password(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "short",
            },
        )
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_change_password_missing_new_password(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={"current_password": VALID_USER["password"]},
        )
        assert response.status_code == 400

    def test_change_password_missing_current_password(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={"new_password": "NewSecurePass2!"},
        )
        assert response.status_code == 400

    def test_change_password_no_json_body(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
        )
        assert response.status_code == 400

    def test_change_password_without_token_returns_401(self, client):
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )
        assert response.status_code == 401

    def test_change_password_never_returns_hash(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )
        raw = json.dumps(response.get_json())
        assert "password_hash" not in raw
        assert "password" not in raw


# ---------------------------------------------------------------------------
# Token type enforcement - cross-endpoint checks
# ---------------------------------------------------------------------------

class TestTokenTypeEnforcement:
    def test_access_token_rejected_by_refresh_endpoint(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]
        response = client.post(
            "/api/auth/refresh", headers=_auth_headers(access_token)
        )
        assert response.status_code == 422
        # Flask-JWT-Extended 4.7.1: WrongTokenError → invalid_token_loader → TOKEN_INVALID
        assert response.get_json()["error"]["code"] in ("TOKEN_WRONG_TYPE", "TOKEN_INVALID")

    def test_refresh_token_rejected_by_me_endpoint(self, client):
        _register(client)
        refresh_token = _login(client).get_json()["refresh_token"]
        response = client.get("/api/auth/me", headers=_auth_headers(refresh_token))
        assert response.status_code == 422

    def test_refresh_token_rejected_by_logout_endpoint(self, client):
        _register(client)
        refresh_token = _login(client).get_json()["refresh_token"]
        response = client.post(
            "/api/auth/logout", headers=_auth_headers(refresh_token)
        )
        assert response.status_code == 422

    def test_refresh_token_rejected_by_change_password(self, client):
        _register(client)
        tokens = _login(client).get_json()
        refresh_token = tokens["refresh_token"]
        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(refresh_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Token blocklist / revocation
# ---------------------------------------------------------------------------

class TestTokenBlocklist:
    def test_revoked_access_token_rejected_on_me(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]
        client.post("/api/auth/logout", headers=_auth_headers(access_token))

        response = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "TOKEN_REVOKED"

    def test_revoked_access_token_rejected_on_change_password(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]
        client.post("/api/auth/logout", headers=_auth_headers(access_token))

        response = client.post(
            "/api/auth/change-password",
            headers=_auth_headers(access_token),
            json={
                "current_password": VALID_USER["password"],
                "new_password": "NewSecurePass2!",
            },
        )
        assert response.status_code == 401

    def test_two_tokens_can_be_independently_revoked(self, client):
        """Login twice; revoking token A should not affect token B."""
        _register(client)
        token_a = _login(client).get_json()["access_token"]
        token_b = _login(client).get_json()["access_token"]

        client.post("/api/auth/logout", headers=_auth_headers(token_a))

        # Token B should still work
        response = client.get("/api/auth/me", headers=_auth_headers(token_b))
        assert response.status_code == 200

        # Token A should be revoked
        response = client.get("/api/auth/me", headers=_auth_headers(token_a))
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Error response consistency
# ---------------------------------------------------------------------------

class TestErrorResponseFormat:
    """All error responses must use the standard error shape."""

    def _check_error_shape(self, response):
        body = response.get_json()
        assert body is not None, "Response must be JSON"
        assert "error" in body, f"Missing 'error' key in: {body}"
        assert "code" in body["error"], f"Missing 'code' key in: {body['error']}"
        assert "message" in body["error"], f"Missing 'message' in: {body['error']}"

    def test_missing_token_has_standard_shape(self, client):
        self._check_error_shape(client.get("/api/auth/me"))

    def test_invalid_token_has_standard_shape(self, client):
        self._check_error_shape(
            client.get("/api/auth/me", headers=_auth_headers("bad.jwt"))
        )

    def test_invalid_credentials_has_standard_shape(self, client):
        self._check_error_shape(
            client.post(
                "/api/auth/login",
                json={"email": "nobody@example.com", "password": "anything"},
            )
        )

    def test_validation_error_has_standard_shape(self, client):
        self._check_error_shape(
            client.post("/api/auth/login", json={"password": "only"})
        )

    def test_revoked_token_has_standard_shape(self, client):
        _register(client)
        access_token = _login(client).get_json()["access_token"]
        client.post("/api/auth/logout", headers=_auth_headers(access_token))
        self._check_error_shape(
            client.get("/api/auth/me", headers=_auth_headers(access_token))
        )


# ---------------------------------------------------------------------------
# Migration / database setup regression
# ---------------------------------------------------------------------------

class TestDatabaseSetup:
    def test_token_blocklist_table_created(self, app):
        """The token_blocklist table must exist in the test DB."""
        from sqlalchemy import inspect
        with app.app_context():
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
        assert "token_blocklist" in tables

    def test_token_blocklist_has_required_columns(self, app):
        from sqlalchemy import inspect
        with app.app_context():
            inspector = inspect(db.engine)
            columns = {c["name"] for c in inspector.get_columns("token_blocklist")}
        assert "jti" in columns
        assert "token_type" in columns
        assert "user_id" in columns
        assert "revoked_at" in columns
        assert "expires_at" in columns


# ---------------------------------------------------------------------------
# Regression: earlier-phase tests still pass
# ---------------------------------------------------------------------------

class TestRegressionEarlierPhases:
    def test_health_endpoint_still_works(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

    def test_users_create_still_works(self, client):
        response = _register(client)
        assert response.status_code == 201

    def test_jwt_extension_registered(self, app):
        assert "flask-jwt-extended" in app.extensions

    def test_sqlalchemy_extension_registered(self, app):
        assert "sqlalchemy" in app.extensions

    def test_migrate_extension_registered(self, app):
        assert "migrate" in app.extensions
