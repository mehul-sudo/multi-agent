"""
Agent API Endpoints.

All endpoints require JWT authentication and enforce strict user-level ownership checks.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.schemas.agent import (
    AgentCreateSchema,
    AgentListResponseSchema,
    AgentResponseSchema,
    AgentUpdateSchema,
)
from app.services import agent_service, auth_service
from app.utils.errors import error_response

agents_bp = Blueprint("agents", __name__)


def _get_current_user():
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if user is None or not user.is_active:
        return None
    return user


def _validation_error_message(exc: ValidationError) -> str:
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first.get("loc", ())) or "input"
    return f"{field}: {first.get('msg', 'invalid value')}"


# ---------------------------------------------------------------------------
# POST /api/agents - Create an agent
# ---------------------------------------------------------------------------
@agents_bp.route("", methods=["POST"])
@jwt_required()
def create_agent():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = AgentCreateSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)

    agent = agent_service.create_agent(user.id, data)
    serialized = AgentResponseSchema.model_validate(agent).model_dump(mode="json")
    return jsonify(serialized), 201


# ---------------------------------------------------------------------------
# GET /api/agents - List agents
# ---------------------------------------------------------------------------
@agents_bp.route("", methods=["GET"])
@jwt_required()
def list_agents():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except ValueError:
        return error_response("VALIDATION_ERROR", "Page and page_size must be positive integers.", 400)

    status = request.args.get("status")
    agent_type = request.args.get("agent_type")

    result = agent_service.list_agents(
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        agent_type=agent_type,
    )

    result["items"] = [
        AgentResponseSchema.model_validate(item).model_dump(mode="json") for item in result["items"]
    ]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/agents/<agent_id> - Get single agent
# ---------------------------------------------------------------------------
@agents_bp.route("/<agent_id>", methods=["GET"])
@jwt_required()
def get_agent(agent_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    agent = agent_service.get_agent_by_public_id(agent_id, user_id=user.id)
    if not agent:
        return error_response("NOT_FOUND", "Agent not found or access denied.", 404)

    serialized = AgentResponseSchema.model_validate(agent).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# PATCH /api/agents/<agent_id> - Update agent
# ---------------------------------------------------------------------------
@agents_bp.route("/<agent_id>", methods=["PATCH"])
@jwt_required()
def update_agent(agent_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    agent = agent_service.get_agent_by_public_id(agent_id, user_id=user.id)
    if not agent:
        return error_response("NOT_FOUND", "Agent not found or access denied.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = AgentUpdateSchema.model_validate(payload).model_dump(mode="python", exclude_unset=True)
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)

    updated_agent = agent_service.update_agent(agent, user.id, data)
    serialized = AgentResponseSchema.model_validate(updated_agent).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# DELETE /api/agents/<agent_id> - Delete or archive agent
# ---------------------------------------------------------------------------
@agents_bp.route("/<agent_id>", methods=["DELETE"])
@jwt_required()
def delete_agent(agent_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    agent = agent_service.get_agent_by_public_id(agent_id, user_id=user.id)
    if not agent:
        return error_response("NOT_FOUND", "Agent not found or access denied.", 404)

    deleted = agent_service.archive_or_delete_agent(agent, user.id)
    if deleted:
        return jsonify({"message": "Agent deleted successfully."}), 200
    else:
        return jsonify({"message": "Agent archived safely because historical executions reference it."}), 200


# ---------------------------------------------------------------------------
# POST /api/agents/<agent_id>/activate - Activate agent
# ---------------------------------------------------------------------------
@agents_bp.route("/<agent_id>/activate", methods=["POST"])
@jwt_required()
def activate_agent(agent_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    agent = agent_service.get_agent_by_public_id(agent_id, user_id=user.id)
    if not agent:
        return error_response("NOT_FOUND", "Agent not found or access denied.", 404)

    activated_agent = agent_service.set_agent_status(agent, user.id, "active")
    serialized = AgentResponseSchema.model_validate(activated_agent).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# POST /api/agents/<agent_id>/disable - Disable agent
# ---------------------------------------------------------------------------
@agents_bp.route("/<agent_id>/disable", methods=["POST"])
@jwt_required()
def disable_agent(agent_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    agent = agent_service.get_agent_by_public_id(agent_id, user_id=user.id)
    if not agent:
        return error_response("NOT_FOUND", "Agent not found or access denied.", 404)

    disabled_agent = agent_service.set_agent_status(agent, user.id, "disabled")
    serialized = AgentResponseSchema.model_validate(disabled_agent).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# GET /api/agents/types - List registered agent types
# ---------------------------------------------------------------------------
@agents_bp.route("/types", methods=["GET"])
@jwt_required()
def list_agent_types():
    from app.agents import list_registered_agent_types, get_agent_instance
    types = list_registered_agent_types()
    details = []
    for t in types:
        inst = get_agent_instance(t)
        details.append({
            "agent_type": t,
            "description": getattr(inst, "description", ""),
            "requires_side_effect_approval": getattr(inst, "requires_side_effect_approval", False),
        })
    return jsonify({"success": True, "agent_types": details}), 200


# ---------------------------------------------------------------------------
# POST /api/agents/<agent_type>/execute - Direct agent execution endpoint
# ---------------------------------------------------------------------------
@agents_bp.route("/<agent_identifier>/execute", methods=["POST"])
@agents_bp.route("/<agent_identifier>/run", methods=["POST"])
@jwt_required()
def execute_registered_agent(agent_identifier: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    from app.agents import get_agent_instance, AgentContext
    agent_type = agent_identifier
    db_agent = agent_service.get_agent_by_public_id(agent_identifier, user_id=user.id)
    if db_agent:
        agent_type = db_agent.agent_type

    agent_instance = get_agent_instance(agent_type)
    if not agent_instance:
        return error_response("NOT_FOUND", f"Specialized agent type '{agent_type}' is not registered.", 404)

    payload = request.get_json(silent=True) or {}
    input_data = payload.get("input") if "input" in payload else (payload.get("input_data") or payload)

    ctx = AgentContext(
        user_id=user.id,
        input_data=input_data,
        instructions=payload.get("instructions", db_agent.system_instructions if db_agent else None),
        metadata=payload.get("metadata", {}),
    )

    result = agent_instance.execute(ctx)
    res_dict = result.to_dict()

    # Create real human approval request if unapproved side effect
    if result.requires_approval:
        try:
            from app.models.approval_request import ApprovalRequest, APPROVAL_STATUS_PENDING
            app_req = ApprovalRequest(
                requested_action=f"Execute {agent_type} agent",
                risk_level="high" if agent_type in ("email", "http_webhook") else "medium",
                explanation=f"Human authorization required for {agent_type} operation.",
                input_summary=input_data if isinstance(input_data, dict) else {"raw": str(input_data)},
                proposed_output=res_dict.get("output") or {},
                status=APPROVAL_STATUS_PENDING,
                assigned_approver_user_id=user.id,
                requested_by_agent_id=db_agent.id if db_agent else None,
            )
            db.session.add(app_req)
            db.session.commit()
            res_dict["requires_approval"] = True
            res_dict["approval_request_id"] = app_req.public_id
            res_dict["approval_status"] = "pending"
            res_dict["message"] = f"Action paused for governance: Created pending approval request {app_req.public_id[:8]}. View and authorize at /approvals."
        except Exception as e:
            db.session.rollback()

    return jsonify(res_dict), 200 if result.success else 400

