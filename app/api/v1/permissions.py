"""
Permissions API Blueprint.

Provides endpoints to inspect permissions, assigned roles, and RBAC rules.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.models.permission import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.services.permission_service import PermissionService

bp = Blueprint("permissions", __name__, url_prefix="/permissions")


@bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_permissions():
    """Return current authenticated user's permissions and roles."""
    org_id_param = request.args.get("organization_id")
    org_id = int(org_id_param) if org_id_param and org_id_param.isdigit() else None

    perms = PermissionService.get_user_permissions(current_user, organization_id=org_id)
    return jsonify({
        "user_id": current_user.id,
        "public_id": current_user.public_id,
        "platform_role": current_user.role,
        "organization_id": org_id,
        "permissions": sorted(list(perms)),
    }), 200


@bp.route("/roles", methods=["GET"])
@jwt_required()
def list_supported_roles():
    """List system supported RBAC roles and their associated permission sets."""
    formatted_roles = {
        role: sorted(list(perms)) for role, perms in ROLE_PERMISSIONS.items()
    }
    return jsonify({
        "roles": formatted_roles,
        "all_permissions": sorted(list(ALL_PERMISSIONS)),
    }), 200
