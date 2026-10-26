"""
Worker Health Pydantic Schemas (v2).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkerHealthResponseSchema(BaseModel):
    """Worker node status and metrics."""

    model_config = ConfigDict(from_attributes=True)

    worker_id: str
    hostname: str
    queues: List[str]
    active_tasks_count: int
    registered_tasks: List[str]
    status: str
    started_at: datetime
    last_heartbeat_at: datetime
    version: Optional[str] = "1.0.0"


class QueueStatsSchema(BaseModel):
    """Metrics for a message queue."""

    queue_name: str
    active_jobs: int
    queued_jobs: int
    retrying_jobs: int
    failed_jobs: int
    completed_jobs: int


class SystemMonitoringOverviewSchema(BaseModel):
    """Comprehensive admin monitoring response."""

    total_active_workers: int
    stale_workers_count: int
    active_jobs_count: int
    queued_jobs_count: int
    failed_jobs_count: int
    dead_lettered_jobs_count: int
    workers: List[WorkerHealthResponseSchema]
    queues: List[QueueStatsSchema]
