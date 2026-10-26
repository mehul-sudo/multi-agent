"""
DelegationRecord model.

Tracks governed agent-to-agent task delegation chains.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DelegationRecord(db.Model):
    """A delegation link between a delegating parent task and delegated child task."""

    __tablename__ = "delegation_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), index=True, nullable=False)

    parent_task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=False)
    child_task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=False)

    parent_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=False)
    child_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), index=True, nullable=False)

    delegation_depth = db.Column(db.Integer, nullable=False, default=1)
    delegation_reason = db.Column(db.Text, nullable=True)

    requested_capability = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, FAILED, REJECTED

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    parent_agent = db.relationship("Agent", foreign_keys=[parent_agent_id])
    child_agent = db.relationship("Agent", foreign_keys=[child_agent_id])
    parent_task = db.relationship("PlanTask", foreign_keys=[parent_task_id])
    child_task = db.relationship("PlanTask", foreign_keys=[child_task_id])

    def __repr__(self) -> str:
        return f"<DelegationRecord depth={self.delegation_depth} parent_agent={self.parent_agent_id} -> child_agent={self.child_agent_id}>"
