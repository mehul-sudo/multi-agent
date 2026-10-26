"""
Administrative Worker Monitoring & Dead-Letter API Endpoints (/api/v1/admin).

Provides system observability, worker node health metrics, queue backlog statistics,
dead-letter job inspection, and manual admin requeue functionality.
Enforces strict administrative authorization (role == 'admin').
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.async_job import JOB_STATUS_DEAD_LETTERED, AsyncWorkflowJob
from app.schemas.async_job import AsyncJobResponseSchema
from app.schemas.worker_health import SystemMonitoringOverviewSchema
from app.services import auth_service, recovery_service
from app.services.job_service import retry_job
from app.utils.errors import error_response

admin_v1_bp = Blueprint("admin_v1", __name__)


def _get_current_user():
    identity = get_jwt_identity()
    user = auth_service.get_user_by_identity(identity)
    if user is None or not user.is_active:
        return None
    return user


def _require_admin_user(user):
    if not user:
        return error_response("UNAUTHORIZED", "User not found or inactive.", 401)
    if getattr(user, "role", "user") != "admin":
        return error_response("FORBIDDEN", "Administrative privileges are required to access this endpoint.", 403)
    return None


# ---------------------------------------------------------------------------
# GET /api/v1/admin/workers - System Monitoring Overview
# ---------------------------------------------------------------------------
@admin_v1_bp.route("/admin/workers", methods=["GET"])
@jwt_required()
def get_worker_monitoring_overview():
    user = _get_current_user()
    err = _require_admin_user(user)
    if err:
        return err

    overview = recovery_service.get_monitoring_overview()
    serialized = SystemMonitoringOverviewSchema.model_validate(overview).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# GET /api/v1/admin/dead_letter - List Dead Letter Jobs
# ---------------------------------------------------------------------------
@admin_v1_bp.route("/admin/dead_letter", methods=["GET"])
@jwt_required()
def list_dead_letter_jobs():
    user = _get_current_user()
    err = _require_admin_user(user)
    if err:
        return err

    jobs = AsyncWorkflowJob.query.filter_by(status=JOB_STATUS_DEAD_LETTERED).order_by(AsyncWorkflowJob.updated_at.desc()).all()
    serialized = [AsyncJobResponseSchema.model_validate(j).model_dump(mode="json") for j in jobs]
    return jsonify({"items": serialized, "total": len(serialized)}), 200


# ---------------------------------------------------------------------------
# POST /api/v1/admin/dead_letter/<job_id>/requeue - Requeue Dead Letter Job
# ---------------------------------------------------------------------------
@admin_v1_bp.route("/admin/dead_letter/<job_id>/requeue", methods=["POST"])
@jwt_required()
def requeue_dead_letter_job(job_id: str):
    user = _get_current_user()
    err = _require_admin_user(user)
    if err:
        return err

    job = AsyncWorkflowJob.query.filter_by(public_id=job_id).first()
    if not job:
        return error_response("NOT_FOUND", f"Job '{job_id}' not found.", 404)

    if job.status != JOB_STATUS_DEAD_LETTERED:
        return error_response("INVALID_STATE", f"Job '{job_id}' is in status '{job.status}', not DEAD_LETTERED.", 400)

    try:
        # Reset max_retries if exhausted so retry_job succeeds
        job.max_retries = max(job.max_retries, job.retry_count + 1)
        requeued_job = retry_job(job, user.id, reason="Manual admin requeue from dead-letter queue.")
    except ValueError as exc:
        return error_response("INVALID_STATE", str(exc), 400)

    serialized = AsyncJobResponseSchema.model_validate(requeued_job).model_dump(mode="json")
    return jsonify(serialized), 200


# ---------------------------------------------------------------------------
# GET /api/v1/admin/metrics - Administrative System Metrics Endpoint
# ---------------------------------------------------------------------------
@admin_v1_bp.route("/admin/metrics", methods=["GET"])
@jwt_required()
def get_system_metrics():
    """Retrieve aggregated system performance, worker, and token metrics for admins."""
    user = _get_current_user()
    err = _require_admin_user(user)
    if err:
        return err

    from sqlalchemy import func
    from app.extensions import db
    from app.models.agent import Agent
    from app.models.approval_request import ApprovalRequest
    from app.models.llm_usage import LLMUsageLog
    from app.models.workflow import Workflow

    total_workflows = Workflow.query.count()
    total_agents = Agent.query.count()
    total_jobs = AsyncWorkflowJob.query.count()
    pending_approvals = ApprovalRequest.query.filter_by(status="PENDING").count()

    token_stats = db.session.query(
        func.sum(LLMUsageLog.total_tokens),
        func.sum(LLMUsageLog.estimated_cost_usd)
    ).first()

    metrics = {
        "system_status": "healthy",
        "total_workflows": total_workflows,
        "total_agents": total_agents,
        "total_jobs": total_jobs,
        "pending_approvals": pending_approvals,
        "total_tokens_consumed": int(token_stats[0] or 0) if token_stats else 0,
        "total_cost_usd": round(float(token_stats[1] or 0.0), 6) if token_stats else 0.0,
    }

    return jsonify({
        "success": True,
        "message": "System metrics retrieved successfully",
        "data": metrics,
        "error": None,
    }), 200
