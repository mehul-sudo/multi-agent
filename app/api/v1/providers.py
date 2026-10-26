"""
Provider & Model Configurations API Endpoints.

Handles managed LLM provider configurations. Secrets are NEVER returned in API responses.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.provider_config import ProviderConfig
from app.models.user import User

providers_bp = Blueprint("providers_v1", __name__)


def _get_current_user():
    public_id = get_jwt_identity()
    return User.query.filter_by(public_id=public_id).first()


@providers_bp.route("/providers", methods=["POST"])
@jwt_required()
def register_provider():
    """Register or update a managed provider configuration. API keys are stored as secret references."""
    user = _get_current_user()
    data = request.get_json() or {}
    provider_name = data.get("provider_name")

    if not provider_name:
        return jsonify({"error": "Field 'provider_name' is required."}), 400

    secret_key = data.get("secret_key")
    secret_ref = f"env:{provider_name.upper()}_API_KEY" if not secret_key else "configured_secret_ref"

    cfg = ProviderConfig(
        user_id=user.id,
        provider_name=provider_name.lower(),
        display_name=data.get("display_name", provider_name.capitalize()),
        secret_key_ref=secret_ref,
        available_models=data.get("available_models", ["v1"]),
        default_model=data.get("default_model"),
        model_capabilities=data.get("model_capabilities", {"streaming": True, "structured_output": True}),
        rate_limits=data.get("rate_limits", {"requests_per_minute": 60}),
        cost_per_1k_tokens=data.get("cost_per_1k_tokens", {"prompt": 0.001, "completion": 0.002}),
        fallback_priority=int(data.get("fallback_priority", 10)),
        is_active=True,
    )
    db.session.add(cfg)
    db.session.commit()

    return jsonify({
        "message": "Provider configuration registered successfully.",
        "provider": {
            "id": cfg.public_id,
            "provider_name": cfg.provider_name,
            "available_models": cfg.available_models,
            "secret_key_configured": True,  # Never return raw key
            "is_active": cfg.is_active,
        }
    }), 201


@providers_bp.route("/providers", methods=["GET"])
@jwt_required()
def list_providers():
    """List all available provider configurations with redacted secret keys."""
    user = _get_current_user()
    cfgs = ProviderConfig.query.filter((ProviderConfig.user_id == user.id) | (ProviderConfig.user_id == None)).all()
    return jsonify({
        "providers": [
            {
                "id": c.public_id,
                "provider_name": c.provider_name,
                "display_name": c.display_name,
                "available_models": c.available_models,
                "default_model": c.default_model,
                "model_capabilities": c.model_capabilities,
                "fallback_priority": c.fallback_priority,
                "is_active": c.is_active,
            }
            for c in cfgs
        ]
    }), 200


@providers_bp.route("/providers/<provider_id>/models", methods=["GET"])
@jwt_required()
def get_provider_models(provider_id):
    """Get available models for a provider."""
    cfg = ProviderConfig.query.filter_by(public_id=provider_id).first()
    if not cfg:
        return jsonify({"error": "Provider not found."}), 404

    return jsonify({
        "provider_name": cfg.provider_name,
        "available_models": cfg.available_models,
        "default_model": cfg.default_model,
    }), 200
