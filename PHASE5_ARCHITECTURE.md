# Phase 5: Multi-Agent Workflow Orchestration Engine Architecture

## Overview
Phase 5 implements a robust, production-quality Multi-Agent Workflow Orchestration Engine for enterprise automation. It allows users to define specialized AI Agents, compose multi-agent workflows as Directed Acyclic Graphs (DAGs), validate workflow graphs for cycles and errors, and execute workflows deterministically with state tracking, retries, context passing, and idempotency protection.

---

## 1. Component Architecture & Data Models

### Database Domain Models (`app/models/`)
- `Agent`: Specialized AI worker entity (`agents` table).
- `Workflow`: Workflow container definition (`workflows` table).
- `WorkflowNode`: Unit of task work assigned to an Agent or system action (`workflow_nodes` table).
- `WorkflowDependency`: Directed dependency edge (`workflow_dependencies` table).
- `WorkflowExecution`: Single run instance of a workflow (`workflow_executions` table).
- `TaskExecution`: Node-level execution record (`task_executions` table).
- `AuditEvent`: Security and operational audit log record (`audit_events` table).

---

## 2. Graph Validation Algorithm
The Workflow Graph Validation Service (`app/services/graph_validation_service.py`) checks:
1. **Node & Agent References**: Verifies referenced agents exist and are active.
2. **Edge Validity**: Rejects self-dependencies (`source == target`) and duplicate edges.
3. **Cycle Detection & Topological Sort**: Implements Kahn's Algorithm (BFS topological sort) to detect cycles (`WORKFLOW_CYCLE_DETECTED`).
4. **Isolated Nodes**: Warns when nodes have no incoming or outgoing connections in multi-node workflows.
5. **Configuration Sanity**: Validates positive timeout seconds and non-negative retry limits.

---

## 3. Execution Engine & State Machine
The execution engine (`app/services/execution_engine.py`) provides provider-agnostic execution:
- **ExecutionContext**: Manages input values, node outputs, and `$context.<key>` / `$input.<key>` resolution.
- **Topological Task Scheduling**: Evaluates ready tasks when prerequisite dependencies succeed (or fail according to dependency type).
- **Retry Policy**: Executes tasks up to `retry_limit` times upon failure, tracking `attempt_number`.
- **State Machine Transitions**:
  - Workflow States: `draft` -> `active` -> `archived` / `disabled`
  - Workflow Execution States: `queued` -> `running` -> `completed` / `failed` / `cancelled` / `partially_completed`
  - Task Execution States: `pending` -> `blocked` / `ready` -> `running` -> `retrying` -> `completed` / `failed` / `skipped` / `cancelled`

---

## 4. API Endpoints
- **Agent API (`/api/agents`)**: Create, list (paginated & filtered), retrieve, patch update, activate, disable, archive/delete.
- **Workflow API (`/api/workflows`)**: Create draft, list, retrieve, patch update, node CRUD, dependency CRUD, validate DAG, activate, archive.
- **Execution API (`/api/executions` & `/api/workflows/<id>/execute`)**: Trigger execution (with optional idempotency key), list, detail, cancel, retry, list task executions.

---

## 5. Security & Audit Logging
- **Authentication**: All Phase 5 endpoints require JWT bearer tokens (`@jwt_required()`).
- **Authorization**: Ownership checks prevent cross-user resource modification or access.
- **Audit Logging**: `log_audit_event()` automatically redacts sensitive key patterns (`password`, `token`, `secret`, `jwt`).

---

## 6. Future Integration Strategy
- **LLM Adapters**: Replace `MockLocalAgentExecutor` with real LLM provider integration (OpenAI, Anthropic, Gemini).
- **Asynchronous Task Queue**: Transition execution engine invocation to Celery + Redis workers for asynchronous distributed background processing.
