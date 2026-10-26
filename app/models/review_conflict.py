"""
ReviewOutcome and ConflictRecord models.

Tracks quality control review outcomes and agent conflict resolutions.
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db

REVIEW_OUTCOME_APPROVED = "Approved"
REVIEW_OUTCOME_APPROVED_WITH_WARNINGS = "Approved With Warnings"
REVIEW_OUTCOME_REJECTED = "Rejected"
REVIEW_OUTCOME_NEEDS_REVISION = "Needs Revision"
REVIEW_OUTCOME_NEEDS_HUMAN_REVIEW = "Needs Human Review"
REVIEW_OUTCOME_INCONCLUSIVE = "Inconclusive"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReviewOutcome(db.Model):
    """A quality-control evaluation of a task result."""

    __tablename__ = "review_outcomes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), index=True, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=False)
    reviewer_agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), nullable=True)

    outcome = db.Column(db.String(30), nullable=False, default=REVIEW_OUTCOME_APPROVED)
    confidence_score = db.Column(db.Float, nullable=False, default=1.0)
    completeness_score = db.Column(db.Float, nullable=False, default=1.0)

    feedback = db.Column(db.Text, nullable=True)
    validation_errors = db.Column(db.JSON, nullable=False, default=list)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    reviewer_agent = db.relationship("Agent")
    task = db.relationship("PlanTask")

    def __repr__(self) -> str:
        return f"<ReviewOutcome task_id={self.task_id} outcome={self.outcome!r}>"


class ConflictRecord(db.Model):
    """Record of contradictory outputs between agents and resolution decision."""

    __tablename__ = "conflict_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    orchestration_id = db.Column(db.Integer, db.ForeignKey("orchestration_sessions.id"), index=True, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("plan_tasks.id"), index=True, nullable=True)

    conflicting_outputs = db.Column(db.JSON, nullable=False, default=dict)
    participating_agent_ids = db.Column(db.JSON, nullable=False, default=list)
    evidence_references = db.Column(db.JSON, nullable=False, default=dict)

    resolution_strategy = db.Column(db.String(50), nullable=False, default="adjudicator_agent")
    final_decision = db.Column(db.JSON, nullable=False, default=dict)
    decision_confidence = db.Column(db.Float, nullable=False, default=1.0)

    human_override = db.Column(db.Boolean, nullable=False, default=False)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ConflictRecord public_id={self.public_id} strategy={self.resolution_strategy}>"
