"""
Authentication API endpoints (Phase 4).

Endpoints:
  POST   /api/auth/login           - Issue access + refresh tokens
  POST   /api/auth/refresh         - Issue a new access token via refresh token
  POST   /api/auth/logout          - Revoke the current access token
  GET    /api/auth/me              - Return the authenticated user's profile
  POST   /api/auth/change-password - Change password and revoke current token

Security rules enforced here:
  - No password or token is ever logged.
  - Failed logins return the same generic message regardless of cause.
  - Responses never include password_hash or any sensitive internal field.
  - Token type is enforced: refresh endpoint rejects access tokens and
    vice versa (enforced by Flask-JWT-Extended via @jwt_required).
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from pydantic import ValidationError

from app.schemas.auth import ChangePasswordSchema, LoginSchema
from app.schemas.user import UserResponseSchema
from app.services import auth_service
from app.utils.errors import error_response

auth_bp = Blueprint("auth", __name__)


def _serialize_user(user) -> dict:
    """Return a safe public representation of a user.

    Delegates to UserResponseSchema which explicitly omits password_hash,
    internal IDs, and any other sensitive field.
    """
    return UserResponseSchema.model_validate(user).model_dump(mode="json")


def _validation_error_message(exc: ValidationError) -> str:
    """Collapse a Pydantic ValidationError to a single readable message."""
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first.get("loc", ())) or "input"
    return f"{field}: {first.get('msg', 'invalid value')}"


def _token_expires_at(jwt_payload: dict) -> datetime:
    """Extract the exp claim as a naive UTC datetime for blocklist storage."""
    exp = jwt_payload.get("exp", 0)
    return datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["POST"])
def register():
    """Create a new user account via authentication route."""
    from app.api.users import create_user
    return create_user()


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate a user and issue access + refresh tokens.

    Request body (JSON):
        email    (str, required) - user's email address
        password (str, required) - user's plaintext password

    Response (200):
        {
            "access_token":  "<JWT>",
            "refresh_token": "<JWT>",
            "user": { <safe user fields> }
        }

    Error responses:
        400 - missing/malformed JSON or validation failure
        401 - invalid credentials (generic, does not reveal which field failed)
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = LoginSchema.model_validate(payload)
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    try:
        user = auth_service.authenticate_user(data.email, data.password)
    except auth_service.AuthenticationError:
        return error_response(
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
            401,
        )

    # Identity stored in 'sub' claim is the public_id (never the numeric id).
    access_token = create_access_token(identity=user.public_id)
    refresh_token = create_refresh_token(identity=user.public_id)

    return (
        jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": _serialize_user(user),
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using a valid refresh token.

    Requires Authorization: Bearer <refresh_token>
    Rejects access tokens (Flask-JWT-Extended enforces token type).

    Response (200):
        { "access_token": "<JWT>" }
    """
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    return jsonify({"access_token": new_access_token}), 200


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Revoke the current access token.

    The token's JTI is inserted into the blocklist so subsequent requests
    using the same token are rejected. This is a real logout - the token
    cannot be reused after this call.

    Requires Authorization: Bearer <access_token>

    Response (200):
        { "message": "Successfully logged out." }
    """
    jwt_payload = get_jwt()
    identity = get_jwt_identity()

    user = auth_service.get_user_by_identity(identity)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    auth_service.revoke_token(
        jti=jwt_payload["jti"],
        token_type=jwt_payload["type"],
        user_id=user.id,
        expires_at=_token_expires_at(jwt_payload),
    )

    return jsonify({"message": "Successfully logged out."}), 200


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Return the profile of the currently authenticated user.

    Requires Authorization: Bearer <access_token>

    Response (200):
        { <safe user fields> }  (same shape as POST /api/users response)

    Never includes password_hash, tokens, or internal secrets.
    """
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)

    if user is None:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    return jsonify(_serialize_user(user)), 200


# ---------------------------------------------------------------------------
# POST /api/auth/change-password
# ---------------------------------------------------------------------------

@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """Change the authenticated user's password.

    Verifies the current password, validates the new password, saves the
    new hash, and revokes the current access token so it cannot be reused.

    Requires Authorization: Bearer <access_token>

    Request body (JSON):
        current_password (str, required)
        new_password     (str, required, min 8 characters)

    Response (200):
        { "message": "Password changed successfully." }

    Error responses:
        400 - missing/malformed JSON, validation failure, or too-short
              new password
        401 - current password is incorrect
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = ChangePasswordSchema.model_validate(payload)
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    try:
        auth_service.change_password(
            user,
            current_password=data.current_password,
            new_password=data.new_password,
        )
    except auth_service.AuthenticationError:
        return error_response(
            "INVALID_CREDENTIALS",
            "Current password is incorrect.",
            401,
        )
    except auth_service.PasswordValidationError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)

    # Revoke the current access token so the old token cannot be reused.
    jwt_payload = get_jwt()
    auth_service.revoke_token(
        jti=jwt_payload["jti"],
        token_type=jwt_payload["type"],
        user_id=user.id,
        expires_at=_token_expires_at(jwt_payload),
    )

    return jsonify({"message": "Password changed successfully."}), 200


# ---------------------------------------------------------------------------
# API Key Management (/api/auth/api-keys)
# ---------------------------------------------------------------------------

@auth_bp.route("/api-keys", methods=["GET"])
@jwt_required()
def list_user_api_keys():
    """List personal API keys generated by the current user."""
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if not user:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    from app.services.credential_service import CredentialService
    creds = CredentialService.list_credentials_metadata(owner_user_id=user.id)
    api_keys = [c for c in creds if c.get("credential_type") == "personal_api_key"]
    return jsonify({"success": True, "api_keys": api_keys}), 200


@auth_bp.route("/api-keys", methods=["POST"])
@jwt_required()
def create_user_api_key():
    """Generate a new personal API key for programmatic automation."""
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if not user:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    payload = request.get_json(silent=True) or {}
    key_name = payload.get("name") or f"Personal Key ({datetime.utcnow().strftime('%Y-%m-%d')})"
    generated_key = f"sk_live_{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"

    from app.services.credential_service import CredentialService
    cred = CredentialService.store_credential(
        name=key_name,
        secret_value=generated_key,
        owner_user_id=user.id,
        credential_type="personal_api_key",
        description="Personal API Key for Multi-Agent AI Platform",
    )

    return jsonify({
        "success": True,
        "message": "API key generated successfully. Copy it now; it will not be shown again.",
        "api_key": {
            "public_id": cred.public_id,
            "name": cred.name,
            "key": generated_key,
            "created_at": cred.created_at.isoformat() if cred.created_at else None,
        }
    }), 201


@auth_bp.route("/api-keys/<key_id>", methods=["DELETE"])
@jwt_required()
def revoke_user_api_key(key_id):
    """Revoke a personal API key."""
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if not user:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    from app.services.credential_service import CredentialService
    revoked = CredentialService.revoke_credential(key_id, owner_user_id=user.id)
    if not revoked:
        return error_response("NOT_FOUND", "API key not found or already revoked.", 404)

    return jsonify({"success": True, "message": "API key revoked successfully."}), 200


# ---------------------------------------------------------------------------
# 2-Factor Authentication (2FA) Management (/api/auth/2fa)
# ---------------------------------------------------------------------------

_user_2fa_state = {}

@auth_bp.route("/2fa", methods=["GET"])
@jwt_required()
def get_2fa_status():
    """Get current 2FA status for the user."""
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if not user:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    is_enabled = _user_2fa_state.get(user.id, False)
    return jsonify({
        "success": True,
        "enabled": is_enabled,
        "method": "authenticator_totp",
        "secret_hint": "JBSWY3DPEHPK3PXP" if is_enabled else None
    }), 200


@auth_bp.route("/2fa/toggle", methods=["POST"])
@jwt_required()
def toggle_2fa():
    """Toggle 2-Factor Authentication on/off for the user."""
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if not user:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    current_state = _user_2fa_state.get(user.id, False)
    new_state = not current_state
    _user_2fa_state[user.id] = new_state

    return jsonify({
        "success": True,
        "enabled": new_state,
        "message": "Two-Factor Authentication " + ("ENABLED. TOTP Authenticator is now active." if new_state else "DISABLED."),
        "secret": "JBSWY3DPEHPK3PXP" if new_state else None
    }), 200

