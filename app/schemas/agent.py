"""
Agent request/response schemas (Pydantic v2).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.agent import KNOWN_AGENT_TYPES, SUPPORTED_AGENT_STATUSES


class AgentCreateSchema(BaseModel):
    """Input for creating an agent."""

    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    agent_type: str = Field(default="custom", max_length=50)
    system_instructions: str = Field(min_length=1, max_length=10000)
    provider: str = Field(default="mock", max_length=50)
    model: str = Field(default="mock-v1", max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=8192)
    token_budget: Optional[int] = Field(default=None, ge=1)
    cost_budget: Optional[float] = Field(default=None, ge=0.0)
    fallback_provider: Optional[str] = Field(default=None, max_length=50)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[Any] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Agent name must not be blank.")
        return stripped

    @field_validator("system_instructions")
    @classmethod
    def instructions_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("System instructions must not be blank.")
        return stripped

    @field_validator("provider", "fallback_provider")
    @classmethod
    def validate_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from app.llm.registry import provider_registry
        supported = provider_registry.list_providers()
        val_lower = value.strip().lower()
        if val_lower not in supported:
            raise ValueError(f"Provider '{value}' is not supported. Supported providers: {supported}")
        return val_lower

    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        for key in value.keys():
            if any(s in str(key).lower() for s in ("password", "secret_key", "jwt_secret", "private_key", "api_key")):
                raise ValueError(f"Sensitive key '{key}' is not allowed in agent configuration.")
        return value


class AgentUpdateSchema(BaseModel):
    """Input for updating an agent."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    agent_type: Optional[str] = Field(default=None, max_length=50)
    system_instructions: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    provider: Optional[str] = Field(default=None, max_length=50)
    model: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)
    token_budget: Optional[int] = Field(default=None, ge=1)
    cost_budget: Optional[float] = Field(default=None, ge=0.0)
    fallback_provider: Optional[str] = Field(default=None, max_length=50)
    configuration: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[Any]] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Agent name must not be blank.")
        return stripped

    @field_validator("provider", "fallback_provider")
    @classmethod
    def validate_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from app.llm.registry import provider_registry
        supported = provider_registry.list_providers()
        val_lower = value.strip().lower()
        if val_lower not in supported:
            raise ValueError(f"Provider '{value}' is not supported. Supported providers: {supported}")
        return val_lower

    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if value is None:
            return value
        for key in value.keys():
            if any(s in str(key).lower() for s in ("password", "secret_key", "jwt_secret", "private_key", "api_key")):
                raise ValueError(f"Sensitive key '{key}' is not allowed in agent configuration.")
        return value


class AgentResponseSchema(BaseModel):
    """Safe public representation of an Agent."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    name: str
    description: Optional[str] = None
    agent_type: str
    system_instructions: str
    provider: str
    model: str
    temperature: float
    max_tokens: int
    token_budget: Optional[int] = None
    cost_budget: Optional[float] = None
    fallback_provider: Optional[str] = None
    configuration: Dict[str, Any]
    capabilities: List[Any]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class AgentListResponseSchema(BaseModel):
    """Paginated response for agents."""

    items: List[AgentResponseSchema]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
