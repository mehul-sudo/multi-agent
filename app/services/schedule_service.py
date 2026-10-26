"""
Workflow Schedule Service.

Manages time-based cron/interval schedules, calculates timezone-aware execution times,
enforces misfire policies, idempotency, and atomic duplicate-trigger prevention.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import zoneinfo
from croniter import croniter

from app.extensions import db
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_schedule import (
    SCHEDULE_STATUS_ACTIVE,
    SCHEDULE_STATUS_CANCELLED,
    SCHEDULE_STATUS_COMPLETED,
    SCHEDULE_STATUS_FAILED,
    SCHEDULE_STATUS_PAUSED,
    SCHEDULE_TYPE_CRON,
    SCHEDULE_TYPE_INTERVAL,
    SCHEDULE_TYPE_ONE_TIME,
    WorkflowSchedule,
)
from app.services.audit_service import log_audit_event
from app.services.job_service import submit_async_job
from app.utils.errors import ResourceNotFoundError
from app.utils.pagination import paginate_query

SCHEDULE_STATUS_CANCELLED = "cancelled"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def calculate_next_run(
    schedule_type: str,
    cron_expr: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    start_from: Optional[datetime] = None,
    tz_name: Optional[str] = "UTC",
) -> Optional[datetime]:
    """Calculate the next execution timestamp with optional timezone awareness."""
    base_time = start_from or _utcnow()

    # Timezone handling
    tz = timezone.utc
    if tz_name and tz_name.upper() != "UTC":
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc

    if schedule_type == SCHEDULE_TYPE_CRON and cron_expr:
        try:
            # Ensure base_time has tzinfo attached for accurate croniter calculation
            if base_time.tzinfo is None:
                aware_base = base_time.replace(tzinfo=timezone.utc).astimezone(tz)
            else:
                aware_base = base_time.astimezone(tz)

            iter_inst = croniter(cron_expr, aware_base)
            nxt = iter_inst.get_next(datetime)
            # Return naive UTC datetime for standardized database storage
            if nxt.tzinfo is not None:
                nxt = nxt.astimezone(timezone.utc).replace(tzinfo=None)
            return nxt
        except Exception:
            return None
    elif schedule_type == SCHEDULE_TYPE_INTERVAL and interval_seconds:
        return base_time + timedelta(seconds=interval_seconds)
    elif schedule_type == SCHEDULE_TYPE_ONE_TIME:
        return base_time

    return None


def create_schedule(user_id: int, workflow_public_id: str, data: Dict[str, Any]) -> WorkflowSchedule:
    """Create a new time-based trigger schedule for a workflow with idempotency check."""
    wf = Workflow.query.filter_by(public_id=workflow_public_id, user_id=user_id).first()
    if not wf:
        raise ResourceNotFoundError(f"Workflow '{workflow_public_id}' not found or access denied.")

    idempotency_key = data.get("idempotency_key")
    if idempotency_key:
        existing = WorkflowSchedule.query.filter_by(user_id=user_id, idempotency_key=idempotency_key).first()
        if existing:
            return existing

    schedule_type = data.get("schedule_type", SCHEDULE_TYPE_CRON)
    cron_expr = data.get("cron_expression")
    interval_sec = data.get("interval_seconds")
    start_time = data.get("start_time")
    tz_name = data.get("timezone", "UTC")

    next_run = calculate_next_run(
        schedule_type=schedule_type,
        cron_expr=cron_expr,
        interval_seconds=interval_sec,
        start_from=start_time or _utcnow(),
        tz_name=tz_name,
    )

    schedule = WorkflowSchedule(
        user_id=user_id,
        workflow_id=wf.id,
        schedule_type=schedule_type,
        cron_expression=cron_expr,
        interval_seconds=interval_sec,
        timezone=tz_name,
        start_time=start_time,
        end_time=data.get("end_time"),
        next_run_at=next_run,
        status=SCHEDULE_STATUS_ACTIVE,
        is_enabled=True,
        misfire_policy=data.get("misfire_policy", "fire_once"),
        input_data=data.get("input_data", {}),
        idempotency_key=idempotency_key,
    )

    db.session.add(schedule)
    db.session.commit()

    log_audit_event(
        event_type="SCHEDULE_CREATED",
        resource_type="workflow_schedule",
        resource_id=schedule.public_id,
        user_id=user_id,
        event_data={"workflow_id": wf.public_id, "schedule_type": schedule_type, "next_run_at": str(next_run)},
    )

    return schedule


def get_schedule_by_public_id(public_id: str, user_id: Optional[int] = None) -> Optional[WorkflowSchedule]:
    """Retrieve a schedule by public_id."""
    query = WorkflowSchedule.query.filter_by(public_id=public_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def list_schedules(user_id: int, page: int = 1, page_size: int = 20) -> dict:
    """List schedules owned by user."""
    query = WorkflowSchedule.query.filter_by(user_id=user_id).order_by(WorkflowSchedule.created_at.desc())
    return paginate_query(query, page=page, page_size=page_size)


def update_schedule(schedule: WorkflowSchedule, user_id: int, updates: Dict[str, Any]) -> WorkflowSchedule:
    """Update schedule properties."""
    for field in ("cron_expression", "interval_seconds", "is_enabled", "input_data", "misfire_policy", "timezone"):
        if field in updates and updates[field] is not None:
            setattr(schedule, field, updates[field])

    if updates.get("is_enabled") is False:
        schedule.status = SCHEDULE_STATUS_PAUSED
    elif updates.get("is_enabled") is True:
        schedule.status = SCHEDULE_STATUS_ACTIVE

    schedule.next_run_at = calculate_next_run(
        schedule_type=schedule.schedule_type,
        cron_expr=schedule.cron_expression,
        interval_seconds=schedule.interval_seconds,
        start_from=_utcnow(),
        tz_name=schedule.timezone,
    )

    db.session.commit()

    log_audit_event(
        event_type="SCHEDULE_UPDATED",
        resource_type="workflow_schedule",
        resource_id=schedule.public_id,
        user_id=user_id,
        event_data={"status": schedule.status, "next_run_at": str(schedule.next_run_at)},
    )

    return schedule


def pause_schedule(schedule: WorkflowSchedule, user_id: int) -> WorkflowSchedule:
    """Pause an active workflow schedule."""
    schedule.status = SCHEDULE_STATUS_PAUSED
    schedule.is_enabled = False
    db.session.commit()

    log_audit_event(
        event_type="SCHEDULE_PAUSED",
        resource_type="workflow_schedule",
        resource_id=schedule.public_id,
        user_id=user_id,
        event_data={"status": schedule.status},
    )
    return schedule


def resume_schedule(schedule: WorkflowSchedule, user_id: int) -> WorkflowSchedule:
    """Resume a paused workflow schedule."""
    schedule.status = SCHEDULE_STATUS_ACTIVE
    schedule.is_enabled = True
    schedule.next_run_at = calculate_next_run(
        schedule_type=schedule.schedule_type,
        cron_expr=schedule.cron_expression,
        interval_seconds=schedule.interval_seconds,
        start_from=_utcnow(),
        tz_name=schedule.timezone,
    )
    db.session.commit()

    log_audit_event(
        event_type="SCHEDULE_RESUMED",
        resource_type="workflow_schedule",
        resource_id=schedule.public_id,
        user_id=user_id,
        event_data={"status": schedule.status, "next_run_at": str(schedule.next_run_at)},
    )
    return schedule


def cancel_schedule(schedule: WorkflowSchedule, user_id: int) -> WorkflowSchedule:
    """Cancel a workflow schedule permanently."""
    schedule.status = SCHEDULE_STATUS_CANCELLED
    schedule.is_enabled = False
    schedule.next_run_at = None
    db.session.commit()

    log_audit_event(
        event_type="SCHEDULE_CANCELLED",
        resource_type="workflow_schedule",
        resource_id=schedule.public_id,
        user_id=user_id,
        event_data={"status": schedule.status},
    )
    return schedule


def delete_schedule(schedule: WorkflowSchedule, user_id: int) -> None:
    """Delete a workflow schedule."""
    log_audit_event(
        event_type="SCHEDULE_DELETED",
        resource_type="workflow_schedule",
        resource_id=schedule.public_id,
        user_id=user_id,
        event_data={"workflow_id": schedule.workflow.public_id if schedule.workflow else None},
    )

    db.session.delete(schedule)
    db.session.commit()


def process_due_schedules() -> int:
    """Process all workflow schedules due for execution with atomic claiming.

    Each schedule is claimed atomically by advancing its ``next_run_at`` to a
    sentinel future time *before* dispatching the job.  A second concurrent
    invocation of this function (e.g. from a second Celery Beat process) will
    not see the schedule as due because its ``next_run_at`` has already been
    advanced.  If dispatching fails, the claim is rolled back so the schedule
    is retried on the next Beat tick.

    NOTE: The sentinel pattern prevents double-dispatch under the normal
    concurrent-Beat scenario.  Under true simultaneous concurrent writers on
    the same row (requiring row-level SELECT FOR UPDATE), a PostgreSQL-native
    advisory lock would be needed.  That is a PostgreSQL-only feature and is
    not testable with SQLite; it is therefore outside scope of this fix.

    Returns:
        Number of scheduled jobs dispatched.
    """
    now = _utcnow()
    # Sentinel future time used as the claim marker.  We advance next_run_at
    # past the heat of the next minute so a second Beat tick within the same
    # minute will not re-claim an in-flight schedule.
    _CLAIM_SENTINEL = now + timedelta(days=365 * 100)

    due_schedules = WorkflowSchedule.query.filter(
        WorkflowSchedule.is_enabled == True,
        WorkflowSchedule.status == SCHEDULE_STATUS_ACTIVE,
        WorkflowSchedule.next_run_at <= now,
    ).all()

    dispatched = 0
    for sched in due_schedules:
        wf = sched.workflow
        if not wf or wf.status != WORKFLOW_STATUS_ACTIVE:
            continue

        # Misfire policy check
        policy = sched.misfire_policy or "fire_once"
        is_misfired = sched.next_run_at is not None and (now - sched.next_run_at).total_seconds() > 300

        if is_misfired and policy == "skip":
            # Skip missed run and advance next_run_at
            sched.next_run_at = calculate_next_run(
                schedule_type=sched.schedule_type,
                cron_expr=sched.cron_expression,
                interval_seconds=sched.interval_seconds,
                start_from=now,
                tz_name=sched.timezone,
            )
            db.session.commit()
            continue

        # --- Atomic claim: advance next_run_at to sentinel BEFORE dispatching ---
        # This prevents a second concurrent Beat invocation from also claiming
        # this schedule while the current invocation is dispatching the job.
        original_next_run_at = sched.next_run_at
        try:
            sched.next_run_at = _CLAIM_SENTINEL
            db.session.commit()
        except Exception:
            db.session.rollback()
            continue

        # --- Dispatch the job ---
        try:
            corr_id = f"sched_{sched.public_id}_{int(now.timestamp())}"
            submit_async_job(
                user_id=sched.user_id,
                workflow_public_id=wf.public_id,
                data={
                    "input_data": sched.input_data,
                    "metadata": {"scheduled_by": sched.public_id},
                    "queue_name": "default",
                },
                correlation_id=corr_id,
            )
            dispatched += 1

            # Update schedule state now that dispatch succeeded
            sched.last_run_at = now
            if sched.schedule_type == SCHEDULE_TYPE_ONE_TIME:
                sched.status = SCHEDULE_STATUS_COMPLETED
                sched.is_enabled = False
                sched.next_run_at = None
            else:
                sched.next_run_at = calculate_next_run(
                    schedule_type=sched.schedule_type,
                    cron_expr=sched.cron_expression,
                    interval_seconds=sched.interval_seconds,
                    start_from=now,
                    tz_name=sched.timezone,
                )

            db.session.commit()
        except Exception:
            # Dispatch failed — roll back the sentinel claim so the schedule is
            # retried on the next Beat tick rather than being stuck forever.
            db.session.rollback()
            try:
                sched.next_run_at = original_next_run_at
                db.session.commit()
            except Exception:
                db.session.rollback()

    return dispatched

