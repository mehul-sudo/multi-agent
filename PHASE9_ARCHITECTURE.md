# Phase 9 Architecture — Enterprise Workflow Intelligence, Scheduling & Dependency Management

## System Overview

Phase 9 upgrades the Multi-Agent AI Assistant backend with enterprise-grade workflow intelligence, staged parallel execution planning, AST-sandboxed conditional dependencies, optional dependency fallback handling, node priority inheritance, timezone-aware schedule dispatching, misfire policies, and idempotency protection.

---

## Key Architecture & Core Components

```
+-----------------------------------------------------------------------------------+
|                                 API Layer v1                                      |
|  POST /schedules/<id>/pause | POST /schedules/<id>/resume | POST /schedules/<id>/cancel|
|  GET /workflows/<id>/execution-plan                                              |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                               Services Layer                                      |
|                                                                                   |
|  +------------------------------+     +----------------------------------------+  |
|  |   Condition Evaluator Engine |     |   Execution Plan Service               |  |
|  |   AST-Sandboxed (No raw eval)|     |   Staged Parallel Topological Sort     |  |
|  +--------------+---------------+     +-------------------+--------------------+  |
|                 |                                         |                       |
|                 +-------------------+---------------------+                       |
|                                     |                                             |
|                                     v                                             |
|  +-----------------------------------------------------------------------------+  |
|  |   Workflow Execution Engine & Schedule Dispatcher                           |  |
|  |   Priority Inheritance, Optional/Conditional Edge Evaluation,                |  |
|  |   Misfire Policies (fire_once, skip), Timezone Calculations (zoneinfo)      |  |
|  +-----------------------------------------------------------------------------+  |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                Database & Models                                  |
|  - Workflow (priority)                                                            |
|  - WorkflowDependency (is_optional, condition)                                   |
|  - WorkflowExecutionPlan (stages, node_priorities, dependency_rules)             |
|  - WorkflowSchedule (timezone, misfire_policy, idempotency_key, status)          |
+-----------------------------------------------------------------------------------+
```

---

## 1. Safe AST Condition Evaluator

- **Location**: `app/services/condition_evaluator.py`
- **Security Guarantee**: Uses Python `ast.parse` and recursive whitelist node inspection (`_validate_ast_node`). Zero use of `eval()` or `exec()`.
- **Supported Expressions**:
  - Comparators: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`, `is`, `is not`
  - Logical operators: `and`, `or`, `not`
  - Arithmetic: `+`, `-`, `*`, `/`, `%`
  - Identifiers & Subscripting: `node_outputs['node_name']['key']`, `inputs.count`, `context.flag`
- **Safety Enforcement**: Rejects function calls, module imports, statement execution, and dunder attribute access (`__class__`, `__globals__`).

---

## 2. Staged Parallel Execution Plans & Priority Inheritance

- **Location**: `app/services/execution_plan_service.py`
- **Staged Staging**: Partitions workflow DAG nodes into parallel execution stages level-by-level (Stage 0: in-degree 0 nodes; Stage 1: nodes dependent only on Stage 0, etc.).
- **Priority Inheritance**:
  $$\text{Node Priority} = \text{Workflow Priority} + \text{Node Base Priority} + \max_{\text{parents}}(\text{Parent Inherited Priority})$$
- **Model**: `WorkflowExecutionPlan` records `stages` (JSON list of public IDs), `node_priorities` (JSON map), and `dependency_rules`.

---

## 3. Optional & Conditional Dependency Resolution

- **Optional Dependencies (`is_optional=True`)**: If an upstream dependency is marked optional and fails or skips, the target node is allowed to execute as long as its non-optional mandatory dependencies pass.
- **Conditional Dependencies (`condition="..."`)**: Evaluated at runtime against the execution context (`node_outputs`, `inputs`, `context`). If the condition evaluates to `False`, non-optional dependency edges trigger an upstream check failure while optional edges are ignored.

---

## 4. Advanced Scheduling & Misfire Policies

- **Location**: `app/services/schedule_service.py`
- **Timezone Awareness**: Converts cron iterators (`croniter`) using `zoneinfo.ZoneInfo(tz_name)` into standardized UTC datetimes.
- **Misfire Policies**:
  - `fire_once`: Fires one run immediately if execution was missed, recalculating future `next_run_at`.
  - `skip`: Skips stale execution runs if missed by > 300s, advancing `next_run_at` to the upcoming valid window.
- **Lifecycle Management**: APIs for `pause` (`status="paused"`), `resume` (`status="active"`), and `cancel` (`status="cancelled"`).
- **Idempotency**: `create_schedule` accepts an `idempotency_key` string to prevent duplicate schedule creation under concurrent retries.

---

## 5. Database Schema & Migration

- **Migration Revision**: `g1h2i3j4k5l6` (`create_phase9_intelligence_and_execution_plan_tables.py`)
- **Schema Updates**:
  - `workflows.priority`: `Integer`, default 1
  - `workflow_dependencies.is_optional`: `Boolean`, default False
  - `workflow_dependencies.condition`: `Text`, nullable
  - `workflow_execution_plans` table created with FKs to `workflows.id` and `workflow_executions.id`.

---

## 6. Phase 9 API Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/schedules/<id>/pause` | Pause an active schedule |
| `POST` | `/api/v1/schedules/<id>/resume` | Resume a paused schedule |
| `POST` | `/api/v1/schedules/<id>/cancel` | Permanently cancel a schedule |
| `GET` | `/api/workflows/<id>/execution-plan` | Retrieve staged execution plan for workflow |
