"""
Tool Policies API Blueprint.

Provides endpoints to create, view, list, and delete tool security policies.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.extensions import db
from app.models.permission import PERM_TOOL_POLICY_MANAGE
from app.models.tool_policy import ToolPolicy
from app.services.permission_service import require_permission

bp = Blueprint("tool_policies", __name__, url_prefix="/tool-policies")


@bp.route("", methods=["POST"])
@jwt_required()
@require_permission(PERM_TOOL_POLICY_MANAGE)
def create_tool_policy():
    """Create a tool security policy."""
    data = request.get_json() or {}
    name = data.get("name")
    tool_name = data.get("tool_name")
    if not name or not tool_name:
        return jsonify({"error": "Validation error", "message": "name and tool_name are required"}), 400

    policy = ToolPolicy(
        name=name,
        description=data.get("description"),
        tool_name=tool_name,
        organization_id=data.get("organization_id"),
        created_by_user_id=current_user.id,
        is_dangerous=data.get("is_dangerous", False),
        require_approval=data.get("require_approval", False),
        timeout_seconds=data.get("timeout_seconds", 60),
        max_invocations_per_hour=data.get("max_invocations_per_hour", 1000),
        allowed_domains=data.get("allowed_domains"),
        denied_patterns=data.get("denied_patterns"),
    )
    db.session.add(policy)
    db.session.commit()

    return jsonify({
        "message": "Tool policy created successfully",
        "policy": {
            "public_id": policy.public_id,
            "name": policy.name,
            "tool_name": policy.tool_name,
            "is_dangerous": policy.is_dangerous,
            "require_approval": policy.require_approval,
            "timeout_seconds": policy.timeout_seconds,
            "is_active": policy.is_active,
        }
    }), 201


@bp.route("", methods=["GET"])
@jwt_required()
@require_permission(PERM_TOOL_POLICY_MANAGE)
def list_tool_policies():
    """List all active tool policies."""
    policies = ToolPolicy.query.filter_by(is_active=True).all()
    return jsonify({
        "policies": [
            {
                "public_id": p.public_id,
                "name": p.name,
                "tool_name": p.tool_name,
                "is_dangerous": p.is_dangerous,
                "require_approval": p.require_approval,
                "timeout_seconds": p.timeout_seconds,
                "allowed_domains": p.allowed_domains,
                "is_active": p.is_active,
            }
            for p in policies
        ]
    }), 200
