"""
Workflow, WorkflowNode, and WorkflowDependency request/response schemas (Pydantic v2).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.workflow_dependency import SUPPORTED_DEPENDENCY_TYPES


class WorkflowNodeCreateSchema(BaseModel):
    """Schema for adding a node to a workflow."""

    name: str = Field(min_length=1, max_length=100)
    agent_id: Optional[str] = Field(default=None, description="Public ID of referenced Agent")
    task_type: str = Field(default="agent_task", max_length=50)
    instructions: Optional[str] = Field(default=None, max_length=10000)
    input_mapping: Dict[str, Any] = Field(default_factory=dict)
    output_key: Optional[str] = Field(default=None, max_length=100)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    retry_limit: int = Field(default=3, ge=0, le=20)
    priority: int = Field(default=0, ge=0, le=100)
    position: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Node name must not be blank.")
        return stripped


class WorkflowNodeUpdateSchema(BaseModel):
    """Schema for updating a workflow node."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    agent_id: Optional[str] = None
    task_type: Optional[str] = Field(default=None, max_length=50)
    instructions: Optional[str] = Field(default=None, max_length=10000)
    input_mapping: Optional[Dict[str, Any]] = None
    output_key: Optional[str] = Field(default=None, max_length=100)
    configuration: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=86400)
    retry_limit: Optional[int] = Field(default=None, ge=0, le=20)
    priority: Optional[int] = Field(default=None, ge=0, le=100)
    position: Optional[Dict[str, Any]] = None


class WorkflowNodeResponseSchema(BaseModel):
    """Response schema for a workflow node."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    agent_id: Optional[str] = None
    agent_public_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    name: str
    task_type: str
    instructions: Optional[str] = None
    input_mapping: Dict[str, Any]
    output_key: Optional[str] = None
    configuration: Dict[str, Any]
    timeout_seconds: int
    retry_limit: int
    priority: int
    position: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowDependencyCreateSchema(BaseModel):
    """Schema for creating a workflow dependency edge."""

    source_node_id: str = Field(description="Public ID of source WorkflowNode")
    target_node_id: str = Field(description="Public ID of target WorkflowNode")
    dependency_type: str = Field(default="on_success")
    is_optional: bool = Field(default=False)
    condition: Optional[str] = Field(default=None)

    @field_validator("dependency_type")
    @classmethod
    def validate_dependency_type(cls, value: str) -> str:
        if value not in SUPPORTED_DEPENDENCY_TYPES:
            raise ValueError(f"Dependency type must be one of {SUPPORTED_DEPENDENCY_TYPES}")
        return value


class WorkflowDependencyResponseSchema(BaseModel):
    """Response schema for a workflow dependency edge."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    source_node_id: str
    target_node_id: str
    dependency_type: str
    is_optional: bool = False
    condition: Optional[str] = None
    created_at: datetime


class WorkflowCreateSchema(BaseModel):
    """Input for creating a workflow."""

    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: int = Field(default=1, ge=1, le=100)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Workflow name must not be blank.")
        return stripped


class WorkflowUpdateSchema(BaseModel):
    """Input for updating workflow metadata."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[int] = Field(default=None, ge=1, le=100)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowResponseSchema(BaseModel):
    """Response schema for a Workflow."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    name: str
    description: Optional[str] = None
    status: str
    version: int
    priority: int = 1
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    metadata: Dict[str, Any] = Field(alias="metadata_json")
    nodes: List[WorkflowNodeResponseSchema] = Field(default_factory=list)
    dependencies: List[WorkflowDependencyResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WorkflowListResponseSchema(BaseModel):
    """Paginated response for workflows."""

    items: List[WorkflowResponseSchema]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class WorkflowValidationResponseSchema(BaseModel):
    """Structured response for workflow graph validation."""

    valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    topological_order: List[str]
    graph_statistics: Dict[str, Any]
