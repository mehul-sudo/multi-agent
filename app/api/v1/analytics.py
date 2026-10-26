"""
Analytics & Usage API endpoints (Phase 11 & Production Hardening).

Endpoints:
  GET /api/v1/analytics/usage     - Token usage and LLM request counts
  GET /api/v1/analytics/costs     - LLM cost calculations by provider and model
  GET /api/v1/analytics/workflows - Workflow execution metrics and duration statistics
  GET /api/v1/analytics/agents    - Agent performance metrics and per-agent token/cost consumption
  GET /api/v1/analytics/history   - Daily historical trends of tokens, costs, and executions
  GET /api/v1/analytics/summary   - Aggregated system performance and cost summary
"""

from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import case, func

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.async_job import AsyncWorkflowJob
from app.models.llm_usage import LLMUsageLog
from app.models.task_execution import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TaskExecution
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.utils.errors import success_response

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/usage", methods=["GET"])
@jwt_required()
def get_token_usage():
    """Retrieve token usage metrics for the current user."""
    user_id = current_user.id
    usages = LLMUsageLog.query.filter_by(user_id=user_id).all()

    total_prompt_tokens = sum(u.prompt_tokens or 0 for u in usages)
    total_completion_tokens = sum(u.completion_tokens or 0 for u in usages)
    total_tokens = sum(u.total_tokens or 0 for u in usages)
    total_cost = sum(u.estimated_cost_usd or 0.0 for u in usages if u.estimated_cost_usd is not None)
    unknown_cost_count = sum(1 for u in usages if u.estimated_cost_usd is None)

    data = {
        "user_id": user_id,
        "record_count": len(usages),
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(total_cost, 6),
        "pricing_complete": (unknown_cost_count == 0),
        "unknown_cost_records": unknown_cost_count,
    }
    return success_response(data=data, message="Token usage metrics retrieved successfully")


@analytics_bp.route("/costs", methods=["GET"])
@jwt_required()
def get_cost_usage():
    """Retrieve LLM cost metrics broken down by provider and model."""
    user_id = current_user.id
    records = db.session.query(
        LLMUsageLog.provider,
        LLMUsageLog.model,
        func.sum(LLMUsageLog.prompt_tokens).label("prompt_tokens"),
        func.sum(LLMUsageLog.completion_tokens).label("completion_tokens"),
        func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
        func.sum(LLMUsageLog.estimated_cost_usd).label("total_cost"),
        func.count(LLMUsageLog.id).label("record_count"),
        func.sum(case((LLMUsageLog.estimated_cost_usd == None, 1), else_=0)).label("unknown_count"),
    ).filter(LLMUsageLog.user_id == user_id).group_by(
        LLMUsageLog.provider, LLMUsageLog.model
    ).all()

    breakdown = []
    total_cost = 0.0
    overall_unknown = 0
    for r in records:
        cost = float(r.total_cost or 0.0) if r.total_cost is not None else 0.0
        total_cost += cost
        unknown_records = int(r.unknown_count or 0)
        overall_unknown += unknown_records

        is_mock = (r.provider or "").lower().startswith("mock")
        has_pricing = (unknown_records == 0 or is_mock)

        breakdown.append({
            "provider": r.provider or "unknown",
            "model": r.model or "unknown",
            "prompt_tokens": int(r.prompt_tokens or 0),
            "completion_tokens": int(r.completion_tokens or 0),
            "total_tokens": int(r.total_tokens or 0),
            "estimated_cost_usd": round(cost, 6) if has_pricing else None,
            "pricing_available": has_pricing,
            "record_count": int(r.record_count or 0),
        })

    data = {
        "user_id": user_id,
        "total_estimated_cost_usd": round(total_cost, 6),
        "pricing_complete": (overall_unknown == 0),
        "breakdown": breakdown,
    }
    return success_response(data=data, message="LLM cost usage metrics retrieved successfully")


@analytics_bp.route("/workflows", methods=["GET"])
@jwt_required()
def get_workflow_stats():
    """Retrieve workflow execution and performance statistics across all executions."""
    user_id = current_user.id
    total_workflows = Workflow.query.filter_by(user_id=user_id).count()

    # Query synchronous WorkflowExecution records
    wf_exec_counts = (
        db.session.query(WorkflowExecution.status, func.count(WorkflowExecution.id))
        .filter(WorkflowExecution.user_id == user_id)
        .group_by(WorkflowExecution.status)
        .all()
    )

    # Query unlinked AsyncWorkflowJob records only, preventing double-counting with WorkflowExecution
    job_counts = (
        db.session.query(AsyncWorkflowJob.status, func.count(AsyncWorkflowJob.id))
        .filter(
            AsyncWorkflowJob.user_id == user_id,
            AsyncWorkflowJob.workflow_execution_id == None,
        )
        .group_by(AsyncWorkflowJob.status)
        .all()
    )

    status_dict = {}
    for status, count in wf_exec_counts:
        s_norm = status.upper() if status else "UNKNOWN"
        status_dict[s_norm] = status_dict.get(s_norm, 0) + count

    for status, count in job_counts:
        s_norm = status.upper() if status else "UNKNOWN"
        status_dict[s_norm] = status_dict.get(s_norm, 0) + count

    total_jobs = sum(status_dict.values())
    succeeded = status_dict.get("SUCCEEDED", 0) + status_dict.get("COMPLETED", 0)
    failed = status_dict.get("FAILED", 0)
    cancelled = status_dict.get("CANCELLED", 0)
    partially_completed = status_dict.get("PARTIALLY_COMPLETED", 0)
    running = status_dict.get("RUNNING", 0)
    pending = status_dict.get("PENDING", 0) + status_dict.get("QUEUED", 0)

    data = {
        "total_workflows": total_workflows,
        "total_jobs": total_jobs,
        "status_counts": status_dict,
        "succeeded_jobs": succeeded,
        "failed_jobs": failed,
        "cancelled_jobs": cancelled,
        "partially_completed_jobs": partially_completed,
        "running_jobs": running,
        "pending_jobs": pending,
    }
    return success_response(data=data, message="Workflow statistics retrieved successfully")


@analytics_bp.route("/agents", methods=["GET"])
@jwt_required()
def get_agent_stats():
    """Retrieve real agent performance and per-agent token/cost consumption."""
    user_id = current_user.id
    agents = Agent.query.filter_by(user_id=user_id).all()

    agent_list = []
    for agent in agents:
        invocations = TaskExecution.query.filter_by(agent_id=agent.id).count()
        successes = TaskExecution.query.filter_by(agent_id=agent.id, status=TASK_STATUS_COMPLETED).count()
        failures = TaskExecution.query.filter_by(agent_id=agent.id, status=TASK_STATUS_FAILED).count()
        avg_dur = (
            db.session.query(func.avg(TaskExecution.duration_ms))
            .filter(TaskExecution.agent_id == agent.id)
            .scalar()
            or 0
        )

        # Fix: Inspect agent.status safely instead of non-existent agent.is_active
        agent_status = "active" if getattr(agent, "status", "") == AGENT_STATUS_ACTIVE else "inactive"

        # Aggregate LLM usage from LLMUsageLog for this agent
        llm_stats = db.session.query(
            func.sum(LLMUsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(LLMUsageLog.completion_tokens).label("completion_tokens"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("total_cost"),
            func.count(LLMUsageLog.id).label("llm_calls"),
        ).filter(LLMUsageLog.agent_id == agent.id).first()

        p_tokens = int(llm_stats.prompt_tokens or 0) if llm_stats else 0
        c_tokens = int(llm_stats.completion_tokens or 0) if llm_stats else 0
        t_tokens = int(llm_stats.total_tokens or 0) if llm_stats else 0
        cost = round(float(llm_stats.total_cost or 0.0), 6) if (llm_stats and llm_stats.total_cost is not None) else 0.0
        llm_calls = int(llm_stats.llm_calls or 0) if llm_stats else 0

        agent_list.append({
            "agent_id": agent.public_id,
            "name": agent.name,
            "role": agent.role,
            "status": agent_status,
            "agent_type": agent.agent_type,
            "invocations": invocations,
            "successes": successes,
            "failures": failures,
            "avg_duration_ms": round(float(avg_dur), 1),
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": t_tokens,
            "estimated_cost_usd": cost,
            "llm_calls": llm_calls,
        })

    data = {
        "total_agents": len(agents),
        "agents": agent_list,
    }
    return success_response(data=data, message="Agent statistics retrieved successfully")


@analytics_bp.route("/history", methods=["GET"])
@jwt_required()
def get_historical_trends():
    """Retrieve daily historical trends for token consumption, costs, and workflow executions."""
    user_id = current_user.id
    days = request.args.get("days", 30, type=int)
    if days is None or days <= 0 or days > 365:
        days = 30

    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    # Daily LLM token usage and costs
    daily_usage = (
        db.session.query(
            func.date(LLMUsageLog.created_at).label("usage_date"),
            func.sum(LLMUsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(LLMUsageLog.completion_tokens).label("completion_tokens"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("total_cost"),
            func.count(LLMUsageLog.id).label("requests_count"),
        )
        .filter(LLMUsageLog.user_id == user_id, LLMUsageLog.created_at >= cutoff_date)
        .group_by(func.date(LLMUsageLog.created_at))
        .order_by(func.date(LLMUsageLog.created_at).asc())
        .all()
    )

    # Daily Workflow execution counts
    exec_date_col = func.coalesce(WorkflowExecution.started_at, WorkflowExecution.created_at)
    daily_wf = (
        db.session.query(
            func.date(exec_date_col).label("exec_date"),
            func.count(WorkflowExecution.id).label("total_executions"),
            func.sum(case((WorkflowExecution.status == "completed", 1), else_=0)).label("succeeded"),
            func.sum(case((WorkflowExecution.status == "failed", 1), else_=0)).label("failed"),
        )
        .filter(WorkflowExecution.user_id == user_id, exec_date_col >= cutoff_date)
        .group_by(func.date(exec_date_col))
        .order_by(func.date(exec_date_col).asc())
        .all()
    )

    # Merge by date into a cohesive time-series map
    dates_map = {}
    for r in daily_usage:
        d_str = str(r.usage_date)
        if not d_str or d_str == "None":
            continue
        if d_str not in dates_map:
            dates_map[d_str] = {
                "date": d_str,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "llm_requests": 0,
                "workflow_executions": 0,
                "succeeded_executions": 0,
                "failed_executions": 0,
            }
        dates_map[d_str]["prompt_tokens"] = int(r.prompt_tokens or 0)
        dates_map[d_str]["completion_tokens"] = int(r.completion_tokens or 0)
        dates_map[d_str]["total_tokens"] = int(r.total_tokens or 0)
        dates_map[d_str]["estimated_cost_usd"] = round(float(r.total_cost or 0.0), 6)
        dates_map[d_str]["llm_requests"] = int(r.requests_count or 0)

    for r in daily_wf:
        d_str = str(r.exec_date)
        if not d_str or d_str == "None":
            continue
        if d_str not in dates_map:
            dates_map[d_str] = {
                "date": d_str,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "llm_requests": 0,
                "workflow_executions": 0,
                "succeeded_executions": 0,
                "failed_executions": 0,
            }
        dates_map[d_str]["workflow_executions"] = int(r.total_executions or 0)
        dates_map[d_str]["succeeded_executions"] = int(r.succeeded or 0)
        dates_map[d_str]["failed_executions"] = int(r.failed or 0)

    sorted_trends = [dates_map[k] for k in sorted(dates_map.keys())]

    data = {
        "period_days": days,
        "record_count": len(sorted_trends),
        "trends": sorted_trends,
    }
    return success_response(data=data, message="Historical analytics trends retrieved successfully")


@analytics_bp.route("/summary", methods=["GET"])
@jwt_required()
def get_summary_analytics():
    """Retrieve top-level summary analytics for dashboard consumption."""
    user_id = current_user.id

    token_sum = (
        db.session.query(
            func.sum(LLMUsageLog.total_tokens),
            func.sum(LLMUsageLog.estimated_cost_usd),
        )
        .filter(LLMUsageLog.user_id == user_id)
        .first()
    )

    total_tokens = int(token_sum[0] or 0) if (token_sum and token_sum[0] is not None) else 0
    total_cost = float(token_sum[1] or 0.0) if (token_sum and token_sum[1] is not None) else 0.0

    total_workflows = Workflow.query.filter_by(user_id=user_id).count()
    total_agents = Agent.query.filter_by(user_id=user_id).count()

    # Deduplicate workflow executions: only count unlinked AsyncWorkflowJob
    unlinked_jobs = AsyncWorkflowJob.query.filter(
        AsyncWorkflowJob.user_id == user_id,
        AsyncWorkflowJob.workflow_execution_id == None,
    ).count()
    total_jobs = WorkflowExecution.query.filter_by(user_id=user_id).count() + unlinked_jobs

    data = {
        "user_id": user_id,
        "total_workflows": total_workflows,
        "total_agents": total_agents,
        "total_jobs": total_jobs,
        "total_tokens_consumed": total_tokens,
        "total_cost_usd": round(total_cost, 6),
    }
    return success_response(data=data, message="Summary analytics retrieved successfully")
