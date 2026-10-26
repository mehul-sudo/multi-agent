"""
Worker Health Model.

Tracks active Celery worker nodes, heatbeats, and queue assignments.
"""

from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkerHealth(db.Model):
    """Celery worker health and heartbeats."""

    __tablename__ = "worker_health"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    worker_id = db.Column(db.String(100), unique=True, index=True, nullable=False)
    hostname = db.Column(db.String(100), nullable=False)

    queues = db.Column(db.JSON, nullable=False, default=list)
    active_tasks_count = db.Column(db.Integer, nullable=False, default=0)
    registered_tasks = db.Column(db.JSON, nullable=False, default=list)

    status = db.Column(db.String(20), nullable=False, default="online")

    started_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    last_heartbeat_at = db.Column(db.DateTime, index=True, nullable=False, default=_utcnow)

    version = db.Column(db.String(50), nullable=True, default="1.0.0")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkerHealth worker_id={self.worker_id} status={self.status} active_tasks={self.active_tasks_count}>"
