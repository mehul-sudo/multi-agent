"""
Execution API Endpoints.

All endpoints require JWT authentication and enforce strict user-level ownership checks.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.schemas.execution import (
    TaskExecutionResponseSchema,
    WorkflowExecutionListResponseSchema,
    WorkflowExecutionResponseSchema,
    WorkflowExecuteSchema,
)
from app.services import auth_service, execution_service, workflow_service
from app.utils.errors import error_response

executions_bp = Blueprint("executions", __name__)


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


def _serialize_task_execution(te) -> dict:
    ag = te.agent or (te.workflow_node.agent if te.workflow_node else None)

    # Truth-based real-time node status resolution
    raw_status = (te.status or "").lower()
    if raw_status == "blocked":
        from app.models.approval_request import ApprovalRequest, APPROVAL_STATUS_PENDING
        has_pending = ApprovalRequest.query.filter_by(
            task_execution_id=te.id,
            status=APPROVAL_STATUS_PENDING,
        ).first()
        status_val = "WAITING_FOR_APPROVAL" if has_pending else "BLOCKED"
    elif raw_status == "pending":
        status_val = "QUEUED"
    elif raw_status == "running":
        status_val = "RUNNING"
    elif raw_status == "completed":
        status_val = "COMPLETED"
    elif raw_status == "failed":
        status_val = "FAILED"
    else:
        status_val = raw_status.upper()

    return TaskExecutionResponseSchema.model_validate({
        "public_id": te.public_id,
        "workflow_execution_id": te.workflow_execution.public_id if te.workflow_execution else None,
        "workflow_node_id": te.workflow_node.public_id if te.workflow_node else None,
        "node_name": te.workflow_node.name if te.workflow_node else None,
        "agent_id": ag.public_id if ag else None,
        "agent_name": ag.name if ag else None,
        "agent_type": getattr(ag, "agent_type", None) if ag else None,
        "status": status_val,
        "attempt_number": te.attempt_number,
        "input_data": te.input_data or {},
        "output_data": te.output_data or {},
        "error_data": te.error_data or {},
        "started_at": te.started_at,
        "completed_at": te.completed_at,
        "duration_ms": te.duration_ms,
        "created_at": te.created_at,
        "updated_at": te.updated_at,
    }).model_dump(mode="json")


def _serialize_execution(ex) -> dict:
    tasks_ser = [_serialize_task_execution(te) for te in ex.task_executions]
    ex_dict = {
        "public_id": ex.public_id,
        "workflow_id": ex.workflow.public_id if ex.workflow else None,
        "triggered_by": ex.triggered_by,
        "status": ex.status,
        "input_data": ex.input_data or {},
        "output_data": ex.output_data or {},
        "context_data": ex.context_data or {},
        "idempotency_key": ex.idempotency_key,
        "started_at": ex.started_at,
        "completed_at": ex.completed_at,
        "failure_reason": ex.failure_reason,
        "created_at": ex.created_at,
        "updated_at": ex.updated_at,
        "task_executions": tasks_ser,
    }
    return WorkflowExecutionResponseSchema.model_validate(ex_dict).model_dump(mode="json")


# ---------------------------------------------------------------------------
# POST /api/workflows/<workflow_id>/execute - Trigger Workflow Execution
# ---------------------------------------------------------------------------
@executions_bp.route("/workflows/<workflow_id>/execute", methods=["POST"])
@jwt_required()
def execute_workflow(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    workflow = workflow_service.get_workflow_by_public_id(workflow_id, user_id=user.id)
    if not workflow:
        return error_response("NOT_FOUND", "Workflow not found or access denied.", 404)

    payload = request.get_json(silent=True) or {}

    try:
        data = WorkflowExecuteSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    input_data = data.get("input_data") or {}
    env_updates = {}
    if input_data.get("resend_api_key"):
        res_key = str(input_data["resend_api_key"]).strip()
        if res_key:
            env_updates["RESEND_API_KEY"] = res_key
            if input_data.get("email_provider") == "resend":
                env_updates["EMAIL_PROVIDER"] = "resend"

    if input_data.get("smtp_user") and input_data.get("smtp_password"):
        smtp_u = str(input_data["smtp_user"]).strip()
        smtp_p = str(input_data["smtp_password"]).replace(" ", "").strip()
        if smtp_u and smtp_p:
            env_updates["SMTP_USER"] = smtp_u
            env_updates["SMTP_PASSWORD"] = smtp_p
            env_updates["EMAIL_PROVIDER"] = "smtp"

    if input_data.get("email_provider") and "EMAIL_PROVIDER" not in env_updates:
        prov = str(input_data["email_provider"]).strip().lower()
        if prov == "smtp" and not (input_data.get("smtp_user") and input_data.get("smtp_password")):
            # Do not switch global provider to smtp without credentials; preserve working resend configuration
            pass
        else:
            env_updates["EMAIL_PROVIDER"] = prov

    if env_updates:
        import os
        for k, v in env_updates.items():
            os.environ[k] = v
        try:
            env_path = os.path.join(os.getcwd(), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                handled_keys = set()
                for line in lines:
                    replaced = False
                    for k, v in env_updates.items():
                        if line.startswith(f"{k}="):
                            new_lines.append(f"{k}={v}\n")
                            handled_keys.add(k)
                            replaced = True
                            break
                    if not replaced:
                        new_lines.append(line)
                for k, v in env_updates.items():
                    if k not in handled_keys:
                        new_lines.append(f"{k}={v}\n")
                with open(env_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
        except Exception:
            pass

    # Auto-activate draft workflow if valid and has nodes
    if workflow.status == "draft":
        if not workflow.nodes or len(workflow.nodes) == 0:
            return error_response(
                "BAD_REQUEST",
                f"Workflow '{workflow.name}' has no agent tasks configured. Please open the workflow designer and add at least one agent node before executing.",
                400,
            )
        from app.services.workflow_service import activate_workflow
        activated, val_res = activate_workflow(workflow, user.id)
        if not activated:
            errors = "; ".join(val_res.get("errors", ["Workflow structure is invalid"]))
            return error_response("VALIDATION_ERROR", f"Workflow cannot be activated: {errors}", 400)

    try:
        execution, is_new = execution_service.trigger_workflow_execution(
            workflow=workflow,
            user_id=user.id,
            input_data=input_data,
            idempotency_key=data.get("idempotency_key"),
        )
    except ValueError as exc:
        return error_response("EXECUTION_ERROR", str(exc), 400)

    status_code = 201 if is_new else 200
    return jsonify(_serialize_execution(execution)), status_code


# ---------------------------------------------------------------------------
# GET /api/executions - List Executions
# ---------------------------------------------------------------------------
@executions_bp.route("/executions", methods=["GET"])
@jwt_required()
def list_executions():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except ValueError:
        return error_response("VALIDATION_ERROR", "Page and page_size must be positive integers.", 400)

    status = request.args.get("status")
    workflow_id = request.args.get("workflow_id")

    result = execution_service.list_executions(
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        workflow_public_id=workflow_id,
    )

    result["items"] = [_serialize_execution(ex) for ex in result["items"]]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/executions/<execution_id> - Get Execution
# ---------------------------------------------------------------------------
@executions_bp.route("/executions/<execution_id>", methods=["GET"])
@jwt_required()
def get_execution(execution_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    execution = execution_service.get_execution_by_public_id(execution_id, user_id=user.id)
    if not execution:
        return error_response("NOT_FOUND", "Execution not found or access denied.", 404)

    return jsonify(_serialize_execution(execution)), 200


# ---------------------------------------------------------------------------
# POST /api/executions/<execution_id>/cancel - Cancel Execution
# ---------------------------------------------------------------------------
@executions_bp.route("/executions/<execution_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_execution(execution_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    execution = execution_service.get_execution_by_public_id(execution_id, user_id=user.id)
    if not execution:
        return error_response("NOT_FOUND", "Execution not found or access denied.", 404)

    ex, success, err = execution_service.cancel_execution(execution, user.id)
    if not success:
        return error_response("STATE_ERROR", err, 400)

    return jsonify(_serialize_execution(ex)), 200


# ---------------------------------------------------------------------------
# POST /api/executions/<execution_id>/retry - Retry Execution
# ---------------------------------------------------------------------------
@executions_bp.route("/executions/<execution_id>/retry", methods=["POST"])
@jwt_required()
def retry_execution(execution_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    execution = execution_service.get_execution_by_public_id(execution_id, user_id=user.id)
    if not execution:
        return error_response("NOT_FOUND", "Execution not found or access denied.", 404)

    ex, success, err = execution_service.retry_execution(execution, user.id)
    if not success:
        return error_response("STATE_ERROR", err, 400)

    return jsonify(_serialize_execution(ex)), 200


# ---------------------------------------------------------------------------
# GET /api/executions/<execution_id>/tasks - List Task Executions
# ---------------------------------------------------------------------------
@executions_bp.route("/executions/<execution_id>/tasks", methods=["GET"])
@jwt_required()
def list_execution_tasks(execution_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    execution = execution_service.get_execution_by_public_id(execution_id, user_id=user.id)
    if not execution:
        return error_response("NOT_FOUND", "Execution not found or access denied.", 404)

    tasks_ser = [_serialize_task_execution(te) for te in execution.task_executions]
    return jsonify({"tasks": tasks_ser}), 200
