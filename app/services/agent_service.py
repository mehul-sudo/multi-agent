"""
Agent Service.

Handles business logic and database interactions for AI Agents.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from app.extensions import db
from app.models.agent import (
    AGENT_STATUS_ACTIVE,
    AGENT_STATUS_ARCHIVED,
    AGENT_STATUS_DISABLED,
    Agent,
)
from app.services.audit_service import log_audit_event
from app.utils.pagination import paginate_query


def create_agent(user_id: int, data: dict) -> Agent:
    """Create a new Agent entity for a user."""
    agent = Agent(
        user_id=user_id,
        name=data["name"],
        description=data.get("description"),
        agent_type=data.get("agent_type", "custom"),
        system_instructions=data["system_instructions"],
        provider=data.get("provider", "mock"),
        model=data.get("model", "mock-v1"),
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens", 1000),
        token_budget=data.get("token_budget"),
        cost_budget=data.get("cost_budget"),
        fallback_provider=data.get("fallback_provider"),
        configuration=data.get("configuration", {}),
        capabilities=data.get("capabilities", []),
        status=AGENT_STATUS_ACTIVE,
        version=1,
    )
    db.session.add(agent)
    db.session.commit()

    log_audit_event(
        event_type="AGENT_CREATED",
        resource_type="agent",
        resource_id=agent.public_id,
        user_id=user_id,
        event_data={"name": agent.name, "agent_type": agent.agent_type, "provider": agent.provider, "model": agent.model},
    )

    return agent


def get_agent_by_public_id(public_id: str, user_id: int | None = None) -> Agent | None:
    """Retrieve an agent by its public_id, optionally scoped by user ownership."""
    query = Agent.query.filter_by(public_id=public_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def list_agents(
    user_id: int,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    agent_type: str | None = None,
) -> dict:
    """List agents owned by a user with filtering and pagination."""
    query = Agent.query.filter_by(user_id=user_id)

    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Agent.status != AGENT_STATUS_ARCHIVED)

    if agent_type:
        query = query.filter_by(agent_type=agent_type)

    query = query.order_by(Agent.id.asc())
    return paginate_query(query, page=page, page_size=page_size)


def update_agent(agent: Agent, user_id: int, updates: dict) -> Agent:
    """Update fields on an existing Agent."""
    updated_any = False
    for field in (
        "name",
        "description",
        "agent_type",
        "system_instructions",
        "provider",
        "model",
        "temperature",
        "max_tokens",
        "token_budget",
        "cost_budget",
        "fallback_provider",
        "configuration",
        "capabilities",
    ):
        if field in updates and updates[field] is not None:
            setattr(agent, field, updates[field])
            updated_any = True

    if updated_any:
        agent.version += 1
        db.session.commit()

        log_audit_event(
            event_type="AGENT_UPDATED",
            resource_type="agent",
            resource_id=agent.public_id,
            user_id=user_id,
            event_data={"version": agent.version},
        )

    return agent


def set_agent_status(agent: Agent, user_id: int, new_status: str) -> Agent:
    """Change agent status (e.g. activate, disable, archive)."""
    if agent.status != new_status:
        old_status = agent.status
        agent.status = new_status
        db.session.commit()

        log_audit_event(
            event_type=f"AGENT_{new_status.upper()}",
            resource_type="agent",
            resource_id=agent.public_id,
            user_id=user_id,
            event_data={"previous_status": old_status, "new_status": new_status},
        )

    return agent


def archive_or_delete_agent(agent: Agent, user_id: int) -> bool:
    """Soft archive an agent if referenced by nodes/executions, or delete if unreferenced."""
    # Check if agent has dependent task executions or nodes
    if agent.nodes.count() > 0 or agent.task_executions.count() > 0:
        set_agent_status(agent, user_id, AGENT_STATUS_ARCHIVED)
        return False  # Archived
    else:
        log_audit_event(
            event_type="AGENT_DELETED",
            resource_type="agent",
            resource_id=agent.public_id,
            user_id=user_id,
            event_data={"name": agent.name},
        )
        db.session.delete(agent)
        db.session.commit()
        return True  # Deleted
