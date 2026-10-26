"""
Workflow Schedule Model.

Tracks time-based cron/interval schedules for automated workflow dispatches.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db

SCHEDULE_TYPE_CRON = "cron"
SCHEDULE_TYPE_INTERVAL = "interval"
SCHEDULE_TYPE_ONE_TIME = "one_time"

SCHEDULE_STATUS_ACTIVE = "active"
SCHEDULE_STATUS_PAUSED = "paused"
SCHEDULE_STATUS_COMPLETED = "completed"
SCHEDULE_STATUS_FAILED = "failed"
SCHEDULE_STATUS_CANCELLED = "cancelled"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkflowSchedule(db.Model):
    """Recurring or one-time trigger schedule for workflows."""

    __tablename__ = "workflow_schedules"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), index=True, nullable=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), index=True, nullable=False)


    schedule_type = db.Column(db.String(20), nullable=False, default=SCHEDULE_TYPE_CRON)
    cron_expression = db.Column(db.String(100), nullable=True)
    interval_seconds = db.Column(db.Integer, nullable=True)

    timezone = db.Column(db.String(50), nullable=False, default="UTC")

    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, index=True, nullable=True)
    last_run_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=SCHEDULE_STATUS_ACTIVE)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    misfire_policy = db.Column(db.String(30), nullable=False, default="fire_once")

    input_data = db.Column(db.JSON, nullable=False, default=dict)
    idempotency_key = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("schedules", lazy="dynamic"))
    workflow = db.relationship("Workflow", backref=db.backref("schedules", lazy="dynamic"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkflowSchedule public_id={self.public_id} type={self.schedule_type} status={self.status}>"
