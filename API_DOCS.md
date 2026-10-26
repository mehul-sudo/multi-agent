# Comprehensive API Documentation — Multi-Agent AI Assistant

Base URL: `/api` / `/api/v1`  
Authentication: HTTP Bearer JWT Header (`Authorization: Bearer <JWT_ACCESS_TOKEN>`)

All endpoints return a standardized JSON response envelope:
- **Success Response Envelope**:
  ```json
  {
    "success": true,
    "message": "Operation completed successfully",
    "data": { ... },
    "error": null
  }
  ```
- **Error Response Envelope**:
  ```json
  {
    "success": false,
    "message": "Validation failed",
    "data": null,
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Validation failed",
      "details": []
    }
  }
  ```

---

## 1. Authentication (`/api/auth`)

### `POST /api/auth/register`
- **Description**: Self-register a new user account.
- **Auth**: Public
- **Request Body**:
  ```json
  {
    "username": "johndoe",
    "email": "johndoe@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response (201)**: Standard user response object.

### `POST /api/auth/login`
- **Description**: Authenticate user credentials and issue access + refresh JWTs.
- **Auth**: Public
- **Request Body**:
  ```json
  {
    "email": "johndoe@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response (200)**:
  ```json
  {
    "access_token": "<JWT_ACCESS_TOKEN>",
    "refresh_token": "<JWT_REFRESH_TOKEN>",
    "user": { "public_id": "...", "username": "johndoe", "email": "johndoe@example.com", "role": "user" }
  }
  ```

### `POST /api/auth/refresh`
- **Description**: Exchange valid refresh token for a new access token.
- **Auth**: Bearer (Refresh Token)
- **Response (200)**: `{ "access_token": "<NEW_JWT_ACCESS_TOKEN>" }`

### `GET /api/auth/me`
- **Description**: Retrieve authenticated user profile.
- **Auth**: Bearer
- **Response (200)**: User profile data.

### `POST /api/auth/logout`
- **Description**: Invalidate current access token (added to token blocklist).
- **Auth**: Bearer

---

## 2. Workflows (`/api/workflows`)

### `POST /api/workflows`
- **Description**: Create a new automation workflow.
- **Auth**: Bearer
- **Request Body**:
  ```json
  {
    "name": "Data Processing Pipeline",
    "description": "Extract, analyze, and summarize quarterly metrics."
  }
  ```

### `GET /api/workflows`
- **Description**: List user workflows with pagination.
- **Auth**: Bearer

### `GET /api/workflows/{public_id}`
- **Description**: Retrieve workflow details, nodes, and dependency edges.
- **Auth**: Bearer

### `POST /api/workflows/{public_id}/nodes`
- **Description**: Add a task node to a workflow.
- **Auth**: Bearer
- **Request Body**:
  ```json
  {
    "name": "Data Analysis",
    "agent_id": "<AGENT_PUBLIC_ID>",
    "instructions": "Process sales logs."
  }
  ```

### `POST /api/workflows/{public_id}/dependencies`
- **Description**: Add a directed edge dependency between two workflow nodes.
- **Auth**: Bearer
- **Request Body**:
  ```json
  {
    "source_node_id": "<SOURCE_NODE_PUBLIC_ID>",
    "target_node_id": "<TARGET_NODE_PUBLIC_ID>"
  }
  ```

### `POST /api/workflows/{public_id}/execute`
- **Description**: Trigger workflow execution in background worker.
- **Auth**: Bearer
- **Response (201/202)**: Execution job details.

---

## 3. Agents (`/api/agents` & `/api/v1/agents`)

### `GET /api/agents` / `GET /api/v1/agents`
- **Description**: List registered agents and specialized capabilities.
- **Auth**: Bearer

### `POST /api/agents`
- **Description**: Register a custom specialized agent.
- **Auth**: Bearer
- **Request Body**:
  ```json
  {
    "name": "Financial Analyst Agent",
    "role": "analyst",
    "system_instructions": "Analyze company P&L reports."
  }
  ```

### `GET /api/v1/agents/{public_id}`
- **Description**: Get agent configuration and capability metadata.
- **Auth**: Bearer

---

## 4. Multi-Agent Orchestrations (`/api/v1/orchestrations`)

### `POST /api/v1/orchestrations`
- **Description**: Create multi-agent orchestration session from high-level objective.
- **Auth**: Bearer
- **Request Body**:
  ```json
  {
    "objective": "Generate monthly financial report",
    "priority": 1
  }
  ```

### `POST /api/v1/orchestrations/{id}/start`
- **Description**: Execute supervisor agent planning & task delegation.
- **Auth**: Bearer

---

## 5. Jobs & Background Executions (`/api/v1/jobs`)

### `GET /api/v1/jobs`
- **Description**: List asynchronous workflow jobs.
- **Auth**: Bearer

### `GET /api/v1/jobs/{job_id}`
- **Description**: Get job status and execution details.
- **Auth**: Bearer

### `POST /api/v1/jobs/{job_id}/cancel`
- **Description**: Cancel queued or running job safely.
- **Auth**: Bearer

### `POST /api/v1/jobs/{job_id}/retry`
- **Description**: Retry failed or timed out job.
- **Auth**: Bearer

---

## 6. Approvals & Governance (`/api/v1/approvals`)

### `GET /api/v1/approvals/pending` / `GET /api/v1/approvals`
- **Description**: List pending human approval requests assigned to current user.
- **Auth**: Bearer

### `POST /api/v1/approvals/{approval_id}/approve`
- **Description**: Grant approval for pending action.
- **Auth**: Bearer (Approver role)

### `POST /api/v1/approvals/{approval_id}/reject`
- **Description**: Reject pending action with reason.
- **Auth**: Bearer (Approver role)

---

## 7. Analytics & Costs (`/api/v1/analytics`)

### `GET /api/v1/analytics/usage`
- **Description**: Get total prompt, completion, and overall token consumption.
- **Auth**: Bearer

### `GET /api/v1/analytics/costs`
- **Description**: Get estimated USD cost breakdown by LLM provider and model.
- **Auth**: Bearer

### `GET /api/v1/analytics/workflows`
- **Description**: Get workflow execution status counts and success/failure ratios.
- **Auth**: Bearer

### `GET /api/v1/analytics/summary`
- **Description**: Top-level executive summary metrics dashboard.
- **Auth**: Bearer
- **Response (200)**:
  ```json
  {
    "success": true,
    "message": "Summary analytics retrieved successfully",
    "data": {
      "total_workflows": 5,
      "total_agents": 4,
      "total_jobs": 12,
      "total_tokens_consumed": 15400,
      "total_cost_usd": 0.308
    },
    "error": null
  }
  ```
