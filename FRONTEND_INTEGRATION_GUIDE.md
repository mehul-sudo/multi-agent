# Frontend Integration Guide — Multi-Agent AI Assistant Backend

## 1. Overview & Setup

The **Multi-Agent AI Assistant for Enterprise Automation** backend exposes RESTful APIs designed for seamless frontend integration (React, Vue, Next.js, Angular).

- **Base URL**: `http://localhost:5000/api` (v1: `http://localhost:5000/api/v1`)
- **Authentication**: HTTP Bearer JWT Header (`Authorization: Bearer <JWT_ACCESS_TOKEN>`)
- **Content Type**: `application/json`
- **CORS**: Pre-configured for local frontend development origins.

---

## 2. API Response Envelope

All endpoints return a standardized JSON envelope:

### Success Response:
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... },
  "error": null
}
```

### Error Response:
```json
{
  "success": false,
  "message": "Invalid email or password",
  "data": null,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password",
    "details": []
  }
}
```

---

## 3. Core Frontend Flows

### A. Authentication & Token Management

1. **User Registration** (`POST /api/auth/register` or `POST /api/users`):
   ```json
   { "username": "alice", "email": "alice@example.com", "password": "Password123!" }
   ```
2. **User Login** (`POST /api/auth/login`):
   - Store `access_token` in memory or secure storage.
   - Store `refresh_token` securely.
3. **Token Refresh** (`POST /api/auth/refresh`):
   - Pass `Authorization: Bearer <REFRESH_TOKEN>` to issue a new access token when HTTP `401 TOKEN_EXPIRED` occurs.
4. **Logout** (`POST /api/auth/logout`):
   - Invalidates token on backend blocklist.

---

### B. Dashboard Statistics & Analytics

Fetch top-level dashboard metrics using `GET /api/v1/analytics/summary`:

```json
{
  "success": true,
  "message": "Summary analytics retrieved successfully",
  "data": {
    "total_workflows": 12,
    "total_agents": 4,
    "total_jobs": 28,
    "total_tokens_consumed": 45200,
    "total_cost_usd": 0.904
  },
  "error": null
}
```

Additional analytics endpoints for charts & tables:
- `GET /api/v1/analytics/usage` (Token consumption breakdown)
- `GET /api/v1/analytics/costs` (Cost by LLM provider & model)
- `GET /api/v1/analytics/workflows` (Workflow execution success/failure counts)

---

### C. Workflow Construction & DAG Graph Data

1. **Create Workflow** (`POST /api/workflows`):
   ```json
   { "name": "Monthly Financial Report", "description": "Extract, analyze, and publish Q3 financial metrics." }
   ```
2. **Add Workflow Task Nodes** (`POST /api/workflows/{id}/nodes`):
   ```json
   { "name": "Fetch Sales Data", "agent_id": "<AGENT_PUBLIC_ID>", "instructions": "Query Q3 SQL DB." }
   ```
3. **Bind Task Dependency Edges (DAG)** (`POST /api/workflows/{id}/dependencies`):
   ```json
   { "source_node_id": "<DATA_NODE_ID>", "target_node_id": "<ANALYSIS_NODE_ID>" }
   ```
4. **DAG Graph Structure for Visualizers (React Flow / Cytoscape)**:
   - Retrieve `GET /api/workflows/{id}`. `nodes` array contains task details; `dependencies` array contains directed edges.

---

### D. Workflow Execution & Real-Time Polling

1. **Trigger Workflow Execution** (`POST /api/workflows/{id}/execute`):
   - Returns execution `job_id`.
2. **Poll Execution Status** (`GET /api/v1/jobs/{job_id}`):
   - Poll status every **2-3 seconds**.
   - Possible statuses: `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.
3. **Retrieve Task Results & Context**:
   - `GET /api/v1/jobs/{job_id}/result` returns synthesized outputs upon completion.

---

### E. Human Approval Checkpoints

1. **List Pending Approvals** (`GET /api/v1/approvals/pending`):
   - Displays approval notifications requiring executive review.
2. **Approve Action** (`POST /api/v1/approvals/{approval_id}/approve`):
   ```json
   { "decision_notes": "Approved for distribution." }
   ```
3. **Reject Action** (`POST /api/v1/approvals/{approval_id}/reject`):
   ```json
   { "rejection_reason": "Data needs further verification." }
   ```

---

## 4. Frontend Best Practices

1. **Request Correlation ID**: Attach `X-Correlation-ID: <UUID>` header to requests for end-to-end telemetry.
2. **Automatic Retry on Token Expiry**: Intercept `401 TOKEN_EXPIRED` responses and automatically call `POST /api/auth/refresh`.
3. **Pagination Handling**: All list endpoints return pagination metadata:
   ```json
   {
     "items": [...],
     "pagination": { "page": 1, "page_size": 20, "total": 45, "total_pages": 3 }
   }
   ```
