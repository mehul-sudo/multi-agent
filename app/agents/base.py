"""
Base Agent Interface & Contracts.

Defines standard data structures (AgentContext, AgentResult, ArtifactRef)
and the abstract BaseAgent interface required for all enterprise agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ArtifactRef:
    """Represents a file or content artifact produced by an agent."""
    type: str  # e.g., "report", "csv", "json", "pdf", "html"
    name: str
    path: Optional[str] = None
    url: Optional[str] = None
    content: Optional[Any] = None


@dataclass
class AgentContext:
    """Standardized input context passed into an agent for execution."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    instructions: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    previous_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Predictable, structured response envelope returned by all agents."""
    success: bool
    agent_type: str
    task_id: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[ArtifactRef] = field(default_factory=list)
    execution_duration_ms: int = 0
    requires_approval: bool = False
    approval_details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize AgentResult to JSON-friendly dictionary."""
        return {
            "success": self.success,
            "agent_type": self.agent_type,
            "task_id": self.task_id,
            "output": self.output or {},
            "error": self.error,
            "metadata": self.metadata,
            "artifacts": [
                {
                    "type": a.type,
                    "name": a.name,
                    "path": a.path,
                    "url": a.url,
                    "content": a.content if isinstance(a.content, (str, dict, list, int, float, bool)) else str(a.content) if a.content else None,
                }
                for a in self.artifacts
            ],
            "execution_duration_ms": self.execution_duration_ms,
            "requires_approval": self.requires_approval,
            "approval_details": self.approval_details,
        }


class BaseAgent(ABC):
    """Abstract interface that all enterprise agents must inherit and implement."""

    agent_type: str = "generic"
    description: str = "Base Enterprise Agent Interface"
    requires_side_effect_approval: bool = False

    @abstractmethod
    def execute(self, context: AgentContext) -> AgentResult:
        """Run the agent logic using the supplied context and return structured AgentResult."""
        pass
