"""
Agent Registry & Discovery.

Maintains a mapping of registered BaseAgent implementations and exposes lookup utilities.
"""

from typing import Dict, List, Optional, Type

from app.agents.base import BaseAgent

_AGENT_REGISTRY: Dict[str, BaseAgent] = {}


def register_agent(agent_instance: BaseAgent) -> None:
    """Register a BaseAgent instance into the global agent registry."""
    _AGENT_REGISTRY[agent_instance.agent_type] = agent_instance


def get_agent_instance(agent_type: str) -> Optional[BaseAgent]:
    """Retrieve a registered BaseAgent by agent_type string."""
    return _AGENT_REGISTRY.get(agent_type)


def list_registered_agent_types() -> List[str]:
    """Return a list of all currently registered agent_type strings."""
    return list(_AGENT_REGISTRY.keys())


def is_agent_registered(agent_type: str) -> bool:
    """Check if an agent_type has a specialized implementation registered."""
    return agent_type in _AGENT_REGISTRY
