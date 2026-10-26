"""
Audit Logs API Blueprint.

Provides endpoints for tenant-isolated security audit event inspection.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.services.permission_service import PermissionService
from app.services.security_audit_service import SecurityAuditService

bp = Blueprint("audit_logs", __name__, url_prefix="/audit-logs")


@bp.route("", methods=["GET"])
@jwt_required()
def list_audit_logs():
    """Retrieve security audit events with tenant isolation and filtering."""
    org_id_param = request.args.get("organization_id")
    org_id = int(org_id_param) if org_id_param and org_id_param.isdigit() else None

    # Check permission
    if not PermissionService.has_permission(current_user, "audit:read", organization_id=org_id):
        return jsonify({"error": "Forbidden", "message": "Permission 'audit:read' required"}), 403

    event_type = request.args.get("event_type")
    resource_type = request.args.get("resource_type")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    events, total = SecurityAuditService.get_audit_logs(
        organization_id=org_id,
        user_id=current_user.id if not org_id else None,
        event_type=event_type,
        resource_type=resource_type,
        page=page,
        per_page=per_page,
    )

    return jsonify({
        "audit_logs": [
            {
                "public_id": e.public_id,
                "event_type": e.event_type,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "user_id": e.user_id,
                "organization_id": e.organization_id,
                "correlation_id": e.correlation_id,
                "ip_address": e.ip_address,
                "event_data": e.event_data,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
        }
    }), 200
