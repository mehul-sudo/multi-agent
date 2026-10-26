"""
Inter-Agent Messages API Endpoints.

Allows querying inter-agent communication history for orchestrations and tasks.
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.agent_message import AgentMessage
from app.models.orchestration_session import OrchestrationSession
from app.models.user import User

messages_bp = Blueprint("agent_messages_v1", __name__)


def _get_current_user():
    public_id = get_jwt_identity()
    return User.query.filter_by(public_id=public_id).first()


@messages_bp.route("/orchestrations/<orchestration_id>/messages", methods=["GET"])
@jwt_required()
def get_orchestration_messages_endpoint(orchestration_id):
    """Get inter-agent messages for an orchestration session."""
    user = _get_current_user()
    session = OrchestrationSession.query.filter_by(public_id=orchestration_id, user_id=user.id).first()
    if not session:
        return jsonify({"error": "Orchestration session not found."}), 404

    messages = AgentMessage.query.filter_by(orchestration_id=session.id).order_by(AgentMessage.created_at.asc()).all()
    return jsonify({
        "messages": [
            {
                "id": m.public_id,
                "message_type": m.message_type,
                "subject": m.subject,
                "sender_agent_id": m.sender_agent.public_id if m.sender_agent else None,
                "receiver_agent_id": m.receiver_agent.public_id if m.receiver_agent else None,
                "payload": m.payload,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
    }), 200
