"""
Human Approvals API Endpoints.

Handles listing pending approval requests, approving actions, and rejecting actions.
"""

import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.models.user import User
from app.services.approval_service import resolve_approval_request

approvals_bp = Blueprint("approvals_v1", __name__)


def _get_current_user():
    public_id = get_jwt_identity()
    return User.query.filter_by(public_id=public_id).first()


def _format_approval_dict(a: ApprovalRequest) -> dict:
    wf = a.workflow_execution.workflow if a.workflow_execution else None
    node = a.task_execution.workflow_node if a.task_execution else None
    user = a.workflow_execution.user if a.workflow_execution else (a.assigned_approver if a.assigned_approver else None)

    inp = a.input_summary or {}
    target = (
        inp.get("to")
        or inp.get("recipient")
        or inp.get("url")
        or inp.get("eventId")
        or inp.get("title")
        or "External Resource"
    )
    if isinstance(target, list):
        target = ", ".join(str(t) for t in target)

    agent_name = a.requested_by_agent.name if a.requested_by_agent else None
    agent_id = a.requested_by_agent.public_id if a.requested_by_agent else None

    return {
        "id": a.public_id,
        "approval_id": a.public_id,
        "workflow_id": wf.public_id if wf else None,
        "workflow_name": wf.name if wf else None,
        "execution_id": a.workflow_execution.public_id if a.workflow_execution else (str(a.orchestration_id) if a.orchestration_id else None),
        "node_id": node.public_id if node else None,
        "node_name": node.name if node else None,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "action_type": a.requested_action,
        "requested_action": a.requested_action,
        "target": str(target),
        "parameters_summary": a.input_summary,
        "risk_level": a.risk_level,
        "explanation": a.explanation,
        "requester": user.username if user else "System",
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "status": a.status,
        "approved_by": a.resolved_by_user.username if a.resolved_by_user and a.status == "APPROVED" else None,
        "rejected_by": a.resolved_by_user.username if a.resolved_by_user and a.status == "REJECTED" else None,
        "resolved_by": a.resolved_by_user.username if a.resolved_by_user else None,
        "decision_timestamp": a.resolved_at.isoformat() if a.resolved_at else None,
        "decision_reason": (a.approval_comments if a.status == "APPROVED" else a.rejection_reason) if a.status in ("APPROVED", "REJECTED") else None,
        "comments": a.approval_comments,
        "rejection_reason": a.rejection_reason,
        "expiration": a.expiry_time.isoformat() if a.expiry_time else None,
        "expiry_time": a.expiry_time.isoformat() if a.expiry_time else None,
        "input_summary": a.input_summary,
        "proposed_output": (
            json.dumps(a.proposed_output, indent=2, default=str)
            if a.proposed_output and not isinstance(a.proposed_output, str)
            else (a.proposed_output or "")
        ),
        "requested_by_agent": agent_name,
    }


@approvals_bp.route("/approvals", methods=["GET"])
@approvals_bp.route("/approvals/pending", methods=["GET"])
@jwt_required()
def list_approvals():
    """List pending approval requests assigned to or accessible by the authenticated user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not found or unauthenticated."}), 401

    from app.services.approval_service import is_self_approval_allowed_in_current_env
    from app.models.workflow_execution import WorkflowExecution

    if user.role in ("admin", "platform_admin", "manager"):
        approvals = (
            ApprovalRequest.query.filter_by(status=APPROVAL_STATUS_PENDING)
            .order_by(ApprovalRequest.created_at.desc())
            .all()
        )
    else:
        approvals = (
            ApprovalRequest.query.outerjoin(
                WorkflowExecution, ApprovalRequest.workflow_execution_id == WorkflowExecution.id
            )
            .filter(
                ApprovalRequest.status == APPROVAL_STATUS_PENDING,
                (
                    (ApprovalRequest.assigned_approver_user_id == user.id)
                    | (ApprovalRequest.assigned_approver_user_id.is_(None))
                    | (WorkflowExecution.user_id == user.id)
                ),
            )
            .order_by(ApprovalRequest.created_at.desc())
            .all()
        )

    return jsonify({
        "self_approval_allowed_in_dev": is_self_approval_allowed_in_current_env(),
        "approvals": [_format_approval_dict(a) for a in approvals]
    }), 200



@approvals_bp.route("/approvals/<approval_id>", methods=["GET"])
@jwt_required()
def get_approval_details(approval_id):
    """Get details for a specific approval request."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not found or unauthenticated."}), 401

    req_obj = ApprovalRequest.query.filter_by(public_id=approval_id).first()
    if not req_obj:
        return jsonify({"error": "Approval request not found."}), 404

    # Permission check: admin/manager or assigned approver or workflow execution owner
    if user.role not in ("admin", "platform_admin", "manager"):
        wf_owner_id = req_obj.workflow_execution.user_id if req_obj.workflow_execution else None
        if req_obj.assigned_approver_user_id != user.id and wf_owner_id != user.id and req_obj.assigned_approver_user_id is not None:
            return jsonify({"error": "Access denied to this approval request."}), 403

    return jsonify(_format_approval_dict(req_obj)), 200


@approvals_bp.route("/approvals/<approval_id>/approve", methods=["POST"])
@jwt_required()
def approve_request_endpoint(approval_id):
    """Approve a pending approval request."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not found or unauthenticated."}), 401

    req_obj = ApprovalRequest.query.filter_by(public_id=approval_id).first()
    if not req_obj:
        return jsonify({"error": "Approval request not found."}), 404

    # Check permission
    if user.role not in ("admin", "platform_admin", "manager"):
        wf_owner_id = req_obj.workflow_execution.user_id if req_obj.workflow_execution else None
        if req_obj.assigned_approver_user_id != user.id and wf_owner_id != user.id and req_obj.assigned_approver_user_id is not None:
            return jsonify({"error": "Access denied to this approval request."}), 403

    data = request.get_json() or {}
    comments = data.get("comments")

    try:
        resolved = resolve_approval_request(
            approval_id=req_obj.id,
            user_id=user.id,
            approve=True,
            comments=comments,
            prevent_self_approval=True,
        )
        return jsonify({
            "message": "Approval request approved successfully.",
            "status": resolved.status,
            "output": resolved.proposed_output,
        }), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@approvals_bp.route("/approvals/<approval_id>/reject", methods=["POST"])
@jwt_required()
def reject_request_endpoint(approval_id):
    """Reject a pending approval request."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not found or unauthenticated."}), 401

    req_obj = ApprovalRequest.query.filter_by(public_id=approval_id).first()
    if not req_obj:
        return jsonify({"error": "Approval request not found."}), 404

    # Check permission
    if user.role not in ("admin", "platform_admin", "manager"):
        wf_owner_id = req_obj.workflow_execution.user_id if req_obj.workflow_execution else None
        if req_obj.assigned_approver_user_id != user.id and wf_owner_id != user.id and req_obj.assigned_approver_user_id is not None:
            return jsonify({"error": "Access denied to this approval request."}), 403

    data = request.get_json() or {}
    rejection_reason = data.get("rejection_reason", "Rejected by approver.")

    try:
        resolved = resolve_approval_request(
            approval_id=req_obj.id,
            user_id=user.id,
            approve=False,
            rejection_reason=rejection_reason,
            prevent_self_approval=True,
        )
        return jsonify({"message": "Approval request rejected.", "status": resolved.status}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
