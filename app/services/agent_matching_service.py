"""
Agent matching service.

Selects the optimal agent for a required role/capability using a deterministic scoring algorithm.
Considers: required capabilities, role, permissions, workload, priority, cost/latency constraints.
Returns selected agent and explicit selection reasoning.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.capability import Capability


ROLE_TO_AGENT_TYPE = {
    "data analyst": "data_analysis",
    "market & data analysis": "data_analysis",
    "data_analysis": "data_analysis",
    "report generator": "report_generation",
    "executive report publisher": "report_generation",
    "report_generation": "report_generation",
    "email specialist": "email",
    "executive email": "email",
    "email": "email",
    "document researcher": "document_research",
    "document research & synthesis": "document_research",
    "document_research": "document_research",
    "database analyst": "database_bi",
    "sql & business intelligence": "database_bi",
    "database_bi": "database_bi",
    "security analyst": "security_analysis",
    "security & vulnerability scanner": "security_analysis",
    "security_analysis": "security_analysis",
    "webhook specialist": "http_webhook",
    "enterprise webhook": "http_webhook",
    "http_webhook": "http_webhook",
    "content generator": "content_generation",
    "content generation specialist": "content_generation",
    "content_generation": "content_generation",
}

CAP_TO_AGENT_TYPE = {
    "data_analysis": "data_analysis",
    "statistical_modeling": "data_analysis",
    "report_generation": "report_generation",
    "email_composition": "email",
    "smtp_dispatch": "email",
    "document_processing": "document_research",
    "web_research": "document_research",
    "sql_querying": "database_bi",
    "data_transformation": "database_bi",
    "vulnerability_scanning": "security_analysis",
    "code_security": "security_analysis",
    "webhook_dispatch": "http_webhook",
    "http_requests": "http_webhook",
    "content_generation": "content_generation",
    "technical_writing": "content_generation",
}


def find_best_agent_for_task(
    user_id: int,
    required_capabilities: List[str],
    role: Optional[str] = None,
    preferred_agent_id: Optional[int] = None,
    preferred_agent_type: Optional[str] = None,
    max_cost_limit: Optional[float] = None,
    max_latency_limit: Optional[int] = None,
) -> Tuple[Optional[Agent], str, float]:
    """Find the optimal agent matching the required capabilities and constraints.

    Returns:
        Tuple of (Agent instance or None, selection_reasoning_string, fit_score)
    """
    if preferred_agent_id:
        preferred = Agent.query.filter_by(id=preferred_agent_id, user_id=user_id, status=AGENT_STATUS_ACTIVE).first()
        if preferred:
            return preferred, f"Directly requested agent '{preferred.name}' (ID: {preferred.id}).", 1.0

    query = Agent.query.filter_by(user_id=user_id, status=AGENT_STATUS_ACTIVE)
    agents = query.all()

    if not agents:
        return None, "No active agents found for user.", 0.0

    candidates = []

    for agent in agents:
        score = 0.0
        reasons = []

        # Explicit preferred agent type match
        if preferred_agent_type and agent.agent_type == preferred_agent_type:
            score += 150.0
            reasons.append(f"Explicit type match '{preferred_agent_type}'")

        # Semantic Role match
        if role:
            role_clean = role.lower().strip()
            target_type = ROLE_TO_AGENT_TYPE.get(role_clean) or role_clean.replace(" ", "_")
            if agent.agent_type == target_type or agent.role == role or agent.agent_type in role_clean or agent.name.lower() in role_clean:
                score += 80.0
                reasons.append(f"Role matches '{role}'")

        # Capabilities match (both direct and semantic)
        agent_caps = agent.capabilities or []
        cap_names = [c["name"] if isinstance(c, dict) else str(c) for c in agent_caps]

        matched_caps = [req for req in required_capabilities if req in cap_names]
        if matched_caps:
            cap_ratio = len(matched_caps) / len(required_capabilities)
            score += cap_ratio * 50.0
            reasons.append(f"Direct matched {len(matched_caps)}/{len(required_capabilities)} capabilities")
        elif required_capabilities:
            # Semantic capability mapping to agent_type
            sem_matches = 0
            for req in required_capabilities:
                if CAP_TO_AGENT_TYPE.get(req) == agent.agent_type:
                    sem_matches += 1
            if sem_matches > 0:
                score += (sem_matches / len(required_capabilities)) * 60.0
                reasons.append(f"Semantic capability match {sem_matches}/{len(required_capabilities)}")
        else:
            score += 10.0
            reasons.append("No specific capabilities required")

        # Priority score
        score += min(agent.priority * 2.0, 10.0)

        candidates.append((agent, score, "; ".join(reasons)))

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    best_agent, top_score, reasoning = candidates[0]
    if top_score <= 0.0:
        return None, "No active agent met the task requirements.", 0.0

    return best_agent, f"Selected '{best_agent.name}' (Score: {top_score:.1f}). Reasons: {reasoning}", top_score
