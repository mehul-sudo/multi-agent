# End-to-End Workflow Demonstration & API Log (`END_TO_END_DEMO.md`)

This document presents sample HTTP request/response payloads, execution steps, and verification logs for a complete multi-agent workflow executed in mock LLM mode.

---

## Realistic Business Scenario

**User Objective**:
> *"Generate a monthly business report using available company data, analyze important trends, create a summary, and prepare the final report."*

---

## 1. User Registration & Authentication

### A. User Registration (`POST /api/auth/register`)

**Request**:
```http
POST /api/auth/register HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "username": "demo_user",
  "email": "demo@example.com",
  "password": "DemoPassword123!"
}
```

**Response (201 Created)**:
```json
{
  "success": true,
  "message": "User created successfully",
  "data": {
    "public_id": "ed3cabf9-3c80-410f-931b-2c4a24e59cfb",
    "username": "demo_user",
    "email": "demo@example.com",
    "role": "user",
    "is_active": true,
    "is_verified": false,
    "created_at": "2026-09-14T10:58:09.123456"
  },
  "error": null
}
```

### B. User Login (`POST /api/auth/login`)

**Request**:
```http
POST /api/auth/login HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "email": "demo@example.com",
  "password": "DemoPassword123!"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "public_id": "ed3cabf9-3c80-410f-931b-2c4a24e59cfb",
      "username": "demo_user",
      "email": "demo@example.com",
      "role": "user"
    }
  },
  "error": null
}
```

---

## 2. Specialized Agent Selection & Registration

### `POST /api/agents`

**Request**:
```http
POST /api/agents HTTP/1.1
Host: localhost:5000
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json

{
  "name": "Data Ingestion Agent",
  "role": "data_collector",
  "system_instructions": "Fetch company sales & metric data."
}
```

**Response (201 Created)**:
```json
{
  "success": true,
  "message": "Agent registered successfully",
  "data": {
    "public_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "name": "Data Ingestion Agent",
    "role": "data_collector",
    "is_active": true
  },
  "error": null
}
```

---

## 3. Workflow DAG Construction

### `POST /api/workflows`

**Request**:
```http
POST /api/workflows HTTP/1.1
Host: localhost:5000
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json

{
  "name": "Monthly Business Report Automation",
  "description": "Generate monthly business report using company data, analyze trends, summarize, and publish."
}
```

**Response (201 Created)**:
```json
{
  "success": true,
  "message": "Workflow created successfully",
  "data": {
    "public_id": "wf-99887766-5544-3322-1100-aaffbbccddee",
    "name": "Monthly Business Report Automation",
    "status": "draft",
    "version": 1
  },
  "error": null
}
```

---

## 4. DAG Task Dependency Binding

### `POST /api/workflows/wf-99887766.../dependencies`

**Request**:
```http
POST /api/workflows/wf-99887766-5544-3322-1100-aaffbbccddee/dependencies HTTP/1.1
Host: localhost:5000
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json

{
  "source_node_id": "node-data-collection-id",
  "target_node_id": "node-trend-analysis-id"
}
```

**Response (201 Created)**:
```json
{
  "success": true,
  "message": "Dependency added successfully",
  "data": {
    "source_node": "Data Collection",
    "target_node": "Trend Analysis",
    "type": "on_success"
  },
  "error": null
}
```

---

## 5. Multi-Agent Orchestration & Supervisor Planning

### `POST /api/v1/orchestrations`

**Request**:
```http
POST /api/v1/orchestrations HTTP/1.1
Host: localhost:5000
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json

{
  "objective": "Generate a monthly business report using available company data, analyze important trends, create a summary, and prepare final report.",
  "priority": 1
}
```

**Response (201 Created)**:
```json
{
  "success": true,
  "message": "Orchestration session created",
  "data": {
    "orchestration": {
      "id": 1,
      "public_id": "orch-11223344-5566-7788-9900-aabbccddeeff",
      "objective": "Generate a monthly business report using available company data...",
      "status": "draft"
    }
  },
  "error": null
}
```

---

## 6. Shared Context Memory

Stored Scoped Context Entries (`GLOBAL` Scope):
```json
{
  "revenue_q3": "$1,450,000",
  "growth_yoy": "+18.4%",
  "trend_insight": "Expansion in enterprise tier driven by security capabilities."
}
```

---

## 7. Governance & Human Approval Checkpoint

### `GET /api/v1/approvals/pending`

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Approvals retrieved",
  "data": {
    "approvals": [
      {
        "id": "3a327264-eefc-42f4-acd8-1fb82024c6cf",
        "requested_action": "Publish Monthly Business Report Q3",
        "risk_level": "medium",
        "explanation": "Requires C-suite approval before external release.",
        "status": "PENDING",
        "created_at": "2026-09-14T10:58:09.654321"
      }
    ]
  },
  "error": null
}
```

### `POST /api/v1/approvals/3a327264.../approve`

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Approval request approved successfully",
  "data": {
    "id": "3a327264-eefc-42f4-acd8-1fb82024c6cf",
    "status": "APPROVED",
    "approval_comments": "Report looks excellent. Approved."
  },
  "error": null
}
```

---

## 8. Analytics & Token Cost Usage Summary

### `GET /api/v1/analytics/summary`

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Summary analytics retrieved successfully",
  "data": {
    "user_id": 1,
    "total_workflows": 1,
    "total_agents": 4,
    "total_jobs": 1,
    "total_tokens_consumed": 3250,
    "total_cost_usd": 0.065
  },
  "error": null
}
```
