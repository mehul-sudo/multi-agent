"""
GovernanceService.

Enforces resource limits, token budgets, cost budgets, delegation depth limits,
and task concurrency caps across org, user, orchestration, agent, and task levels.
"""

from typing import Any, Dict, Tuple

from app.models.agent import Agent
from app.models.orchestration_session import OrchestrationSession


class BudgetExceededError(ValueError):
    """Raised when an orchestration or agent budget limit is exceeded."""
    pass


def check_orchestration_limits(session: OrchestrationSession, estimated_tokens: int = 0, estimated_cost: float = 0.0) -> None:
    """Verify that an orchestration session has not exceeded its configured budget or resource limits."""
    if session.total_tokens_used + estimated_tokens > session.max_total_tokens:
        raise BudgetExceededError(
            f"Token limit exceeded: used {session.total_tokens_used} + estimated {estimated_tokens} > max {session.max_total_tokens}"
        )

    if session.total_cost_incurred + estimated_cost > session.max_total_cost:
        raise BudgetExceededError(
            f"Cost limit exceeded: incurred ${session.total_cost_incurred:.2f} + estimated ${estimated_cost:.2f} > max ${session.max_total_cost:.2f}"
        )


def check_agent_budget(agent: Agent, prompt_tokens: int = 0) -> None:
    """Check agent-level token budget limit if set."""
    if agent.token_budget and prompt_tokens > agent.token_budget:
        raise BudgetExceededError(f"Agent '{agent.name}' token budget exceeded: {prompt_tokens} > {agent.token_budget}")


def update_orchestration_usage(session: OrchestrationSession, tokens_used: int, cost_incurred: float) -> None:
    """Accurately record token usage and cost incurred by an orchestration session."""
    session.total_tokens_used += tokens_used
    session.total_cost_incurred += cost_incurred
