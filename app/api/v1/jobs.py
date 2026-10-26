"""
Async Jobs API Endpoints (/api/v1/jobs and /api/v1/workflows/<id>/jobs).

Provides asynchronous job submission, status polling, cancellation, retry, result, and listing.
All endpoints require JWT authentication and enforce strict user-level ownership.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.schemas.async_job import (
    AsyncJobDetailResponseSchema,
    AsyncJobResponseSchema,
    JobCancelSchema,
    JobListResponseSchema,
    JobRetrySchema,
    JobSubmitSchema,
)
from app.services import auth_service, job_service
from app.utils.errors import ResourceNotFoundError, error_response

jobs_v1_bp = Blueprint("jobs_v1", __name__)


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
# POST /api/v1/workflows/<workflow_id>/jobs - Submit Workflow Job
# ---------------------------------------------------------------------------
@jobs_v1_bp.route("/workflows/<workflow_id>/jobs", methods=["POST"])
@jwt_required()
def submit_workflow_job(workflow_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    payload = request.get_json(silent=True) or {}
    correlation_id = request.headers.get("X-Correlation-ID") or payload.get("correlation_id")

    try:
        data = JobSubmitSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)

    try:
        job, is_existing = job_service.submit_async_job(
            user_id=user.id,
            workflow_public_id=workflow_id,
            data=data,
            correlation_id=correlation_id,
        )
    except ResourceNotFoundError as exc:
        return error_response("NOT_FOUND", str(exc), 404)
    except ValueError as exc:
        return error_response("BAD_REQUEST", str(exc), 400)
    except Exception as exc:
        return error_response("SERVER_ERROR", str(exc), 500)

    serialized = AsyncJobResponseSchema.model_validate(job).model_dump(mode="json")
    status_code = 200 if is_existing else 202
    return jsonify(serialized), status_code


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<job_id> - Get Job Status
# ---------------------------------------------------------------------------
@jobs_v1_bp.route("/jobs/<job_id>", methods=["GET"])
@jwt_required()
def get_job_status(job_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    job = job_service.get_job_by_public_id(job_id, user_id=user.id)
    if not job:
        return error_response("NOT_FOUND", "Job not found or access denied.", 404)

    serialized = AsyncJobDetailResponseSchema.model_validate(job).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/<job_id>/cancel - Cancel Job
# ---------------------------------------------------------------------------
@jobs_v1_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_job(job_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    job = job_service.get_job_by_public_id(job_id, user_id=user.id)
    if not job:
        return error_response("NOT_FOUND", "Job not found or access denied.", 404)

    payload = request.get_json(silent=True) or {}
    try:
        cancel_data = JobCancelSchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    try:
        cancelled_job = job_service.cancel_job(job, user.id, reason=cancel_data.get("reason", "Cancelled by user."))
    except ValueError as exc:
        return error_response("INVALID_STATE", str(exc), 400)

    serialized = AsyncJobResponseSchema.model_validate(cancelled_job).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/<job_id>/retry - Retry Failed Job
# ---------------------------------------------------------------------------
@jobs_v1_bp.route("/jobs/<job_id>/retry", methods=["POST"])
@jwt_required()
def retry_job(job_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    job = job_service.get_job_by_public_id(job_id, user_id=user.id)
    if not job:
        return error_response("NOT_FOUND", "Job not found or access denied.", 404)

    payload = request.get_json(silent=True) or {}
    try:
        retry_data = JobRetrySchema.model_validate(payload).model_dump(mode="python")
    except ValidationError as exc:
        return error_response("VALIDATION_ERROR", _validation_error_message(exc), 400)

    try:
        retried_job = job_service.retry_job(
            job,
            user.id,
            reason=retry_data.get("reason", "Retried by user."),
            priority_override=retry_data.get("priority_override"),
        )
    except ValueError as exc:
        return error_response("INVALID_STATE", str(exc), 400)

    serialized = AsyncJobResponseSchema.model_validate(retried_job).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# GET /api/v1/jobs - List Jobs
# ---------------------------------------------------------------------------
@jobs_v1_bp.route("/jobs", methods=["GET"])
@jwt_required()
def list_jobs():
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

    result = job_service.list_jobs(
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        workflow_public_id=workflow_id,
    )

    result["items"] = [
        AsyncJobResponseSchema.model_validate(item).model_dump(mode="json") for item in result["items"]
    ]
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<job_id>/result - Job Result
# ---------------------------------------------------------------------------
@jobs_v1_bp.route("/jobs/<job_id>/result", methods=["GET"])
@jwt_required()
def get_job_result(job_id: str):
    user = _get_current_user()
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)

    job = job_service.get_job_by_public_id(job_id, user_id=user.id)
    if not job:
        return error_response("NOT_FOUND", "Job not found or access denied.", 404)

    return jsonify({
        "job_id": job.public_id,
        "status": job.status,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "result_data": job.result_data or {},
    }), 200
