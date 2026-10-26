# Phase 7 — Production-Grade Distributed Asynchronous Workflow Execution Backend

## Architectural Overview

Phase 7 converts the synchronous workflow execution foundation into a production-grade distributed execution platform powered by **Celery**, **Redis**, persistent database job tracking, and time-based scheduling.

```
                  +-----------------------------------+
                  |   REST API Layer (/api/v1/jobs)   |
                  +-----------------------------------+
                                    |
            1. Submit Job           v           2. Query DB
      (Deduplicate & Validate) ----------> [ AsyncWorkflowJob DB ]
                                    |
                        3. Celery Dispatch
                                    v
                          +-------------------+
                          |   Redis Broker    |
                          +-------------------+
                                    |
                             4. Pull Job
                                    v
                     +-----------------------------+
                     |  Celery Worker Process      |
                     |  - Late Acknowledgments     |
                     |  - Attempt & Heartbeat Log  |
                     |  - Engine Integration       |
                     +-----------------------------+
                                    |
                             5. Run DAG Nodes
                                    v
                     +-----------------------------+
                     |  Workflow Execution Engine  |
                     |  + LLMAgentExecutor         |
                     |  + Provider Adapters        |
                     +-----------------------------+
```

---

## 1. Core Infrastructure & Configuration

### Application Factory & Celery Context
- **Factory (`app/celery_app.py`)**: `init_celery(app)` binds Celery instance config with the Flask app factory. Celery tasks execute inside `app.app_context()`.
- **Eager Test Execution**: `TestingConfig` sets `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True` so test suites run synchronously without requiring a live Redis server.
- **Production Broker/Backend**: Environment-configured via `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` (default `redis://localhost:6379/0`).

---

## 2. Queue Architecture & Worker Startup Commands

### Logical Queue Registry (`app/utils/queues.py`)
- `default`: General asynchronous workflow tasks.
- `high_priority`: Time-critical automation workflows.
- `llm`: Dedicated queue for heavy LLM task nodes.
- `integrations`: External enterprise tool API tasks.
- `maintenance`: Periodic cleanup, stale job recovery, and schedule processing.
- `recovery`: Retried or recovered worker failure tasks.

### Worker & Scheduler Launch Commands
```bash
# Start Worker for all queues
celery -A celery_worker.celery worker --loglevel=INFO -Q default,high_priority,llm,integrations,maintenance,recovery

# Start Scheduler (Celery Beat)
celery -A celery_worker.celery beat --loglevel=INFO
```

---

## 3. Database Models & Schema Migrations

- **`async_workflow_jobs`**: Persistent status, priority, queue, Celery task ID, idempotency key, correlation ID, progress, and result payload.
- **`execution_attempts`**: Individual worker attempts, durations, heartbeats, and recovery reasons.
- **`workflow_schedules`**: Time-based cron (`*/5 * * * *`), interval, and one-time trigger specifications.
- **`worker_health`**: Worker node heartbeats, hostname, active task count, and assigned queues.
- **Migration (`e1f2a3b4c5d6`)**: Alembic migration script for all Phase 7 tables with indexed foreign keys and public IDs.

---

## 4. API Specification (/api/v1)

### Jobs API
- `POST /api/v1/workflows/{workflow_id}/jobs`: Submit workflow job asynchronously (returns `202 Accepted` or `200 OK` if deduplicated via idempotency key).
- `GET /api/v1/jobs/{job_id}`: Retrieve safe job execution status and progress.
- `POST /api/v1/jobs/{job_id}/cancel`: Cooperative job cancellation & Celery task revocation.
- `POST /api/v1/jobs/{job_id}/retry`: Re-dispatch failed/cancelled job with attempt tracking.
- `GET /api/v1/jobs`: List user jobs with status/workflow filters and pagination.
- `GET /api/v1/jobs/{job_id}/result`: Retrieve job result output payload safely.

### Schedules API
- `POST /api/v1/workflows/{workflow_id}/schedules`: Create workflow schedule (cron or interval).
- `GET /api/v1/schedules`: List user's workflow schedules.
- `GET /api/v1/schedules/{schedule_id}`: Retrieve schedule detail.
- `PATCH /api/v1/schedules/{schedule_id}`: Enable/disable or update cron expression.
- `DELETE /api/v1/schedules/{schedule_id}`: Delete workflow schedule.

### Admin Monitoring API (Requires `role == "admin"`)
- `GET /api/v1/admin/workers`: System-wide worker node heartbeats, active tasks, and queue backlog statistics.
- `GET /api/v1/admin/dead_letter`: Inspect dead-lettered jobs.
- `POST /api/v1/admin/dead_letter/{job_id}/requeue`: Re-queue dead-lettered job for execution.

---

## 5. Reliability, Recovery & Dead-Letter Policy

1. **Idempotency Deduplication**: Submitting a job with an existing `idempotency_key` returns the existing job without re-dispatching duplicate tasks.
2. **Concurrency Limits**:
   - `MAX_USER_CONCURRENT_JOBS` (default 10)
   - `MAX_WORKFLOW_CONCURRENT_JOBS` (default 5)
3. **Stale Job Recovery**: `detect_and_recover_stale_jobs()` identifies jobs whose worker heartbeats expired (>300s). Recoverable jobs are re-queued; jobs exceeding `max_retries` transition to `DEAD_LETTERED`.
4. **Dead-Letter Storage**: Permanent failures are logged with safe error messages and audit events (`JOB_DEAD_LETTERED`) for administrative inspection.
