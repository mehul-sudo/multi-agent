"""
LLM Usage and Cost Tracking Service.

Calculates model cost estimates and persists LLM usage logs to the database.
Maintains model-specific pricing per 1 Million (1M) tokens in USD.
Provides deduplication and separates verified metadata from unconfigured pricing.
"""

from datetime import datetime, timedelta, timezone
import os
import uuid
from typing import Any, Dict, Optional, Tuple

from app.extensions import db
from app.llm.contracts import LLMRequest, LLMResponse
from app.models.llm_usage import LLMUsageLog


# ────────────────────────────────────────────────────────────────────────────
# Verified Model Pricing Table (Per 1 Million Tokens in USD)
# Format: model_name -> (prompt_cost_per_1M, completion_cost_per_1M)
# ────────────────────────────────────────────────────────────────────────────
MODEL_PRICING_PER_1M: Dict[str, Tuple[float, float]] = {
    # Mock / Sandbox Providers (Genuine $0 cost)
    "mock": (0.0, 0.0),
    "mock-v1": (0.0, 0.0),
    "mock-pro-v1": (0.0, 0.0),
    "mock-fast-v1": (0.0, 0.0),
    "mock-model": (0.0, 0.0),

    # Google Gemini Models (Active & Supported)
    # Gemini Flash Lite ($0.075 / 1M prompt, $0.30 / 1M completion)
    "gemini-flash-lite-latest": (0.075, 0.30),
    "gemini-2.5-flash-lite": (0.075, 0.30),
    "gemini-3.5-flash-lite": (0.075, 0.30),

    # Gemini Flash ($0.10 / 1M prompt, $0.40 / 1M completion)
    "gemini-flash-latest": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-3.5-flash": (0.10, 0.40),
    "gemini-3.8-flash": (0.10, 0.40),
    "gemini-3-flash-preview": (0.10, 0.40),

    # Gemini Pro ($1.25 / 1M prompt, $5.00 / 1M completion)
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-pro-latest": (1.25, 5.00),
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-1.0-pro": (0.50, 1.50),

    # OpenAI Models
    "gpt-4o": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (1.50, 2.00),

    # Anthropic Models
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
}

# Compatibility mapping: rates per 1,000 tokens (for legacy tests/callers)
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    model: (rates[0] / 1000.0, rates[1] / 1000.0)
    for model, rates in MODEL_PRICING_PER_1M.items()
}


def _normalize_model_name(model: str) -> str:
    """Normalize model identifier by stripping prefixes and whitespace."""
    if not model:
        return ""
    m = model.strip().lower()
    if m.startswith("models/"):
        m = m[len("models/"):]
    return m


def calculate_estimated_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Calculate estimated cost in USD based on model pricing table.

    Returns:
        float cost in USD or None if model pricing is not configured.
        Explicitly returns 0.0 for mock/free models, and None for unknown pricing.
    """
    model_key = _normalize_model_name(model)
    rates = MODEL_PRICING_PER_1M.get(model_key)

    if not rates:
        # Fallback to prefix matching if exact version suffix differs
        for known_model, known_rates in MODEL_PRICING_PER_1M.items():
            if model_key.startswith(known_model) or known_model.startswith(model_key):
                rates = known_rates
                break

    if not rates:
        return None

    prompt_rate_1m, completion_rate_1m = rates
    cost = (prompt_tokens / 1_000_000.0 * prompt_rate_1m) + (completion_tokens / 1_000_000.0 * completion_rate_1m)
    return round(cost, 6)


def check_agent_budget(agent: Any) -> Optional[str]:
    """Check if agent's token or cost budget has been exceeded based on persisted LLMUsageLogs.

    Returns:
        Error message string if budget is exceeded, or None if budget is valid.
    """
    if not agent or (getattr(agent, "token_budget", None) is None and getattr(agent, "cost_budget", None) is None):
        return None

    # Calculate total successful usage for agent
    result = db.session.query(
        db.func.coalesce(db.func.sum(LLMUsageLog.total_tokens), 0).label("tokens"),
        db.func.coalesce(db.func.sum(LLMUsageLog.estimated_cost_usd), 0.0).label("cost"),
    ).filter(
        LLMUsageLog.agent_id == agent.id,
        LLMUsageLog.success == True,
    ).first()

    total_tokens = int(result.tokens) if result else 0
    total_cost = float(result.cost) if result else 0.0

    if agent.token_budget is not None and total_tokens >= agent.token_budget:
        return f"Agent '{agent.name}' token budget exceeded ({total_tokens}/{agent.token_budget} tokens)."

    if agent.cost_budget is not None and total_cost >= agent.cost_budget:
        return f"Agent '{agent.name}' cost budget exceeded (${total_cost:.4f}/${agent.cost_budget:.4f} USD)."

    return None


def record_llm_usage(
    user_id: int,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: int,
    agent_id: Optional[int] = None,
    workflow_id: Optional[int] = None,
    workflow_execution_id: Optional[int] = None,
    task_execution_id: Optional[int] = None,
    success: bool = True,
    error_category: Optional[str] = None,
    fallback_used: bool = False,
    dedup_key: Optional[str] = None,
    allow_mock: bool = False,
) -> Optional[LLMUsageLog]:
    """Record LLM usage metrics to database with deduplication and mock protection."""
    # Filter out mock/test calls unless explicitly opted in or running unit tests
    is_mock = provider.lower().startswith("mock") or model.lower().startswith("mock")
    if is_mock and not allow_mock and not os.getenv("PYTEST_CURRENT_TEST"):
        return None

    # Reliable deduplication: check dedup_key / public_id
    if dedup_key:
        existing = LLMUsageLog.query.filter_by(public_id=dedup_key).first()
        if existing:
            return existing

    # Avoid duplicate counting of the same provider response during retries/refreshes
    if task_execution_id and user_id and prompt_tokens > 0:
        recent_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=20)
        existing = LLMUsageLog.query.filter(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.task_execution_id == task_execution_id,
            LLMUsageLog.provider == provider,
            LLMUsageLog.model == model,
            LLMUsageLog.prompt_tokens == prompt_tokens,
            LLMUsageLog.completion_tokens == completion_tokens,
            LLMUsageLog.created_at >= recent_cutoff,
        ).first()
        if existing:
            return existing

    total_tokens = prompt_tokens + completion_tokens
    estimated_cost = calculate_estimated_cost(model, prompt_tokens, completion_tokens)

    log = LLMUsageLog(
        public_id=dedup_key if (dedup_key and len(dedup_key) <= 36) else str(uuid.uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        workflow_id=workflow_id,
        workflow_execution_id=workflow_execution_id,
        task_execution_id=task_execution_id,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        estimated_cost_usd=estimated_cost,
        success=success,
        error_category=error_category,
        fallback_used=fallback_used,
    )

    try:
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Fallback query if conflict arose concurrently
        if dedup_key:
            return LLMUsageLog.query.filter_by(public_id=dedup_key).first()

    return log


def record_llm_response_usage(
    request: LLMRequest,
    response: LLMResponse,
) -> Optional[LLMUsageLog]:
    """Centralized extraction and recording helper for provider adapters.

    Safely resolves user_id, metadata, and handles missing token metadata.
    """
    if not request or not response:
        return None

    # Resolve user_id
    user_id = getattr(request, "user_id", None)
    if not user_id:
        try:
            from flask import has_request_context
            from flask_jwt_extended import current_user
            if has_request_context() and current_user:
                user_id = getattr(current_user, "id", None)
        except Exception:
            pass

    if not user_id and hasattr(request, "metadata") and isinstance(request.metadata, dict):
        user_id = request.metadata.get("user_id")

    if not user_id:
        # Resolve via agent if agent_id is present
        raw_agent_id = getattr(request, "agent_id", None)
        if raw_agent_id:
            from app.models.agent import Agent
            ag = Agent.query.filter(
                (Agent.public_id == str(raw_agent_id)) | (Agent.id == raw_agent_id)
            ).first()
            if ag:
                user_id = ag.user_id

    if not user_id:
        # Fallback to first active user in database (e.g. background supervisor tasks)
        try:
            from app.models.user import User
            first_user = User.query.first()
            if first_user:
                user_id = first_user.id
        except Exception:
            pass

    if not user_id:
        # Cannot persist usage without a valid user foreign key
        return None

    # Resolve agent_id (integer FK)
    agent_fk = None
    raw_agent = getattr(request, "agent_id", None)
    if raw_agent:
        if isinstance(raw_agent, int):
            agent_fk = raw_agent
        else:
            from app.models.agent import Agent
            ag = Agent.query.filter(
                (Agent.public_id == str(raw_agent)) | (Agent.name == str(raw_agent))
            ).first()
            if ag:
                agent_fk = ag.id

    if not agent_fk and hasattr(request, "metadata") and isinstance(request.metadata, dict):
        meta_agent_type = request.metadata.get("agent_type")
        if meta_agent_type:
            from app.models.agent import Agent
            ag = Agent.query.filter_by(agent_type=meta_agent_type).first()
            if ag:
                agent_fk = ag.id

    # Resolve workflow & task IDs (integer FKs where possible)
    wf_id = None
    if getattr(request, "workflow_id", None):
        try:
            wf_id = int(request.workflow_id)
        except (ValueError, TypeError):
            pass

    wf_exec_id = None
    if getattr(request, "workflow_execution_id", None):
        try:
            wf_exec_id = int(request.workflow_execution_id)
        except (ValueError, TypeError):
            pass

    task_exec_id = None
    if getattr(request, "task_execution_id", None):
        try:
            task_exec_id = int(request.task_execution_id)
        except (ValueError, TypeError):
            pass

    p_tok = response.usage.prompt_tokens if response.usage else 0
    c_tok = response.usage.completion_tokens if response.usage else 0
    meta_avail = getattr(response.usage, "metadata_available", True) if response.usage else False

    err_cat = None
    if not meta_avail and (p_tok == 0 and c_tok == 0):
        err_cat = "USAGE_METADATA_UNAVAILABLE"

    dedup = getattr(response, "provider_request_id", None) or getattr(request, "correlation_id", None)

    allow_mock = False
    if hasattr(request, "metadata") and isinstance(request.metadata, dict):
        allow_mock = bool(request.metadata.get("allow_mock_usage"))

    return record_llm_usage(
        user_id=user_id,
        provider=response.provider,
        model=response.model,
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        duration_ms=response.request_duration_ms,
        agent_id=agent_fk,
        workflow_id=wf_id,
        workflow_execution_id=wf_exec_id,
        task_execution_id=task_exec_id,
        success=True,
        error_category=err_cat,
        fallback_used=(response.retry_count > 0),
        dedup_key=dedup,
        allow_mock=allow_mock,
    )
