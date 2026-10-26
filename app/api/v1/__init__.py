"""
API v1 Blueprint Package.

Exports the v1 Blueprint aggregator for Phase 1-10 routes.
"""

from flask import Blueprint
from app.api.v1.jobs import jobs_v1_bp
from app.api.v1.schedules import schedules_v1_bp
from app.api.v1.admin import admin_v1_bp
from app.api.v1.agents import agents_v1_bp
from app.api.v1.capabilities import capabilities_bp
from app.api.v1.providers import providers_bp
from app.api.v1.orchestrations import orchestrations_bp
from app.api.v1.agent_messages import messages_bp
from app.api.v1.approvals import approvals_bp
from app.api.v1.organizations import bp as organizations_bp
from app.api.v1.permissions import bp as permissions_bp
from app.api.v1.workflow_policies import bp as workflow_policies_bp
from app.api.v1.tool_policies import bp as tool_policies_bp
from app.api.v1.credentials import bp as credentials_bp
from app.api.v1.audit_logs import bp as audit_logs_bp
from app.api.v1.analytics import analytics_bp
from app.api.v1.integration_status import integration_status_bp

api_v1_bp = Blueprint("api_v1", __name__)
api_v1_bp.register_blueprint(jobs_v1_bp)
api_v1_bp.register_blueprint(schedules_v1_bp)
api_v1_bp.register_blueprint(admin_v1_bp)
api_v1_bp.register_blueprint(agents_v1_bp)
api_v1_bp.register_blueprint(capabilities_bp)
api_v1_bp.register_blueprint(providers_bp)
api_v1_bp.register_blueprint(orchestrations_bp)
api_v1_bp.register_blueprint(messages_bp)
api_v1_bp.register_blueprint(approvals_bp)
api_v1_bp.register_blueprint(organizations_bp)
api_v1_bp.register_blueprint(permissions_bp)
api_v1_bp.register_blueprint(workflow_policies_bp)
api_v1_bp.register_blueprint(tool_policies_bp)
api_v1_bp.register_blueprint(credentials_bp)
api_v1_bp.register_blueprint(audit_logs_bp)
api_v1_bp.register_blueprint(analytics_bp, url_prefix="/analytics")
api_v1_bp.register_blueprint(integration_status_bp)

from app.api.v1.streaming import streaming_bp
from app.api.v1.uploads import uploads_bp
from app.api.v1.chat import chat_bp

api_v1_bp.register_blueprint(streaming_bp)
api_v1_bp.register_blueprint(uploads_bp)
api_v1_bp.register_blueprint(chat_bp)

