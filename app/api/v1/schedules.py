"""
Workflow Schedules API Endpoints (/api/v1/schedules and /api/v1/workflows/<id>/schedules).

Provides workflow schedule management and cron/interval triggers.
All endpoints require JWT authentication and enforce strict user-level ownership checks.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.schemas.workflow_schedule import (
    ScheduleCreateSchema,
    ScheduleListResponseSchema,
    ScheduleResponseSchema,
    ScheduleUpdateSchema,
)
from app.services import auth_service, schedule_service
from app.utils.errors import ResourceNotFoundError, error_response

schedules_v1_bp = Blueprint("schedules_v1", __name__)


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
# POST /api/v1/workflows/<workflow_id>/schedules - Create Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/workflows/<workflow_id>/schedules", methods=["POST"])
@jwt_required()
def create_schedule(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    payload = request.get_json(silent=True) or {}
    try:
        data = ScheduleCreateSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)

    try:
        schedule = schedule_service.create_schedule(user.id, workflow_id, data)
    except ResourceNotFoundError as exc:
        return error_response("NOT_FOUND", str(exc), 404)
    except ValueError as exc:
        return error_response("BAD_REQUEST", str(exc), 400)

    serialized = ScheduleResponseSchema.model_validate(schedule).model_dump(mode="json")
    return jsonify(serialized), 201


# ---------------------------------------------------------------------------
# GET /api/v1/schedules - List Schedules
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules", methods=["GET"])
@jwt_required()
def list_schedules():
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except ValueError:
        return error_response("VALIDATION_ERROR", "Page and page_size must be positive integers.", 400)

    result = schedule_service.list_schedules(user_id=user.id, page=page, page_size=page_size)
    result["items"] = [
        ScheduleResponseSchema.model_validate(item).model_dump(mode="json") for item in result["items"]
    ]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/v1/schedules/<schedule_id> - Get Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules/<schedule_id>", methods=["GET"])
@jwt_required()
def get_schedule(schedule_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    schedule = schedule_service.get_schedule_by_public_id(schedule_id, user_id=user.id)
    if not schedule:
        return error_response("NOT_FOUND", "Schedule not found or access denied.", 404)

    serialized = ScheduleResponseSchema.model_validate(schedule).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# PATCH /api/v1/schedules/<schedule_id> - Update Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules/<schedule_id>", methods=["PATCH"])
@jwt_required()
def update_schedule(schedule_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    schedule = schedule_service.get_schedule_by_public_id(schedule_id, user_id=user.id)
    if not schedule:
        return error_response("NOT_FOUND", "Schedule not found or access denied.", 404)

    payload = request.get_json(silent=True) or {}
    try:
        data = ScheduleUpdateSchema.model_validate(payload).model_dump(mode="python", exclude_unset=True)
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    updated_schedule = schedule_service.update_schedule(schedule, user.id, data)
    serialized = ScheduleResponseSchema.model_validate(updated_schedule).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# DELETE /api/v1/schedules/<schedule_id> - Delete Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules/<schedule_id>", methods=["DELETE"])
@jwt_required()
def delete_schedule(schedule_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    schedule = schedule_service.get_schedule_by_public_id(schedule_id, user_id=user.id)
    if not schedule:
        return error_response("NOT_FOUND", "Schedule not found or access denied.", 404)

    schedule_service.delete_schedule(schedule, user.id)
    return jsonify({"message": "Schedule deleted successfully."}), 200


# ---------------------------------------------------------------------------
# POST /api/v1/schedules/<schedule_id>/pause - Pause Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules/<schedule_id>/pause", methods=["POST"])
@jwt_required()
def pause_schedule(schedule_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    schedule = schedule_service.get_schedule_by_public_id(schedule_id, user_id=user.id)
    if not schedule:
        return error_response("NOT_FOUND", "Schedule not found or access denied.", 404)

    paused = schedule_service.pause_schedule(schedule, user.id)
    serialized = ScheduleResponseSchema.model_validate(paused).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# POST /api/v1/schedules/<schedule_id>/resume - Resume Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules/<schedule_id>/resume", methods=["POST"])
@jwt_required()
def resume_schedule(schedule_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    schedule = schedule_service.get_schedule_by_public_id(schedule_id, user_id=user.id)
    if not schedule:
        return error_response("NOT_FOUND", "Schedule not found or access denied.", 404)

    resumed = schedule_service.resume_schedule(schedule, user.id)
    serialized = ScheduleResponseSchema.model_validate(resumed).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# POST /api/v1/schedules/<schedule_id>/cancel - Cancel Schedule
# ---------------------------------------------------------------------------
@schedules_v1_bp.route("/schedules/<schedule_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_schedule(schedule_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    schedule = schedule_service.get_schedule_by_public_id(schedule_id, user_id=user.id)
    if not schedule:
        return error_response("NOT_FOUND", "Schedule not found or access denied.", 404)

    cancelled = schedule_service.cancel_schedule(schedule, user.id)
    serialized = ScheduleResponseSchema.model_validate(cancelled).model_dump(mode="json")
    return jsonify(serialized), 200

