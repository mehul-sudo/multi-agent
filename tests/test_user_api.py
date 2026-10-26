"""Tests for the /api/users endpoints."""

import json


def _create_user(client, **overrides):
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "s3curePass!",
        "first_name": "Alice",
        "last_name": "Anderson",
    }
    payload.update(overrides)
    return client.post("/api/users", json=payload)


def test_create_user_success(client):
    response = _create_user(client)
    assert response.status_code == 201

    body = response.get_json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["is_verified"] is False
    assert "public_id" in body


def test_create_user_response_never_contains_password(client):
    response = _create_user(client)
    body = response.get_json()

    assert "password" not in body
    assert "password_hash" not in body
    raw_text = json.dumps(body)
    assert "s3curePass!" not in raw_text


def test_create_user_rejects_invalid_email(client):
    response = _create_user(client, email="not-an-email")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_rejects_empty_username(client):
    response = _create_user(client, username="")
    assert response.status_code == 400


def test_create_user_rejects_too_short_username(client):
    """Username below the minimum length is invalid, not just an empty one."""
    response = _create_user(client, username="ab")
    assert response.status_code == 400


def test_create_user_rejects_weak_password(client):
    response = _create_user(client, password="short")
    assert response.status_code == 400


def test_create_user_rejects_empty_password(client):
    response = _create_user(client, password="")
    assert response.status_code == 400


def test_create_user_rejects_missing_password(client):
    response = client.post(
        "/api/users",
        json={"username": "bob", "email": "bob@example.com"},
    )
    assert response.status_code == 400


def test_create_user_rejects_duplicate_username(client):
    _create_user(client)
    response = _create_user(client, email="different@example.com")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DUPLICATE_USERNAME"


def test_create_user_rejects_duplicate_email(client):
    _create_user(client)
    response = _create_user(client, username="different-user")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DUPLICATE_EMAIL"


def test_create_user_cannot_set_role_or_flags(client):
    """Even if a client sends role/is_active/is_verified, they must be ignored."""
    response = _create_user(
        client,
        role="admin",
        is_active=False,
        is_verified=True,
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["is_verified"] is False


# ---------------------------------------------------------------------------
# Protected read/list/update/deactivate endpoints (require JWT + authorization)
# ---------------------------------------------------------------------------


def test_get_user_by_public_id(client, admin_auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.get(f"/api/users/{public_id}", headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.get_json()["username"] == "alice"


def test_get_user_unknown_public_id_returns_404(client, admin_auth_headers):
    response = client.get(
        "/api/users/00000000-0000-0000-0000-000000000000",
        headers=admin_auth_headers,
    )
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "USER_NOT_FOUND"


def test_get_user_requires_authentication(client):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.get(f"/api/users/{public_id}")
    assert response.status_code == 401


def test_get_self_allowed_for_non_admin(client, test_user, auth_headers):
    response = client.get(f"/api/users/{test_user.public_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["username"] == "testuser"


def test_get_other_user_forbidden_for_non_admin(client, auth_headers):
    create_response = _create_user(client)
    other_public_id = create_response.get_json()["public_id"]

    response = client.get(f"/api/users/{other_public_id}", headers=auth_headers)
    assert response.status_code == 403


def test_list_users_pagination(client, admin_auth_headers):
    for i in range(5):
        _create_user(
            client, username=f"user{i}", email=f"user{i}@example.com"
        )

    response = client.get("/api/users?page=1&per_page=2", headers=admin_auth_headers)
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["users"]) == 2
    assert body["page"] == 1
    assert body["per_page"] == 2
    # admin_auth_headers also creates one admin user, so total is the 5 created here + 1 admin.
    assert body["total"] == 6
    assert body["pages"] == 3


def test_list_users_excessive_per_page_is_capped(client, admin_auth_headers):
    _create_user(client)

    response = client.get("/api/users?per_page=99999", headers=admin_auth_headers)
    body = response.get_json()

    assert response.status_code == 200
    assert body["per_page"] == 100  # MAX_PER_PAGE


def test_list_users_requires_authentication(client):
    response = client.get("/api/users")
    assert response.status_code == 401


def test_list_users_forbidden_for_non_admin(client, auth_headers):
    response = client.get("/api/users", headers=auth_headers)
    assert response.status_code == 403


def test_update_user_changes_allowed_fields(client, admin_auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.patch(
        f"/api/users/{public_id}",
        json={"first_name": "Alicia", "last_name": "A."},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["first_name"] == "Alicia"
    assert body["last_name"] == "A."


def test_update_user_can_change_username_if_unique(client, admin_auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.patch(
        f"/api/users/{public_id}",
        json={"username": "alice_renamed"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["username"] == "alice_renamed"


def test_update_user_rejects_username_already_taken(client, admin_auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]
    _create_user(client, username="bob", email="bob@example.com")

    response = client.patch(
        f"/api/users/{public_id}",
        json={"username": "bob"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DUPLICATE_USERNAME"


def test_update_user_cannot_change_role(client, admin_auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.patch(
        f"/api/users/{public_id}",
        json={"role": "admin", "is_active": False, "first_name": "Alicia"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["first_name"] == "Alicia"


def test_update_self_allowed_for_non_admin(client, test_user, auth_headers):
    response = client.patch(
        f"/api/users/{test_user.public_id}",
        json={"first_name": "Testy"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["first_name"] == "Testy"


def test_update_other_user_forbidden_for_non_admin(client, auth_headers):
    create_response = _create_user(client)
    other_public_id = create_response.get_json()["public_id"]

    response = client.patch(
        f"/api/users/{other_public_id}",
        json={"first_name": "Nope"},
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_update_user_requires_authentication(client):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.patch(f"/api/users/{public_id}", json={"first_name": "X"})
    assert response.status_code == 401


def test_delete_user_performs_soft_deactivation(client, admin_auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.delete(f"/api/users/{public_id}", headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.get_json()["is_active"] is False

    # The record must still exist (soft delete, not a real delete).
    fetch_response = client.get(f"/api/users/{public_id}", headers=admin_auth_headers)
    assert fetch_response.status_code == 200
    assert fetch_response.get_json()["is_active"] is False


def test_delete_user_requires_authentication(client):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.delete(f"/api/users/{public_id}")
    assert response.status_code == 401


def test_deactivate_forbidden_for_non_admin(client, auth_headers):
    create_response = _create_user(client)
    public_id = create_response.get_json()["public_id"]

    response = client.delete(f"/api/users/{public_id}", headers=auth_headers)
    assert response.status_code == 403


def test_migration_setup_does_not_break_app_startup(app):
    """Flask-Migrate must be wired in without preventing normal app
    creation/startup - e.g. no exception at import/create_app time,
    and the extension is actually registered.
    """
    assert "migrate" in app.extensions


def test_existing_health_endpoint_still_works(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
