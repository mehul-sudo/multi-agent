"""
Workflow Design API Endpoints.

All endpoints require JWT authentication and enforce strict user-level ownership checks.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_node import WorkflowNode
from app.schemas.workflow import (
    WorkflowCreateSchema,
    WorkflowDependencyCreateSchema,
    WorkflowDependencyResponseSchema,
    WorkflowNodeCreateSchema,
    WorkflowNodeResponseSchema,
    WorkflowNodeUpdateSchema,
    WorkflowResponseSchema,
    WorkflowUpdateSchema,
    WorkflowValidationResponseSchema,
)
from app.services import auth_service, workflow_service
from app.utils.errors import error_response

workflows_bp = Blueprint("workflows", __name__)


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


def _serialize_workflow(wf) -> dict:
    nodes_ser = []
    for node in wf.nodes:
        n_dict = {
            "public_id": node.public_id,
            "agent_id": node.agent.public_id if node.agent else None,
            "agent_public_id": node.agent.public_id if node.agent else None,
            "agent_name": node.agent.name if node.agent else None,
            "agent_type": getattr(node.agent, "agent_type", None) if node.agent else None,
            "name": node.name,
            "task_type": node.task_type,
            "instructions": node.instructions,
            "input_mapping": node.input_mapping or {},
            "output_key": node.output_key,
            "configuration": node.configuration or {},
            "timeout_seconds": node.timeout_seconds,
            "retry_limit": node.retry_limit,
            "priority": node.priority,
            "position": node.position or {},
            "created_at": node.created_at,
            "updated_at": node.updated_at,
        }
        nodes_ser.append(n_dict)

    deps_ser = []
    for dep in wf.dependencies:
        d_dict = {
            "public_id": dep.public_id,
            "source_node_id": dep.source_node.public_id if dep.source_node else str(dep.source_node_id),
            "target_node_id": dep.target_node.public_id if dep.target_node else str(dep.target_node_id),
            "dependency_type": dep.dependency_type,
            "is_optional": getattr(dep, "is_optional", False),
            "condition": getattr(dep, "condition", None),
            "created_at": dep.created_at,
        }
        deps_ser.append(d_dict)

    wf_dict = {
        "public_id": wf.public_id,
        "name": wf.name,
        "description": wf.description,
        "status": wf.status,
        "version": wf.version,
        "priority": getattr(wf, "priority", 1),
        "input_schema": wf.input_schema or {},
        "output_schema": wf.output_schema or {},
        "metadata_json": wf.metadata_json or {},
        "nodes": nodes_ser,
        "dependencies": deps_ser,
        "created_at": wf.created_at,
        "updated_at": wf.updated_at,
    }
    return WorkflowResponseSchema.model_validate(wf_dict).model_dump(mode="json")


# ---------------------------------------------------------------------------
# POST /api/workflows - Create draft workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("", methods=["POST"])
@jwt_required()
def create_workflow():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = WorkflowCreateSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    workflow = workflow_service.create_workflow(user.id, data)
    return jsonify(_serialize_workflow(workflow)), 201


# ---------------------------------------------------------------------------
# GET /api/workflows - List workflows
# ---------------------------------------------------------------------------
@workflows_bp.route("", methods=["GET"])
@jwt_required()
def list_workflows():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except ValueError:
        return error_response("VALIDATION_ERROR", "Page and page_size must be positive integers.", 400)

    status = request.args.get("status")

    result = workflow_service.list_workflows(user.id, page=page, page_size=page_size, status=status)
    result["items"] = [_serialize_workflow(item) for item in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/workflows/<workflow_id> - Get workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>", methods=["GET"])
@jwt_required()
def get_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    return jsonify(_serialize_workflow(workflow)), 200


# ---------------------------------------------------------------------------
# PATCH /api/workflows/<workflow_id> - Update workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>", methods=["PATCH"])
@jwt_required()
def update_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = WorkflowUpdateSchema.model_validate(payload).model_dump(mode="python", exclude_unset=True)
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    updated_wf = workflow_service.update_workflow(workflow, user.id, data)
    return jsonify(_serialize_workflow(updated_wf)), 200


# ---------------------------------------------------------------------------
# DELETE /api/workflows/<workflow_id> - Delete or Archive workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>", methods=["DELETE"])
@jwt_required()
def delete_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    force = request.args.get("force", "true").lower() in ("true", "1", "yes")
    deleted = workflow_service.delete_workflow_safely(workflow, user.id, force=force)
    if deleted:
        return jsonify({"message": "Workflow deleted successfully."}), 200
    else:
        return jsonify({"message": "Workflow archived safely because historical executions reference it."}), 200


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/nodes - Add Node
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/nodes", methods=["POST"])
@jwt_required()
def add_node(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = WorkflowNodeCreateSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    node, err = workflow_service.add_node_to_workflow(workflow, user.id, data)
    if err:
        return error_response("VALIDATION_ERROR", err, 400)

    n_dict = {
        "public_id": node.public_id,
        "agent_id": node.agent.public_id if node.agent else None,
        "agent_public_id": node.agent.public_id if node.agent else None,
        "agent_name": node.agent.name if node.agent else None,
        "agent_type": getattr(node.agent, "agent_type", None) if node.agent else None,
        "name": node.name,
        "task_type": node.task_type,
        "instructions": node.instructions,
        "input_mapping": node.input_mapping or {},
        "output_key": node.output_key,
        "configuration": node.configuration or {},
        "timeout_seconds": node.timeout_seconds,
        "retry_limit": node.retry_limit,
        "priority": node.priority,
        "position": node.position or {},
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }
    ser = WorkflowNodeResponseSchema.model_validate(n_dict).model_dump(mode="json")
    return jsonify(ser), 201


# ---------------------------------------------------------------------------
# PATCH /api/workflows/<workflow_id>/nodes/<node_id> - Update Node
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/nodes/<node_id>", methods=["PATCH"])
@jwt_required()
def update_node(workflow_id: str, node_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    node = WorkflowNode.query.filter_by(public_id=node_id, workflow_id=workflow.id).first()
    if not node:
        return error_response("NOT_FOUND", "Workflow node not found.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = WorkflowNodeUpdateSchema.model_validate(payload).model_dump(mode="python", exclude_unset=True)
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    updated_node, err = workflow_service.update_workflow_node(workflow, node, user.id, data)
    if err:
        return error_response("VALIDATION_ERROR", err, 400)

    n_dict = {
        "public_id": updated_node.public_id,
        "agent_id": updated_node.agent.public_id if updated_node.agent else None,
        "agent_public_id": updated_node.agent.public_id if updated_node.agent else None,
        "agent_name": updated_node.agent.name if updated_node.agent else None,
        "agent_type": getattr(updated_node.agent, "agent_type", None) if updated_node.agent else None,
        "name": updated_node.name,
        "task_type": updated_node.task_type,
        "instructions": updated_node.instructions,
        "input_mapping": updated_node.input_mapping or {},
        "output_key": updated_node.output_key,
        "configuration": updated_node.configuration or {},
        "timeout_seconds": updated_node.timeout_seconds,
        "retry_limit": updated_node.retry_limit,
        "priority": updated_node.priority,
        "position": updated_node.position or {},
        "created_at": updated_node.created_at,
        "updated_at": updated_node.updated_at,
    }
    ser = WorkflowNodeResponseSchema.model_validate(n_dict).model_dump(mode="json")
    return jsonify(ser), 200


# ---------------------------------------------------------------------------
# DELETE /api/workflows/<workflow_id>/nodes/<node_id> - Delete Node
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/nodes/<node_id>", methods=["DELETE"])
@jwt_required()
def delete_node(workflow_id: str, node_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    node = WorkflowNode.query.filter_by(public_id=node_id, workflow_id=workflow.id).first()
    if not node:
        return error_response("NOT_FOUND", "Workflow node not found.", 404)

    workflow_service.delete_workflow_node(workflow, node, user.id)
    return jsonify({"message": "Workflow node deleted successfully."}), 200


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/dependencies - Add Dependency
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/dependencies", methods=["POST"])
@jwt_required()
def add_dependency(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("VALIDATION_ERROR", "Request body must be valid JSON.", 400)

    try:
        data = WorkflowDependencyCreateSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    dep, err = workflow_service.add_dependency_to_workflow(workflow, user.id, data)
    if err:
        return error_response("VALIDATION_ERROR", err, 400)

    d_dict = {
        "public_id": dep.public_id,
        "source_node_id": dep.source_node.public_id,
        "target_node_id": dep.target_node.public_id,
        "dependency_type": dep.dependency_type,
        "created_at": dep.created_at,
    }
    ser = WorkflowDependencyResponseSchema.model_validate(d_dict).model_dump(mode="json")
    return jsonify(ser), 201


# ---------------------------------------------------------------------------
# DELETE /api/workflows/<workflow_id>/dependencies/<dependency_id> - Delete Dependency
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/dependencies/<dependency_id>", methods=["DELETE"])
@jwt_required()
def delete_dependency(workflow_id: str, dependency_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    dep = WorkflowDependency.query.filter_by(public_id=dependency_id, workflow_id=workflow.id).first()
    if not dep:
        return error_response("NOT_FOUND", "Workflow dependency not found.", 404)

    workflow_service.delete_dependency_from_workflow(workflow, dep, user.id)
    return jsonify({"message": "Workflow dependency deleted successfully."}), 200


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/validate - Validate Workflow DAG
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/validate", methods=["POST"])
@jwt_required()
def validate_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    res = workflow_service.validate_workflow(workflow)
    ser = WorkflowValidationResponseSchema.model_validate(res).model_dump(mode="json")
    return jsonify(ser), 200


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/activate - Activate Workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/activate", methods=["POST"])
@jwt_required()
def activate_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    activated, val_res = workflow_service.activate_workflow(workflow, user.id)
    if not activated:
        err_msgs = [e.get("message") for e in val_res.get("errors", []) if isinstance(e, dict) and e.get("message")]
        err_summary = "; ".join(err_msgs) if err_msgs else "Cannot activate invalid workflow graph."
        return jsonify({
            "error": {
                "code": "VALIDATION_FAILED",
                "message": err_summary,
                "details": val_res.get("errors", []),
            }
        }), 400

    return jsonify(_serialize_workflow(workflow)), 200


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/archive - Archive Workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/archive", methods=["POST"])
@jwt_required()
def archive_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    archived_wf = workflow_service.archive_workflow(workflow, user.id)
    return jsonify(_serialize_workflow(archived_wf)), 200


# ---------------------------------------------------------------------------
# GET /api/workflows/<workflow_id>/execution-plan - Get Execution Plan
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/execution-plan", methods=["GET"])
@jwt_required()
def get_execution_plan(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    from app.services.execution_plan_service import (
        generate_execution_plan,
        get_execution_plan_for_workflow,
    )

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    plan = get_execution_plan_for_workflow(workflow_id, user.id)
    if not plan:
        plan = generate_execution_plan(workflow)

    return jsonify({
        "public_id": plan.public_id,
        "workflow_id": workflow.public_id,
        "stages": plan.stages,
        "node_priorities": plan.node_priorities,
        "dependency_rules": plan.dependency_rules,
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
    }), 200


# ---------------------------------------------------------------------------
# GET /api/workflows/<workflow_id>/export - Export Workflow JSON (Schema 1.0)
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/export", methods=["GET"])
@jwt_required()
def export_workflow_endpoint(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    export_data = workflow_service.export_workflow(workflow)
    return jsonify(export_data), 200


# ---------------------------------------------------------------------------
# POST /api/workflows/import - Import Workflow JSON (Schema 1.0)
# ---------------------------------------------------------------------------
@workflows_bp.route("/import", methods=["POST"])
@jwt_required()
def import_workflow_endpoint():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    payload = request.get_json(silent=True)
    if not payload:
        return error_response("VALIDATION_ERROR", "Request body must be a valid JSON object.", 400)

    wf, warnings, err = workflow_service.import_workflow(user.id, payload)
    if err:
        return error_response("VALIDATION_ERROR", err, 400)

    serialized = _serialize_workflow(wf)
    return jsonify({
        "workflow": serialized,
        "warnings": warnings,
        "message": "Workflow imported successfully.",
    }), 201


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/copy or /duplicate - Clone Workflow
# ---------------------------------------------------------------------------
@workflows_bp.route("/<workflow_id>/duplicate", methods=["POST"])
@workflows_bp.route("/<workflow_id>/copy", methods=["POST"])
@jwt_required()
def duplicate_workflow_endpoint(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    clone = workflow_service.duplicate_workflow(workflow, user.id)
    return jsonify(_serialize_workflow(clone)), 201

