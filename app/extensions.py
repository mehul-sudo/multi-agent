"""
Flask extension instances.

Extensions are instantiated here (uninitialized) and bound to the app
inside the application factory via extension.init_app(app). This keeps
extension objects importable elsewhere (e.g. in blueprints or models)
without creating circular imports - modules can do
rom app.extensions import db freely, since db is not bound to any
particular app until create_app() calls db.init_app(app).

db: SQLAlchemy connection/ORM.
migrate: Flask-Migrate (Alembic) schema migrations, bound to db.
jwt: Flask-JWT-Extended, handles JWT token issuance and verification.
"""

from flask import jsonify
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def _make_error(code: str, message: str, status: int):
    """Produce the project-standard error response shape."""
    return jsonify({"error": {"code": code, "message": message}}), status


def register_jwt_callbacks(jwt_instance: JWTManager) -> None:
    """Register Flask-JWT-Extended error callbacks on a JWTManager instance.

    Called from the application factory after jwt.init_app(app) so the
    callbacks are bound to the correct app context. All callbacks follow
    the project-standard error shape:

        {"error": {"code": "...", "message": "..."}}

    Never logs tokens, Authorization headers, or secrets.
    """

    @jwt_instance.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return _make_error(
            "TOKEN_EXPIRED",
            "The token has expired. Please log in again.",
            401,
        )

    @jwt_instance.invalid_token_loader
    def invalid_token_callback(error_string):
        return _make_error(
            "TOKEN_INVALID",
            "The token is invalid.",
            422,
        )

    @jwt_instance.unauthorized_loader
    def missing_token_callback(error_string):
        return _make_error(
            "TOKEN_MISSING",
            "Authentication token is required.",
            401,
        )

    @jwt_instance.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return _make_error(
            "TOKEN_REVOKED",
            "The token has been revoked.",
            401,
        )

    @jwt_instance.needs_fresh_token_loader
    def fresh_token_required_callback(jwt_header, jwt_payload):
        return _make_error(
            "TOKEN_NOT_FRESH",
            "A fresh token is required.",
            401,
        )

    @jwt_instance.token_verification_failed_loader
    def wrong_token_callback(jwt_header, jwt_payload):
        return _make_error(
            "TOKEN_WRONG_TYPE",
            "Wrong token type provided for this endpoint.",
            422,
        )

    @jwt_instance.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Resolve the User for the token's identity so ``current_user`` works.

        The JWT identity ("sub" claim) is the user's public_id (never the
        internal numeric id). Returning None here causes the
        user_lookup_error_loader below to reject the request. Imported
        lazily to avoid a circular import at module load time.
        """
        from app.services import user_service

        identity = jwt_data.get("sub")
        if not identity:
            return None
        return user_service.find_by_public_id(identity)

    @jwt_instance.user_lookup_error_loader
    def user_lookup_error_callback(_jwt_header, _jwt_data):
        """Reject tokens whose identity no longer maps to a user.

        Fails closed (401) rather than leaking whether the account existed.
        """
        return _make_error(
            "USER_NOT_FOUND",
            "The user associated with this token could not be found.",
            401,
        )
