"""
Capability Registry API Endpoints.

Handles registration of system capabilities and matching agents for required capabilities.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.capability import Capability
from app.models.user import User
from app.services.agent_matching_service import find_best_agent_for_task

capabilities_bp = Blueprint("capabilities_v1", __name__)


def _get_current_user():
    public_id = get_jwt_identity()
    return User.query.filter_by(public_id=public_id).first()


@capabilities_bp.route("/capabilities", methods=["POST"])
@jwt_required()
def register_capability():
    """Register a new system capability definition."""
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "Field 'name' is required."}), 400

    existing = Capability.query.filter_by(name=name).first()
    if existing:
        return jsonify({"error": f"Capability '{name}' already exists."}), 409

    cap = Capability(
        name=name,
        display_name=data.get("display_name", name),
        description=data.get("description"),
        input_schema=data.get("input_schema", {}),
        output_schema=data.get("output_schema", {}),
        required_permissions=data.get("required_permissions", []),
        risk_level=data.get("risk_level", "low"),
        required_tools=data.get("required_tools", []),
        supported_data_types=data.get("supported_data_types", []),
        estimated_cost=float(data.get("estimated_cost", 0.0)),
        estimated_execution_time=int(data.get("estimated_execution_time", 10)),
        requires_human_approval=bool(data.get("requires_human_approval", False)),
    )
    db.session.add(cap)
    db.session.commit()

    return jsonify({
        "message": "Capability registered successfully.",
        "capability": {
            "id": cap.public_id,
            "name": cap.name,
            "risk_level": cap.risk_level,
            "requires_human_approval": cap.requires_human_approval,
        }
    }), 201


@capabilities_bp.route("/capabilities", methods=["GET"])
@jwt_required()
def list_capabilities():
    """List all registered capabilities and dynamic agents with provider readiness."""
    import os
    capabilities = Capability.query.filter_by(is_active=True).all()

    gemini_avail = bool(os.getenv("GEMINI_API_KEY"))
    openai_avail = bool(os.getenv("OPENAI_API_KEY"))
    resend_avail = bool(os.getenv("RESEND_API_KEY"))

    agents_list = [
        {
            "agent_type": "data_analysis",
            "name": "Data Analysis Agent",
            "category": "Analytics & Intelligence",
            "description": "Performs dataset analysis, revenue trends, calculations, metric aggregation, and anomaly detection.",
            "provider": "gemini" if gemini_avail else "openai",
            "requires_approval": False,
            "risk_level": "low",
            "is_available": True,
            "inputs": ["dataset", "query", "columns", "format"],
            "outputs": ["statistics", "summary", "anomalies", "insights"],
        },
        {
            "agent_type": "document_research",
            "name": "Document Research Agent",
            "category": "Knowledge & Retrieval",
            "description": "Performs grounded document research, policy extraction, and cited synthesis from enterprise documents.",
            "provider": "gemini" if gemini_avail else "openai",
            "requires_approval": False,
            "risk_level": "low",
            "is_available": True,
            "inputs": ["query", "document_ids", "file_ids", "max_results"],
            "outputs": ["content", "sources", "confidence"],
        },
        {
            "agent_type": "report_generation",
            "name": "Executive Report Agent",
            "category": "Reporting & Documentation",
            "description": "Synthesizes multi-agent outputs, analytics, and documents into executive briefs, markdown, and downloadable artifacts.",
            "provider": "gemini" if gemini_avail else "openai",
            "requires_approval": False,
            "risk_level": "low",
            "is_available": True,
            "inputs": ["title", "sections", "theme", "format", "data", "report_type"],
            "outputs": ["reportTitle", "content", "summary", "metrics", "download_url"],
        },
        {
            "agent_type": "email",
            "name": "Enterprise Email Dispatcher",
            "category": "External Communication",
            "description": "Drafts and dispatches email notifications via Resend API or SMTP with mandatory human approval for sending.",
            "provider": "resend" if resend_avail else "smtp",
            "requires_approval": True,
            "risk_level": "medium",
            "is_available": resend_avail or bool(os.getenv("SMTP_HOST")),
            "inputs": ["to", "subject", "body", "attachments", "mode"],
            "outputs": ["messageId", "status", "to", "subject"],
        },
        {
            "agent_type": "database_bi",
            "name": "Database Analytics & BI Agent",
            "category": "Database & BI",
            "description": "Executes read-only SQL queries and schema introspection on enterprise databases with strict DDL/DML write blocking.",
            "provider": "sql_engine",
            "requires_approval": False,
            "risk_level": "low",
            "is_available": True,
            "inputs": ["query", "sql", "operation", "parameters"],
            "outputs": ["rows", "columns", "row_count", "summary"],
        },
        {
            "agent_type": "http_webhook",
            "name": "HTTP & Webhook Agent",
            "category": "External Integrations",
            "description": "Dispatches secure outbound HTTP requests and webhooks with domain allowlisting, SSRF protection, and write approval.",
            "provider": "http_adapter",
            "requires_approval": True,
            "risk_level": "high",
            "is_available": True,
            "inputs": ["url", "method", "headers", "body", "timeout"],
            "outputs": ["statusCode", "data", "headers", "durationMs"],
        },
        {
            "agent_type": "security_analysis",
            "name": "Security & Policy Audit Agent",
            "category": "Governance & Compliance",
            "description": "Performs static security analysis, dependency vulnerability scans, and access policy compliance validation.",
            "provider": "security_engine",
            "requires_approval": False,
            "risk_level": "low",
            "is_available": True,
            "inputs": ["code", "target", "policy_rules"],
            "outputs": ["vulnerabilities", "risk_score", "recommendations"],
        },
    ]

    return jsonify({
        "capabilities": [
            {
                "id": c.public_id,
                "name": c.name,
                "display_name": c.display_name,
                "description": c.description,
                "risk_level": c.risk_level,
                "estimated_cost": c.estimated_cost,
                "requires_human_approval": c.requires_human_approval,
            }
            for c in capabilities
        ],
        "agents": agents_list,
    }), 200


@capabilities_bp.route("/capabilities/match", methods=["POST"])
@jwt_required()
def match_agent_capability():
    """Discover the best matching agent for required capabilities."""
    user = _get_current_user()
    data = request.get_json() or {}
    required_caps = data.get("required_capabilities", [])
    role = data.get("role")

    agent, reasoning, score = find_best_agent_for_task(
        user_id=user.id,
        required_capabilities=required_caps,
        role=role,
    )

    if not agent:
        return jsonify({"matched": False, "reason": reasoning}), 404

    return jsonify({
        "matched": True,
        "fit_score": score,
        "reasoning": reasoning,
        "agent": {
            "id": agent.public_id,
            "name": agent.name,
            "role": agent.role,
            "provider": agent.provider,
            "model": agent.model,
        }
    }), 200
