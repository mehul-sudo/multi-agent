"""
Workflow execution and task execution request/response schemas (Pydantic v2).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkflowExecuteSchema(BaseModel):
    """Input for executing a workflow."""

    input_data: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=100)


class TaskExecutionResponseSchema(BaseModel):
    """Response schema for a single task execution."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    workflow_execution_id: Optional[str] = None
    workflow_node_id: Optional[str] = None
    node_name: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    status: str
    attempt_number: int
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_data: Dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class WorkflowExecutionResponseSchema(BaseModel):
    """Response schema for a Workflow Execution."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    workflow_id: Optional[str] = None
    triggered_by: str
    status: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    context_data: Dict[str, Any]
    idempotency_key: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    task_executions: List[TaskExecutionResponseSchema] = Field(default_factory=list)


class WorkflowExecutionListResponseSchema(BaseModel):
    """Paginated response for workflow executions."""

    items: List[WorkflowExecutionResponseSchema]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
