"""
Normalized Request and Response Contracts for Multi-Provider LLM Integration.
"""

from dataclasses import dataclass, field
import uuid
from typing import Any, Dict, List, Optional


@dataclass
class LLMMessage:
    """Represents a single message in a multi-turn conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMToolDefinition:
    """Defines a function/tool that an LLM can invoke."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema specification


@dataclass
class LLMToolCall:
    """Represents a tool call emitted by an LLM."""

    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMUsage:
    """Normalized token usage metric."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    metadata_available: bool = True


@dataclass
class LLMRequest:
    """Normalized LLM Request object supporting all providers cleanly."""

    provider: str = "mock"
    model: str = "mock-v1"
    system_instructions: Optional[str] = None
    messages: List[LLMMessage] = field(default_factory=list)
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 1000
    stop_sequences: List[str] = field(default_factory=list)
    response_format: str = "text"  # "text" or "json"
    json_schema: Optional[Dict[str, Any]] = None
    tools: List[LLMToolDefinition] = field(default_factory=list)
    tool_choice: str = "auto"
    streaming: bool = False
    timeout: float = 30.0
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[int] = None
    agent_id: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_execution_id: Optional[str] = None
    task_execution_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate_limits(
        self,
        max_messages: int = 50,
        max_prompt_chars: int = 100000,
        max_output_tokens_cap: int = 8192,
        max_tools_cap: int = 20,
    ) -> None:
        """Validate strict limit bounds on requests."""
        if len(self.messages) > max_messages:
            raise ValueError(f"Message count ({len(self.messages)}) exceeds limit of {max_messages}.")

        total_chars = sum(len(m.content) for m in self.messages)
        if self.system_instructions:
            total_chars += len(self.system_instructions)
        if total_chars > max_prompt_chars:
            raise ValueError(f"Total prompt characters ({total_chars}) exceeds limit of {max_prompt_chars}.")

        if self.max_tokens > max_output_tokens_cap:
            raise ValueError(f"max_tokens ({self.max_tokens}) exceeds maximum cap of {max_output_tokens_cap}.")

        if len(self.tools) > max_tools_cap:
            raise ValueError(f"Number of defined tools ({len(self.tools)}) exceeds limit of {max_tools_cap}.")


@dataclass
class LLMResponse:
    """Normalized LLM Response object returned by all provider adapters."""

    provider: str
    model: str
    text: str = ""
    json_data: Optional[Dict[str, Any]] = None
    tool_calls: List[LLMToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # "stop", "length", "tool_calls", "content_filter"
    usage: LLMUsage = field(default_factory=LLMUsage)
    request_duration_ms: int = 0
    provider_request_id: Optional[str] = None
    retry_count: int = 0
    is_streaming: bool = False
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
