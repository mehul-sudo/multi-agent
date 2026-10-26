"""
Celery Task Definitions for Distributed Multi-Agent Orchestration Execution.

Wired to the Phase 7 Celery app factory and bound to Flask app context.
Handles background orchestration execution, late ACKs, worker heartbeats, and retries.
"""

from typing import Any, Dict

from celery import Task

from app.celery_app import celery_app
from app.extensions import db
from app.models.orchestration_session import OrchestrationSession
from app.services.supervisor_service import SupervisorService


@celery_app.task(bind=True, acks_late=True, max_retries=3, name="app.tasks.execute_orchestration_task")
def execute_orchestration_task(self: Task, orchestration_id: int) -> Dict[str, Any]:
    """Execute an orchestration session asynchronously on a Celery worker."""
    session = db.session.get(OrchestrationSession, orchestration_id)
    if not session:
        return {"status": "error", "message": f"Orchestration session {orchestration_id} not found."}

    try:
        supervisor = SupervisorService()
        result_session = supervisor.run_orchestration(orchestration_id)
        return {
            "status": result_session.status.lower(),
            "orchestration_id": result_session.public_id,
            "tokens_used": result_session.total_tokens_used,
            "cost_incurred": result_session.total_cost_incurred,
        }
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5)
        session.status = "FAILED"
        session.failure_reason = f"Worker exception: {str(exc)}"
        db.session.commit()
        return {"status": "failed", "orchestration_id": session.public_id, "error": str(exc)}
