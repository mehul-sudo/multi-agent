# System Architecture Blueprint — Multi-Agent AI Assistant for Enterprise Automation

## 1. System Overview

The **Multi-Agent AI Assistant for Enterprise Automation** is an enterprise-grade, distributed AI task orchestration backend built on Flask, SQLAlchemy, Celery, Redis, and multi-provider LLM abstractions (OpenAI, Anthropic, Gemini).

It enables users and enterprise teams to construct, validate, execute, and monitor complex multi-agent workflows defined as Directed Acyclic Graphs (DAGs).

```
                      +-----------------------------+
                      |    REST API (Flask / v1)    |
                      +--------------+--------------+
                                     |
               +---------------------+---------------------+
               |                     |                     |
     +---------v---------+  +--------v--------+  +---------v---------+
     | Auth & Governance |  | Workflow & DAG  |  | Agent Orchestration|
     | (JWT, RBAC, IDOR) |  | Validation      |  | & Planner Service |
     +---------+---------+  +--------+--------+  +---------+---------+
               |                     |                     |
               +---------------------+---------------------+
                                     |
                       +-------------v-------------+
                       |   Celery Worker Queue     |
                       |  (Redis Broker / Backend) |
                       +-------------+-------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
+--------v--------+         +--------v--------+         +--------v--------+
| OpenAI Adapter  |         |Anthropic Adapter|         | Gemini Adapter  |
+--------+--------+         +--------+--------+         +--------+--------+
         |                           |                           |
         +---------------------------+---------------------------+
                                     |
                       +-------------v-------------+
                       | Resilient Execution Engine|
                       | (Circuit Breaker Manager) |
                       +-------------+-------------+
                                     |
                       +-------------v-------------+
                       |   Shared Context Memory   |
                       | (Optimistic CAS Lock / DB)|
                       +---------------------------+
```

---

## 2. Core Architecture Modules

### A. Application Factory & Extensions (`app/__init__.py`, `app/extensions.py`)
- Standard Flask application factory supporting `development`, `testing`, and `production` configurations.
- Extensions wired centrally: SQLAlchemy, Flask-Migrate, Flask-JWT-Extended, Celery, and security middleware (Correlation ID tracking, Rate Limiting, Security Headers `nosniff`, `DENY`, `HSTS`).

### B. User Management, RBAC & Credential IDOR Protection (`app/services/user_service.py`, `app/services/credential_service.py`)
- Role-Based Access Control (`admin`, `platform_admin`, `user`).
- Secure bcrypt password hashing.
- Credential storage with tenant isolation: credential operations require user organization membership validation (`organization_id` authorization check).

### C. Workflow & DAG Engine (`app/services/workflow_service.py`, `app/services/graph_validation_service.py`)
- Directed Acyclic Graph (DAG) validation ensuring zero cycle loops (`validate_workflow_graph`).
- Task node dependency resolution and topological execution planning.
- Node creation, dependency binding, and state management.

### D. Multi-Agent Orchestration & Planner (`app/services/planner_service.py`, `app/services/orchestration_service.py`)
- **Supervisor Agent**: Interprets high-level user objectives ("Generate a monthly business report...") and decomposes them into executable tasks.
- **Agent Selection**: Matches task requirements with specialized agents based on capability tags and system instructions.
- **Agent Communication & Shared Context**: Cross-agent message passing and scoped shared memory (`GLOBAL`, `PLAN`, `TASK`, `AGENT_PRIVATE`).

### E. LLM Provider Abstraction & Resilient Execution Engine (`app/llm/providers/`, `app/services/execution_engine.py`)
- Unified interface for OpenAI (`gpt-4`), Anthropic (`claude-3-5-sonnet`), Gemini (`gemini-1.5-pro`), and deterministic Mock providers.
- **Circuit Breaker Singleton**: Tracks failure thresholds per provider; automatically trips open to protect against cascading supplier outages, with automatic half-open recovery.
- **Token & Cost Tracking**: Accurately records prompt tokens, completion tokens, duration, and estimated USD costs into `LLMUsageLog`.

### F. Asynchronous Job Processing & Resilience (`app/tasks/workflow_tasks.py`, `app/services/job_service.py`, `app/services/schedule_service.py`)
- Celery worker task execution for non-blocking asynchronous jobs.
- Task revocation audit logging (`JOB_CELERY_REVOKED`).
- Session safety: `db.session.remove()` in worker `finally` blocks prevents DB pool leaks.
- Stale job auto-recovery and atomic schedule claiming with server-side `NOW()` and optimistic version locking.

### G. Governance & Human Approval Checkpoints (`app/services/approval_service.py`)
- Human-in-the-loop approval workflow before critical or high-risk tasks are executed.
- Enforces strict separation of duties (requester cannot self-approve).

---

## 3. Database Schema Overview

```
                      +-------------------+
                      |       User        |
                      +---------+---------+
                                |
               +----------------+----------------+
               |                                 |
     +---------v---------+             +---------v---------+
     |     Workflow      |             |       Agent       |
     +---------+---------+             +---------+---------+
               |                                 |
     +---------v---------+                       |
     |   WorkflowNode    |<----------------------+
     +---------+---------+
               |
     +---------v---------+
     |WorkflowDependency |
     +-------------------+

               +----------------------------------+
               |       OrchestrationSession       |
               +----------------+-----------------+
                                |
               +----------------+-----------------+
               |                                  |
     +---------v---------+              +---------v---------+
     |SharedContextRecord|              |  ApprovalRequest  |
     +-------------------+              +-------------------+
```

- **Users**: Credentials, hashed passwords, roles (`user`, `admin`), active status.
- **Agents**: Capabilities, system instructions, role, status.
- **Workflows & WorkflowNodes**: Workflow definitions, task nodes, execution configurations.
- **WorkflowDependencies**: Directed edges defining DAG execution order.
- **AsyncWorkflowJobs**: Background execution job records, statuses (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`), Celery task IDs.
- **OrchestrationSessions**: High-level multi-agent orchestration objectives and execution plans.
- **SharedContextRecords**: Scoped agent memory entries with compare-and-swap (CAS) version keys.
- **ApprovalRequests**: Human-in-the-loop review checkpoints.
- **LLMUsageLogs**: Token counts, durations, and estimated USD costs per LLM request.
