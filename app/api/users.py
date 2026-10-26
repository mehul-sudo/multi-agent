"""
User API endpoints.

Authentication & authorization:
  - ``POST ""`` (create_user) is intentionally public so new accounts can
    self-register. Role/is_active/is_verified are never accepted from the
    client - safe defaults are always applied.
  - All other endpoints require a valid JWT (``@jwt_required``). Read and
    update are restricted to the account owner or an administrator; listing
    and deactivation are administrator-only. ``current_user`` is resolved by
    the JWT user-lookup loader registered in app/extensions.py.

Route handlers only translate between HTTP and the service layer
(app/services/user_service.py) - no direct database queries happen
here.
"""

from pydantic import ValidationError
from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.models.user import ROLE_ADMIN, ROLE_PLATFORM_ADMIN
from app.schemas.user import UserCreateSchema, UserResponseSchema, UserUpdateSchema
from app.services import user_service
from app.utils.errors import error_response

users_bp = Blueprint("users", __name__)


def _serialize_user(user) -> dict:
    return UserResponseSchema.model_validate(user).model_dump(mode="json")


def _is_admin(user) -> bool:
    """True when the authenticated user holds an administrative platform role."""
    return user is not None and user.role in (ROLE_ADMIN, ROLE_PLATFORM_ADMIN)


def _validation_error_message(exc: ValidationError) -> str:
    """Collapse a Pydantic ValidationError into one readable message
    without leaking internal schema/library details.
    """
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first.get("loc", ())) or "input"
    return f"{field}: {first.get('msg', 'invalid value')}"


@users_bp.route("", methods=["POST"])
def create_user():
    """Create a new user account (public self-registration).

    Role, is_active, and is_verified are never accepted from the
    client - defaults (user / True / False) are always applied.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(
            "VALIDATION_ERROR", "Request body must be valid JSON.", 400
        )

    try:
        data = UserCreateSchema.model_validate(payload)
    except ValidationError as exc:
        return error_response(
            "VALIDATION_ERROR", _validation_error_message(exc), 400
        )

    try:
        user = user_service.create_user(
            username=data.username,
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
        )
    except user_service.DuplicateUsernameError as exc:
        return error_response("DUPLICATE_USERNAME", str(exc), 409)
    except user_service.DuplicateEmailError as exc:
        return error_response("DUPLICATE_EMAIL", str(exc), 409)

    return jsonify(_serialize_user(user)), 201


@users_bp.route("/<public_id>", methods=["GET"])
@jwt_required()
def get_user(public_id):
    """Fetch one user by public UUID.

    A non-admin caller may only read their own record; administrators may
    read any user. The ownership check runs before the existence lookup so
    a non-admin cannot probe which public_ids exist.
    """
    if not _is_admin(current_user) and current_user.public_id != public_id:
        return error_response(
            "FORBIDDEN", "You are not allowed to access this user.", 403
        )

    user = user_service.find_by_public_id(public_id)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    return jsonify(_serialize_user(user)), 200


@users_bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    """List users with pagination. Administrator-only.

    Query params: page (default 1), per_page (default 20, capped at 100).
    """
    if not _is_admin(current_user):
        return error_response(
            "FORBIDDEN", "Administrator privileges are required to list users.", 403
        )

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        return error_response("VALIDATION_ERROR", "page must be an integer.", 400)

    try:
        per_page = int(request.args.get("per_page", user_service.DEFAULT_PER_PAGE))
    except ValueError:
        return error_response(
            "VALIDATION_ERROR", "per_page must be an integer.", 400
        )

    if page < 1 or per_page < 1:
        return error_response(
            "VALIDATION_ERROR", "page and per_page must be positive integers.", 400
        )

    result = user_service.list_users(page=page, per_page=per_page)

    return (
        jsonify(
            {
                "users": [_serialize_user(u) for u in result.users],
                "page": result.page,
                "per_page": result.per_page,
                "total": result.total,
                "pages": result.pages,
            }
        ),
        200,
    )


@users_bp.route("/<public_id>", methods=["PATCH"])
@jwt_required()
def update_user(public_id):
    """Update safe profile fields only. Owner or administrator.

    role, password_hash, is_active, is_verified, public_id,
    created_at, and updated_at can never be changed through this
    endpoint, regardless of what the request body contains.
    """
    if not _is_admin(current_user) and current_user.public_id != public_id:
        return error_response(
            "FORBIDDEN", "You are not allowed to modify this user.", 403
        )

    user = user_service.find_by_public_id(public_id)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(
            "VALIDATION_ERROR", "Request body must be valid JSON.", 400
        )

    try:
        data = UserUpdateSchema.model_validate(payload)
    except ValidationError as exc:
        return error_response(
            "VALIDATION_ERROR", _validation_error_message(exc), 400
        )

    try:
        updated = user_service.update_profile(
            user,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
        )
    except user_service.DuplicateUsernameError as exc:
        return error_response("DUPLICATE_USERNAME", str(exc), 409)

    return jsonify(_serialize_user(updated)), 200


@users_bp.route("/<public_id>", methods=["DELETE"])
@jwt_required()
def deactivate_user(public_id):
    """Soft-deactivate a user (is_active=False). Administrator-only.

    Does not delete the record.
    """
    if not _is_admin(current_user):
        return error_response(
            "FORBIDDEN", "Administrator privileges are required to deactivate users.", 403
        )

    user = user_service.find_by_public_id(public_id)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found.", 404)

    updated = user_service.deactivate_user(user)

    return jsonify(_serialize_user(updated)), 200
