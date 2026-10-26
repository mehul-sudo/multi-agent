"""
Workflow Schedule Pydantic Schemas (v2).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScheduleCreateSchema(BaseModel):
    """Input for creating a workflow schedule."""

    schedule_type: str = Field(default="cron", pattern="^(cron|interval|one_time)$")
    cron_expression: Optional[str] = Field(default=None, max_length=100)
    interval_seconds: Optional[int] = Field(default=None, ge=10)
    timezone: str = Field(default="UTC", max_length=50)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    misfire_policy: str = Field(default="fire_once", max_length=30)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=255)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, value: Optional[str], info) -> Optional[str]:
        schedule_type = info.data.get("schedule_type", "cron")
        if schedule_type == "cron":
            if not value:
                raise ValueError("cron_expression is required when schedule_type is 'cron'.")
            if not croniter.is_valid(value):
                raise ValueError(f"Invalid cron expression: '{value}'.")
        return value

    @field_validator("interval_seconds")
    @classmethod
    def validate_interval(cls, value: Optional[int], info) -> Optional[int]:
        schedule_type = info.data.get("schedule_type")
        if schedule_type == "interval" and not value:
            raise ValueError("interval_seconds is required when schedule_type is 'interval'.")
        return value


class ScheduleUpdateSchema(BaseModel):
    """Input for updating a schedule."""

    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = Field(default=None, ge=10)
    is_enabled: Optional[bool] = None
    input_data: Optional[Dict[str, Any]] = None
    misfire_policy: Optional[str] = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not croniter.is_valid(value):
            raise ValueError(f"Invalid cron expression: '{value}'.")
        return value


class ScheduleResponseSchema(BaseModel):
    """Response representation of a WorkflowSchedule."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    workflow_id: int
    schedule_type: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    timezone: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    status: str
    is_enabled: bool
    misfire_policy: str
    input_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ScheduleListResponseSchema(BaseModel):
    """Paginated response for workflow schedules."""

    items: List[ScheduleResponseSchema]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
