"""
Orchestration Sessions API Endpoints.

Handles session creation, starting, pausing, resuming, cancelling, replanning,
and retrieving plans, tasks, events, and context artifacts.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.agent_message import AgentMessage
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.models.orchestration_event import OrchestrationEvent
from app.models.orchestration_plan import (
    PLAN_TASK_STATUS_AWAITING_APPROVAL,
    PLAN_TASK_STATUS_CANCELLED,
    PLAN_TASK_STATUS_COMPLETED,
    PLAN_TASK_STATUS_FAILED,
    PLAN_TASK_STATUS_PENDING,
    PLAN_TASK_STATUS_READY,
    PLAN_TASK_STATUS_RUNNING,
    OrchestrationPlan,
    PlanTask,
    TaskDependency,
)
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_CANCELLED,
    ORCHESTRATION_STATUS_CREATED,
    ORCHESTRATION_STATUS_FAILED,
    ORCHESTRATION_STATUS_PAUSED,
    ORCHESTRATION_STATUS_READY,
    ORCHESTRATION_STATUS_RUNNING,
    OrchestrationSession,
)
from app.models.shared_context import SharedContextRecord
from app.models.user import User
from app.services.context_service import get_all_context_for_orchestration
from app.services.orchestration_event_service import emit_orchestration_event
from app.services.planner_service import generate_orchestration_plan, replan_orchestration
from app.services.supervisor_service import SupervisorService

orchestrations_bp = Blueprint("orchestrations_v1", __name__)


def _get_current_user():
    public_id = get_jwt_identity()
    return User.query.filter_by(public_id=public_id).first()


def _serialize_plan_task(task: PlanTask) -> dict:
    deps = [
        dep.parent_task.task_key
        for dep in task.upstream_dependencies.all()
        if dep.parent_task
    ]
    # Check if there is an active pending approval request for this task
    has_pending_approval = ApprovalRequest.query.filter_by(
        task_id=task.id,
        status=APPROVAL_STATUS_PENDING,
    ).first() is not None

    effective_status = task.status
    if has_pending_approval and effective_status in (PLAN_TASK_STATUS_PENDING, PLAN_TASK_STATUS_READY):
        effective_status = PLAN_TASK_STATUS_AWAITING_APPROVAL

    return {
        "id": task.public_id,
        "task_key": task.task_key,
        "name": task.name,
        "description": task.description,
        "task_type": task.task_type,
        "assigned_agent_id": task.assigned_agent.public_id if task.assigned_agent else None,
        "assigned_agent_name": task.assigned_agent.name if task.assigned_agent else None,
        "assigned_agent_type": task.assigned_agent.agent_type if task.assigned_agent else None,
        "priority": task.priority or 1,
        "status": effective_status,
        "attempt_count": task.attempt_count or 0,
        "output_data": task.output_data or {},
        "error_message": task.error_message,
        "input_references": task.input_references or {},
        "dependencies": deps,
        "awaiting_approval": has_pending_approval,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@orchestrations_bp.route("/orchestrations/tasks/overview", methods=["GET"])
@jwt_required()
def get_tasks_overview():
    """Retrieve persisted count statistics for all tasks belonging to the current user."""
    user = _get_current_user()
    session_public_id = request.args.get("orchestration_id")

    if session_public_id:
        user_sessions = OrchestrationSession.query.filter_by(public_id=session_public_id, user_id=user.id).all()
    else:
        user_sessions = OrchestrationSession.query.filter_by(user_id=user.id).all()

    if not user_sessions:
        return jsonify({
            "total": 0,
            "pending_queued": 0,
            "in_progress": 0,
            "awaiting_approval": 0,
            "completed": 0,
            "failed": 0,
        }), 200

    plan_ids = [s.plan_id for s in user_sessions if s.plan_id]
    if not plan_ids:
        return jsonify({
            "total": 0,
            "pending_queued": 0,
            "in_progress": 0,
            "awaiting_approval": 0,
            "completed": 0,
            "failed": 0,
        }), 200

    tasks = PlanTask.query.filter(PlanTask.plan_id.in_(plan_ids)).all()

    # Find pending approvals for user's tasks
    pending_appr_task_ids = set()
    user_session_ids = [s.id for s in user_sessions]
    pending_approvals = ApprovalRequest.query.filter(
        ApprovalRequest.orchestration_id.in_(user_session_ids),
        ApprovalRequest.status == APPROVAL_STATUS_PENDING,
    ).all()
    for appr in pending_approvals:
        if appr.task_id:
            pending_appr_task_ids.add(appr.task_id)

    total = len(tasks)
    pending_queued = 0
    in_progress = 0
    awaiting_approval = 0
    completed = 0
    failed = 0

    for t in tasks:
        is_awaiting = t.status == PLAN_TASK_STATUS_AWAITING_APPROVAL or t.id in pending_appr_task_ids
        if is_awaiting:
            awaiting_approval += 1
        elif t.status == PLAN_TASK_STATUS_COMPLETED:
            completed += 1
        elif t.status == PLAN_TASK_STATUS_RUNNING:
            in_progress += 1
        elif t.status in (PLAN_TASK_STATUS_FAILED, PLAN_TASK_STATUS_CANCELLED, "BLOCKED"):
            failed += 1
        else:
            pending_queued += 1

    return jsonify({
        "total": total,
        "pending_queued": pending_queued,
        "in_progress": in_progress,
        "awaiting_approval": awaiting_approval,
        "completed": completed,
        "failed": failed,
    }), 200


@orchestrations_bp.route("/orchestrations", methods=["POST"])
@jwt_required()
def create_orchestration():
    """Create a new enterprise multi-agent orchestration session and generate plan."""
    user = _get_current_user()
    data = request.get_json() or {}
    objective = data.get("objective")

    if not objective:
        return jsonify({"error": "Field 'objective' is required."}), 400

    session = OrchestrationSession(
        user_id=user.id,
        organization_id=data.get("organization_id", "default_org"),
        objective=objective,
        input_context=data.get("input_context", {}),
        priority=int(data.get("priority", 1)),
        max_execution_time=int(data.get("max_execution_time", 3600)),
        max_total_tokens=int(data.get("max_total_tokens", 100000)),
        max_total_cost=float(data.get("max_total_cost", 10.0)),
        status=ORCHESTRATION_STATUS_CREATED,
    )
    db.session.add(session)
    db.session.flush()

    # Generate DAG Plan
    plan = generate_orchestration_plan(session, data.get("tasks"))
    session.status = ORCHESTRATION_STATUS_READY
    db.session.commit()

    emit_orchestration_event(
        event_type="ORCHESTRATION_CREATED",
        orchestration_id=session.id,
        correlation_id=session.correlation_id,
        trace_id=session.trace_id,
        organization_id=session.organization_id,
    )

    return jsonify({
        "message": "Orchestration session created and planned successfully.",
        "orchestration": {
            "id": session.public_id,
            "objective": session.objective,
            "status": session.status,
            "plan_id": plan.public_id,
            "total_tasks": plan.tasks.count(),
            "correlation_id": session.correlation_id,
            "created_at": session.created_at.isoformat(),
        }
    }), 201


@orchestrations_bp.route("/orchestrations", methods=["GET"])
@jwt_required()
def list_orchestrations():
    """List all orchestration sessions for the authenticated user."""
    user = _get_current_user()
    sessions = OrchestrationSession.query.filter_by(user_id=user.id).order_by(OrchestrationSession.created_at.desc()).all()
    return jsonify({
        "orchestrations": [
            {
                "id": s.public_id,
                "objective": s.objective,
                "status": s.status,
                "total_tokens_used": s.total_tokens_used,
                "total_cost_incurred": s.total_cost_incurred,
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ]
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>", methods=["GET"])
@jwt_required()
def get_orchestration(orchestration_id):
    """Retrieve details for a specific orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    return jsonify({
        "id": session.public_id,
        "objective": session.objective,
        "input_context": session.input_context,
        "status": session.status,
        "priority": session.priority,
        "total_tokens_used": session.total_tokens_used,
        "total_cost_incurred": session.total_cost_incurred,
        "max_total_tokens": session.max_total_tokens,
        "max_total_cost": session.max_total_cost,
        "requires_approval": session.requires_approval,
        "approval_status": session.approval_status,
        "failure_reason": session.failure_reason,
        "result_summary": session.result_summary,
        "correlation_id": session.correlation_id,
        "trace_id": session.trace_id,
        "created_at": session.created_at.isoformat(),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/start", methods=["POST"])
@jwt_required()
def start_orchestration(orchestration_id):
    """Execute/Start an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    # Trigger via SupervisorService
    supervisor = SupervisorService()
    updated_session = supervisor.run_orchestration(session.id)

    return jsonify({
        "message": "Orchestration execution updated.",
        "orchestration_id": updated_session.public_id,
        "status": updated_session.status,
        "tokens_used": updated_session.total_tokens_used,
        "cost_incurred": updated_session.total_cost_incurred,
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/pause", methods=["POST"])
@jwt_required()
def pause_orchestration(orchestration_id):
    """Pause a running orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    session.status = ORCHESTRATION_STATUS_PAUSED
    db.session.commit()
    return jsonify({"message": "Orchestration session paused.", "status": session.status}), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/resume", methods=["POST"])
@jwt_required()
def resume_orchestration(orchestration_id):
    """Resume a paused or ready orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    session.status = ORCHESTRATION_STATUS_READY
    db.session.commit()

    supervisor = SupervisorService()
    updated_session = supervisor.run_orchestration(session.id)

    return jsonify({"message": "Orchestration session resumed.", "status": updated_session.status}), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_orchestration(orchestration_id):
    """Cancel an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    session.status = ORCHESTRATION_STATUS_CANCELLED
    session.cancelled_at = db.func.now()
    db.session.commit()
    return jsonify({"message": "Orchestration session cancelled.", "status": session.status}), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/replan", methods=["POST"])
@jwt_required()
def replan_session_endpoint(orchestration_id):
    """Trigger dynamic replanning for an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    new_plan = replan_orchestration(session, reason="User requested replan.")
    return jsonify({
        "message": "Orchestration session replanned successfully.",
        "new_plan_id": new_plan.public_id,
        "version": new_plan.version,
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/plan", methods=["GET"])
@jwt_required()
def get_orchestration_plan(orchestration_id):
    """Retrieve DAG plan for an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session or not session.plan_id:
        return jsonify({"error": "Orchestration plan not found."}), 404

    plan = db.session.get(OrchestrationPlan, session.plan_id)
    tasks = plan.tasks.all()

    return jsonify({
        "plan_id": plan.public_id,
        "version": plan.version,
        "objective": plan.objective,
        "validation_status": plan.validation_status,
        "tasks": [_serialize_plan_task(t) for t in tasks]
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/tasks", methods=["GET"])
@jwt_required()
def get_orchestration_tasks(orchestration_id):
    """Retrieve full task list for an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session or not session.plan_id:
        return jsonify({"error": "Orchestration session or plan not found."}), 404

    plan = db.session.get(OrchestrationPlan, session.plan_id)
    tasks = plan.tasks.all()
    return jsonify({
        "tasks": [_serialize_plan_task(t) for t in tasks]
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/tasks/<task_id>/retry", methods=["POST"])
@jwt_required()
def retry_task_endpoint(orchestration_id, task_id):
    """Safely retry a failed, cancelled, or blocked task in an orchestration."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session or not session.plan_id:
        return jsonify({"error": "Orchestration session or plan not found."}), 404

    task = PlanTask.query.filter_by(public_id=task_id, plan_id=session.plan_id).first()
    if not task:
        return jsonify({"error": "Task not found."}), 404

    if task.status in (PLAN_TASK_STATUS_RUNNING, PLAN_TASK_STATUS_COMPLETED):
        return jsonify({"error": f"Cannot retry a task that is currently {task.status.lower()}."}), 400

    # Reset task state safely without duplicate side-effects
    deps = TaskDependency.query.filter_by(plan_id=session.plan_id, child_task_id=task.id).all()
    all_parents_done = True
    for dep in deps:
        parent_t = db.session.get(PlanTask, dep.parent_task_id)
        if not parent_t or parent_t.status != PLAN_TASK_STATUS_COMPLETED:
            all_parents_done = False
            break

    task.status = PLAN_TASK_STATUS_READY if all_parents_done else PLAN_TASK_STATUS_PENDING
    task.error_message = None
    task.output_data = {}
    task.completed_at = None

    if session.status in (ORCHESTRATION_STATUS_FAILED, ORCHESTRATION_STATUS_CANCELLED):
        session.status = ORCHESTRATION_STATUS_READY
        session.failure_reason = None

    db.session.commit()

    if task.status == PLAN_TASK_STATUS_READY:
        supervisor = SupervisorService()
        supervisor.run_orchestration(session.id)
        db.session.refresh(task)
        db.session.refresh(session)

    return jsonify({
        "message": f"Task '{task.name}' reset for retry.",
        "task": _serialize_plan_task(task),
        "orchestration_status": session.status,
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/tasks/<task_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_task_endpoint(orchestration_id, task_id):
    """Safely cancel a pending, ready, or running task."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session or not session.plan_id:
        return jsonify({"error": "Orchestration session or plan not found."}), 404

    task = PlanTask.query.filter_by(public_id=task_id, plan_id=session.plan_id).first()
    if not task:
        return jsonify({"error": "Task not found."}), 404

    if task.status == PLAN_TASK_STATUS_COMPLETED:
        return jsonify({"error": "Cannot cancel an already completed task."}), 400

    task.status = PLAN_TASK_STATUS_CANCELLED
    task.error_message = "Task cancelled by user."
    task.completed_at = db.func.now()

    ApprovalRequest.query.filter_by(
        task_id=task.id,
        status=APPROVAL_STATUS_PENDING,
    ).update({"status": "CANCELLED"})

    downstream_deps = TaskDependency.query.filter_by(plan_id=session.plan_id, parent_task_id=task.id).all()
    for d_dep in downstream_deps:
        child_t = db.session.get(PlanTask, d_dep.child_task_id)
        if child_t and child_t.status in (PLAN_TASK_STATUS_PENDING, PLAN_TASK_STATUS_READY):
            child_t.status = "BLOCKED"
            child_t.error_message = f"Blocked due to cancellation of prerequisite task '{task.name}'."

    db.session.commit()

    return jsonify({
        "message": f"Task '{task.name}' cancelled.",
        "task": _serialize_plan_task(task),
        "orchestration_status": session.status,
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/events", methods=["GET"])
@jwt_required()
def get_orchestration_events(orchestration_id):
    """Retrieve audit events for an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    events = OrchestrationEvent.query.filter_by(orchestration_id=session.id).order_by(OrchestrationEvent.created_at.asc()).all()
    return jsonify({
        "events": [
            {
                "id": e.public_id,
                "event_type": e.event_type,
                "actor": e.actor,
                "metadata": e.event_metadata,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }), 200


@orchestrations_bp.route("/orchestrations/<orchestration_id>/artifacts", methods=["GET"])
@jwt_required()
def get_orchestration_artifacts(orchestration_id):
    """Retrieve shared context memory artifacts generated during orchestration."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    artifacts = get_all_context_for_orchestration(session.id)
    return jsonify({
        "orchestration_id": session.public_id,
        "artifacts": artifacts,
    }), 200
