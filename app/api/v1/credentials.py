"""
Credential Vault API Blueprint.

Provides endpoints for creating, listing, inspecting metadata, and revoking
encrypted credentials. Secret values are NEVER returned in API responses.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.models.permission import PERM_CREDENTIAL_DELETE, PERM_CREDENTIAL_READ, PERM_CREDENTIAL_WRITE
from app.services.credential_service import CredentialService

bp = Blueprint("credentials", __name__, url_prefix="/credentials")


@bp.route("", methods=["POST"])
@jwt_required()
def store_credential():
    """Store a secret encrypted at rest."""
    data = request.get_json() or {}
    name = data.get("name")
    secret_value = data.get("secret_value")
    credential_type = data.get("credential_type", "api_key")

    if not name or not secret_value:
        return jsonify({"error": "Validation error", "message": "name and secret_value are required"}), 400

    try:
        cred = CredentialService.store_credential(
            name=name,
            secret_value=secret_value,
            owner_user_id=current_user.id,
            credential_type=credential_type,
            description=data.get("description"),
            organization_id=data.get("organization_id"),
        )
        return jsonify({
            "message": "Credential stored securely",
            "credential": {
                "public_id": cred.public_id,
                "name": cred.name,
                "credential_type": cred.credential_type,
                "description": cred.description,
                "organization_id": cred.organization_id,
                "created_at": cred.created_at.isoformat() if cred.created_at else None,
            }
        }), 201
    except ValueError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400


@bp.route("", methods=["GET"])
@jwt_required()
def list_credentials():
    """List credential metadata. Secret values are NEVER returned."""
    org_id_param = request.args.get("organization_id")
    org_id = int(org_id_param) if org_id_param and org_id_param.isdigit() else None

    try:
        creds = CredentialService.list_credentials_metadata(
            owner_user_id=current_user.id, organization_id=org_id
        )
    except PermissionError as exc:
        return jsonify({"error": "Forbidden", "message": str(exc)}), 403

    return jsonify({"credentials": creds}), 200



@bp.route("/<public_id>", methods=["DELETE"])
@jwt_required()
def revoke_credential(public_id):
    """Revoke an encrypted credential."""
    revoked = CredentialService.revoke_credential(public_id, owner_user_id=current_user.id)
    if not revoked:
        return jsonify({"error": "Not Found", "message": "Credential not found or unauthorized"}), 404
    return jsonify({"message": "Credential revoked successfully"}), 200
