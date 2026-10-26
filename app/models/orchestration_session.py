"""
OrchestrationSession model.

Represents a high-level enterprise multi-agent orchestration session.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db

ORCHESTRATION_STATUS_CREATED = "CREATED"
ORCHESTRATION_STATUS_VALIDATING = "VALIDATING"
ORCHESTRATION_STATUS_PLANNING = "PLANNING"
ORCHESTRATION_STATUS_AWAITING_APPROVAL = "AWAITING_APPROVAL"
ORCHESTRATION_STATUS_READY = "READY"
ORCHESTRATION_STATUS_RUNNING = "RUNNING"
ORCHESTRATION_STATUS_PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
ORCHESTRATION_STATUS_REPLANNING = "REPLANNING"
ORCHESTRATION_STATUS_PAUSED = "PAUSED"
ORCHESTRATION_STATUS_FAILED = "FAILED"
ORCHESTRATION_STATUS_CANCELLED = "CANCELLED"
ORCHESTRATION_STATUS_COMPLETED = "COMPLETED"
ORCHESTRATION_STATUS_COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
ORCHESTRATION_STATUS_RECOVERING = "RECOVERING"

SUPPORTED_ORCHESTRATION_STATUSES = (
    ORCHESTRATION_STATUS_CREATED,
    ORCHESTRATION_STATUS_VALIDATING,
    ORCHESTRATION_STATUS_PLANNING,
    ORCHESTRATION_STATUS_AWAITING_APPROVAL,
    ORCHESTRATION_STATUS_READY,
    ORCHESTRATION_STATUS_RUNNING,
    ORCHESTRATION_STATUS_PARTIALLY_COMPLETED,
    ORCHESTRATION_STATUS_REPLANNING,
    ORCHESTRATION_STATUS_PAUSED,
    ORCHESTRATION_STATUS_FAILED,
    ORCHESTRATION_STATUS_CANCELLED,
    ORCHESTRATION_STATUS_COMPLETED,
    ORCHESTRATION_STATUS_COMPLETED_WITH_WARNINGS,
    ORCHESTRATION_STATUS_RECOVERING,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrchestrationSession(db.Model):
    """An Enterprise Multi-Agent Orchestration Session."""

    __tablename__ = "orchestration_sessions"
    __table_args__ = (
        CheckConstraint(
            f"status IN {SUPPORTED_ORCHESTRATION_STATUSES}",
            name="ck_orchestration_sessions_status_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    organization_id = db.Column(db.String(100), index=True, nullable=True, default="default_org")

    objective = db.Column(db.Text, nullable=False)
    input_context = db.Column(db.JSON, nullable=False, default=dict)

    status = db.Column(db.String(30), nullable=False, default=ORCHESTRATION_STATUS_CREATED)
    priority = db.Column(db.Integer, nullable=False, default=1)

    plan_id = db.Column(db.Integer, db.ForeignKey("orchestration_plans.id"), nullable=True)
    root_task_id = db.Column(db.Integer, nullable=True)
    parent_orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), nullable=True)

    correlation_id = db.Column(db.String(100), index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    trace_id = db.Column(db.String(100), index=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # Resource and Governance Limits
    max_execution_time = db.Column(db.Integer, nullable=False, default=3600)  # seconds
    max_agent_count = db.Column(db.Integer, nullable=False, default=10)
    max_delegation_depth = db.Column(db.Integer, nullable=False, default=3)
    max_total_tokens = db.Column(db.Integer, nullable=False, default=100000)
    max_total_cost = db.Column(db.Float, nullable=False, default=10.0)
    max_parallel_tasks = db.Column(db.Integer, nullable=False, default=5)

    # Actual usage accumulation
    total_tokens_used = db.Column(db.Integer, nullable=False, default=0)
    total_cost_incurred = db.Column(db.Float, nullable=False, default=0.0)

    requires_approval = db.Column(db.Boolean, nullable=False, default=False)
    approval_status = db.Column(db.String(20), nullable=True)  # PENDING, APPROVED, REJECTED

    failure_reason = db.Column(db.Text, nullable=True)
    result_summary = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship("User", backref=db.backref("orchestrations", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<OrchestrationSession public_id={self.public_id} status={self.status}>"
