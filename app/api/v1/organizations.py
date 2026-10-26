"""
Organizations API Blueprint.

Provides organization tenant CRUD, member listing, member invitation,
role updating, and member removal endpoints.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.models.permission import PERM_ORG_MANAGE, PERM_ORG_MEMBER_MANAGE
from app.services.organization_service import OrganizationService
from app.services.permission_service import require_permission

bp = Blueprint("organizations", __name__, url_prefix="/organizations")


@bp.route("", methods=["POST"])
@jwt_required()
def create_organization():
    """Create a new organization."""
    data = request.get_json() or {}
    name = data.get("name")
    slug = data.get("slug")
    if not name or not slug:
        return jsonify({"error": "Validation error", "message": "name and slug are required"}), 400

    try:
        org = OrganizationService.create_organization(
            name=name,
            slug=slug,
            owner_user_id=current_user.id,
            description=data.get("description"),
            max_members=data.get("max_members", 50),
            max_workflows=data.get("max_workflows", 100),
            max_agents=data.get("max_agents", 20),
        )
        return jsonify({
            "message": "Organization created successfully",
            "organization": {
                "public_id": org.public_id,
                "name": org.name,
                "slug": org.slug,
                "description": org.description,
                "owner_user_id": org.owner_user_id,
                "created_at": org.created_at.isoformat() if org.created_at else None,
            }
        }), 201
    except ValueError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400


@bp.route("", methods=["GET"])
@jwt_required()
def list_user_organizations():
    """List organizations the user belongs to."""
    orgs = OrganizationService.list_user_organizations(current_user.id)
    return jsonify({
        "organizations": [
            {
                "public_id": o.public_id,
                "name": o.name,
                "slug": o.slug,
                "description": o.description,
                "owner_user_id": o.owner_user_id,
                "is_active": o.is_active,
            }
            for o in orgs
        ]
    }), 200


@bp.route("/<public_id>", methods=["GET"])
@jwt_required()
def get_organization(public_id):
    """Fetch organization details."""
    org = OrganizationService.get_organization_by_public_id(public_id)
    if not org:
        return jsonify({"error": "Not Found", "message": "Organization not found"}), 404

    if not OrganizationService.validate_tenant_access(current_user.id, org.id):
        return jsonify({"error": "Forbidden", "message": "Access denied to organization tenant"}), 403

    return jsonify({
        "organization": {
            "public_id": org.public_id,
            "name": org.name,
            "slug": org.slug,
            "description": org.description,
            "owner_user_id": org.owner_user_id,
            "max_members": org.max_members,
            "max_workflows": org.max_workflows,
            "max_agents": org.max_agents,
            "created_at": org.created_at.isoformat() if org.created_at else None,
        }
    }), 200


@bp.route("/<public_id>/members", methods=["POST"])
@jwt_required()
def add_member(public_id):
    """Add a user member to an organization."""
    org = OrganizationService.get_organization_by_public_id(public_id)
    if not org:
        return jsonify({"error": "Not Found", "message": "Organization not found"}), 404

    if not OrganizationService.validate_tenant_access(current_user.id, org.id):
        return jsonify({"error": "Forbidden", "message": "Access denied to organization tenant"}), 403

    data = request.get_json() or {}
    user_id = data.get("user_id")
    org_role = data.get("org_role", "member")
    if not user_id:
        return jsonify({"error": "Validation error", "message": "user_id is required"}), 400

    try:
        member = OrganizationService.add_member(org.id, user_id, org_role=org_role)
        return jsonify({
            "message": "Member added successfully",
            "member": {
                "organization_id": member.organization_id,
                "user_id": member.user_id,
                "org_role": member.org_role,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            }
        }), 201
    except ValueError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400


@bp.route("/<public_id>/members/<int:user_id>", methods=["DELETE"])
@jwt_required()
def remove_member(public_id, user_id):
    """Remove a user member from an organization."""
    org = OrganizationService.get_organization_by_public_id(public_id)
    if not org:
        return jsonify({"error": "Not Found", "message": "Organization not found"}), 404

    if not OrganizationService.validate_tenant_access(current_user.id, org.id):
        return jsonify({"error": "Forbidden", "message": "Access denied to organization tenant"}), 403

    try:
        removed = OrganizationService.remove_member(org.id, user_id)
        if not removed:
            return jsonify({"error": "Not Found", "message": "Member not found"}), 404
        return jsonify({"message": "Member removed successfully"}), 200
    except ValueError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400
