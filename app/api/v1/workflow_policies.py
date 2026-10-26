"""
Workflow Security Policies API Blueprint.

Provides endpoints for creating, listing, viewing, and deleting workflow policies.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.extensions import db
from app.models.permission import PERM_POLICY_MANAGE
from app.models.workflow_policy import WorkflowPolicy
from app.services.permission_service import PermissionService, require_permission

bp = Blueprint("workflow_policies", __name__, url_prefix="/workflow-policies")


@bp.route("", methods=["POST"])
@jwt_required()
@require_permission(PERM_POLICY_MANAGE)
def create_policy():
    """Create a workflow security policy."""
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "Validation error", "message": "name is required"}), 400

    policy = WorkflowPolicy(
        name=name,
        description=data.get("description"),
        organization_id=data.get("organization_id"),
        workflow_id=data.get("workflow_id"),
        created_by_user_id=current_user.id,
        max_duration_seconds=data.get("max_duration_seconds", 3600),
        max_retry_count=data.get("max_retry_count", 3),
        max_parallelism=data.get("max_parallelism", 5),
        token_budget=data.get("token_budget", 100000),
        require_human_approval=data.get("require_human_approval", False),
        allow_external_side_effects=data.get("allow_external_side_effects", True),
        allow_scheduled_execution=data.get("allow_scheduled_execution", True),
        allow_automatic_execution=data.get("allow_automatic_execution", True),
        allowed_tools=data.get("allowed_tools"),
        denied_tools=data.get("denied_tools"),
    )
    db.session.add(policy)
    db.session.commit()

    return jsonify({
        "message": "Workflow policy created successfully",
        "policy": {
            "public_id": policy.public_id,
            "name": policy.name,
            "organization_id": policy.organization_id,
            "workflow_id": policy.workflow_id,
            "require_human_approval": policy.require_human_approval,
            "max_retry_count": policy.max_retry_count,
            "max_duration_seconds": policy.max_duration_seconds,
            "is_active": policy.is_active,
        }
    }), 201


@bp.route("", methods=["GET"])
@jwt_required()
@require_permission(PERM_POLICY_MANAGE)
def list_policies():
    """List workflow security policies."""
    query = WorkflowPolicy.query.filter_by(is_active=True)
    policies = query.all()
    return jsonify({
        "policies": [
            {
                "public_id": p.public_id,
                "name": p.name,
                "organization_id": p.organization_id,
                "workflow_id": p.workflow_id,
                "require_human_approval": p.require_human_approval,
                "max_retry_count": p.max_retry_count,
                "max_duration_seconds": p.max_duration_seconds,
                "is_active": p.is_active,
            }
            for p in policies
        ]
    }), 200


@bp.route("/<public_id>", methods=["GET"])
@jwt_required()
@require_permission(PERM_POLICY_MANAGE)
def get_policy(public_id):
    """Fetch policy details."""
    policy = WorkflowPolicy.query.filter_by(public_id=public_id, is_active=True).first()
    if not policy:
        return jsonify({"error": "Not Found", "message": "Policy not found"}), 404

    return jsonify({
        "policy": {
            "public_id": policy.public_id,
            "name": policy.name,
            "description": policy.description,
            "organization_id": policy.organization_id,
            "workflow_id": policy.workflow_id,
            "created_by_user_id": policy.created_by_user_id,
            "max_duration_seconds": policy.max_duration_seconds,
            "max_retry_count": policy.max_retry_count,
            "max_parallelism": policy.max_parallelism,
            "token_budget": policy.token_budget,
            "require_human_approval": policy.require_human_approval,
            "allow_external_side_effects": policy.allow_external_side_effects,
            "allow_scheduled_execution": policy.allow_scheduled_execution,
            "allowed_tools": policy.allowed_tools,
            "denied_tools": policy.denied_tools,
            "is_active": policy.is_active,
        }
    }), 200
