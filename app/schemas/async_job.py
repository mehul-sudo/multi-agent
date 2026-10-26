"""
Async Job Pydantic Schemas (v2).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.async_job import SUPPORTED_JOB_STATUSES
from app.utils.queues import validate_queue_name


class JobSubmitSchema(BaseModel):
    """Input parameters for submitting an asynchronous workflow job."""

    priority: int = Field(default=0, ge=0, le=10)
    queue_name: str = Field(default="default", max_length=50)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=255)
    correlation_id: Optional[str] = Field(default=None, max_length=255)
    max_retries: int = Field(default=3, ge=0, le=10)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("queue_name")
    @classmethod
    def check_queue(cls, value: str) -> str:
        return validate_queue_name(value)


class JobCancelSchema(BaseModel):
    """Input parameters for cancelling a job."""

    reason: Optional[str] = Field(default="Cancelled by user.", max_length=1000)


class JobRetrySchema(BaseModel):
    """Input parameters for retrying a failed job."""

    reason: Optional[str] = Field(default="Retried by user.", max_length=1000)
    priority_override: Optional[int] = Field(default=None, ge=0, le=10)


class ExecutionAttemptResponseSchema(BaseModel):
    """Response representation of an execution attempt."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    attempt_number: int
    worker_id: Optional[str] = None
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    failure_category: Optional[str] = None
    retry_reason: Optional[str] = None
    error_code: Optional[str] = None
    duration_ms: Optional[int] = None
    recovery_status: Optional[str] = None


class AsyncJobResponseSchema(BaseModel):
    """Safe public representation of an AsyncWorkflowJob."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    job_type: str
    status: str
    priority: int
    queue_name: str
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    retry_count: int
    max_retries: int
    progress_percentage: float
    current_node_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failure_category: Optional[str] = None
    cancellation_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    worker_id: Optional[str] = None
    workflow_id: int
    created_at: datetime
    updated_at: datetime


class AsyncJobDetailResponseSchema(AsyncJobResponseSchema):
    """Detailed job response including result summary and attempts."""

    result_data: Optional[Dict[str, Any]] = None
    attempts: List[ExecutionAttemptResponseSchema] = Field(default_factory=list)


class JobListResponseSchema(BaseModel):
    """Paginated list response for async jobs."""

    items: List[AsyncJobResponseSchema]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
