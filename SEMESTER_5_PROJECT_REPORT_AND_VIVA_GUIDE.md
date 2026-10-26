# Semester 5 Major Project: Multi-Agent AI Assistant for Autonomous Enterprise Automation

---

## 📌 1. Project Abstract & Overview

* **Project Title:** Multi-Agent AI Assistant for Enterprise Automation
* **Domain:** Artificial Intelligence, Distributed Systems, Multi-Agent Systems (MAS), Full-Stack Engineering
* **Tech Stack:**
  * **Backend:** Python 3.13, Flask 3.0, SQLAlchemy ORM, Celery / Redis, Server-Sent Events (SSE), JWT Authentication
  * **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons
  * **External Integrations:** Resend API (Transactional Email), Gmail SMTP, Webhooks (Slack/Discord), SQLite / PostgreSQL
  * **Testing:** Pytest Suite (**343 / 343 Tests Passing - 100% Green**)

### Problem Statement:
Traditional enterprise automation relies on rigid, hardcoded if-else scripts or isolated bots that break when inputs change or require complex coordination. Enterprises need an autonomous, intelligent multi-agent platform capable of decomposing complex business objectives into Directed Acyclic Graphs (DAGs), dynamically executing tasks across specialized agents with real-time feedback, and maintaining strict human-in-the-loop security governance.

### Solution Delivered:
A full-stack, enterprise-grade Multi-Agent platform featuring:
1. **8 Autonomous Specialized Agents** (Email, Data Analysis, Database BI, Document Research, Report Generation, HTTP/Webhook, Security Analysis, Calendar).
2. **Deterministic Topological DAG Execution Engine** supporting sequential and concurrent agent dependencies.
3. **Live Server-Sent Events (SSE) Streaming Terminal** streaming millisecond execution logs to the client UI.
4. **Real-World Live Connectors**: Direct deliverability via modern Resend API and Gmail SMTP, plus external REST Webhooks.
5. **Human-in-the-Loop (HITL) Governance**: Policy-driven pausing for sensitive actions (e.g. sending bulk emails, executing database modifications).
6. **Enterprise Security**: Personal API Keys, 2-Factor Authentication, Rate Limiting, Audit Trails, and RBAC.

---

## 🏗️ 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          React 19 + Vite Frontend                           │
│   • Interactive DAG Workflow Designer       • Real-Time SSE Live Terminal   │
│   • Human-in-the-Loop Approvals Desk        • Connectors & Settings Page    │
│   • Visual Analytics & Execution History    • Personal API Keys & 2FA Cards │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP REST & SSE Stream (JWT Auth)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            Flask 3.0 API Gateway                            │
│   • JWT Auth & RBAC Middleware              • Rate Limiting & Correlation ID│
│   • Real-Time EventSource Stream (/stream)  • Dynamic Configuration Engine  │
└───────────────────┬───────────────────────────────────┬─────────────────────┘
                    │                                   │
┌───────────────────▼─────────────────────┐   ┌─────────▼─────────────────────┐
│      DAG Workflow Execution Engine      │   │   Security & Governance Guard │
│   • Topological Dependency Resolution   │   │   • Risk Assessment (Low/Med) │
│   • Pause / Resume State Transitions    │   │   • Human-in-the-Loop Pausing │
│   • Task Context Propagation            │   │   • Audit Trail Logging       │
└───────────────────┬─────────────────────┘   └─────────┬─────────────────────┘
                    │                                   │
┌───────────────────▼───────────────────────────────────▼─────────────────────┐
│                         8 Specialized AI Agents                             │
│   1. Email Agent (Resend API / SMTP)    5. HTTP/Webhook Agent (REST / SSRF) │
│   2. Data Analysis Agent (Pandas/Stats) 6. Security Analysis Agent (PII/Inj)│
│   3. Database BI Agent (SQL Engine)     7. Report Generation Agent (Files)  │
│   4. Document Research Agent (Parser)   8. Calendar Scheduling Agent (Time) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 3. The 8 Specialized Agents in Detail

| # | Agent Name | Real-Time Execution Capability | Safety & Governance |
|---|---|---|---|
| **1** | **Email Agent** | Dispatches real emails via **Resend API** (`onboarding@resend.dev`) or **Gmail SMTP**. | High-risk recipient actions trigger Human-in-the-Loop pause. |
| **2** | **HTTP / Webhook Agent** | Executes real HTTP calls (GET, POST, PUT, DELETE) to external APIs, Discord, or Slack. | SSRF guardrails prevent attacks against internal private IP networks. |
| **3** | **Data Analysis Agent** | Computes real statistical analytics, percentages, trend analysis, and anomalies. | Validates dataset shape and numerical inputs to prevent execution crashes. |
| **4** | **Database BI Agent** | Runs real SQL queries against SQLite or PostgreSQL databases. | Enforces read-only execution guardrails to prevent accidental DROP/DELETE. |
| **5** | **Document Research Agent**| Extracts structured text, performs regex tokenization, and indexes documents. | Sanitizes untrusted user text uploads before forwarding to subsequent agents. |
| **6** | **Report Generation Agent**| Compiles analytical findings into formatted Markdown/HTML report files on disk. | Verifies directory isolation in `instance/reports/` preventing path traversal. |
| **7** | **Security Analysis Agent**| Real-time scanner for prompt injections, credential leaks, and PII exposure. | Classifies threat level (Low, Medium, Critical) and sanitizes payloads. |
| **8** | **Calendar Agent** | Calculates ISO 8601 timestamps, validates availability, and resolves meeting clashes. | Verifies boundary parameters and duration constraints. |

---

## 🎯 4. Step-by-Step Viva & Presentation Demo Script

Jab aap apne evaluators/professors ke samne project present karein, ye sequence follow karein:

### Step 1: System Overview & Live Integration Status (2 mins)
1. Browser me open karein: **`http://localhost:5173/settings`**.
2. Evaluator ko dikhayein:
   * *"Humara system multi-provider architecture support karta hai."*
   * *"Email Provider me modern **Resend API** and **Gmail SMTP** integrated hain."*
3. **Live Proof:** Niche "Test Live Email Delivery" me apna email daalein aur **"Send Real Test Email"** click karein.
   * Evaluator ko dikhayein: *"Sir, within 2 seconds real email mere Gmail inbox me deliver ho gaya bina kisi mock ya simulation ke."*

### Step 2: Interactive DAG Workflow Execution (3 mins)
1. Navigate to **Workflows** (`http://localhost:5173/workflows`).
2. "Monthly Business Report" ya "Customer Alert Workflow" select karein.
3. Show the DAG graph: explain how nodes have dependencies (e.g. Email Agent depends on Report Generator, which depends on Data Analysis Agent).
4. Click **"Run Workflow"**.

### Step 3: Real-Time SSE Live Terminal (2 mins)
1. Workflow start hote hi **"Live Terminal"** button click karein.
2. Evaluator ko screen par live logs stream hote hue dikhayein:
   * *"Ye logs Server-Sent Events (SSE) protocol se server se direct real-time broadcast ho rahe hain."*
   * Point out: `task_start` event -> Agent computation time in milliseconds -> `task_complete` event.

### Step 4: Human-in-the-Loop Governance & Approvals (2 mins)
1. Navigate to **Approvals** (`http://localhost:5173/approvals`).
2. Dikhayein ki jab agent koi sensitive action (jaise bulk email ya external action) perform karta hai, system automatically execution ko pause kar deta hai.
3. Click **"Approve"** to resume execution.

### Step 5: Enterprise Security & Analytics (1 min)
1. Settings page par **Personal API Keys** card dikhayein (Users can generate scoped API keys with revocation).
2. **2-Factor Authentication** card and **Audit Trail** logs dikhayein.

---

## ❓ 5. Most Frequently Asked Viva Questions & Model Answers

#### Q1: "Why did you use Resend API instead of direct Gmail SMTP?"
> **Answer:** *"In enterprise production systems (like Uber, Vercel, Stripe), applications never use individual personal Gmail SMTP accounts due to Google's rate limits and security passkey restrictions. They use specialized transactional email APIs like Resend or SendGrid. We chose Resend because it delivers emails via a RESTful HTTPS API in under 500ms with zero SMTP port blocking, while still providing a built-in fallback to standard Gmail SMTP if needed."*

#### Q2: "How do your agents coordinate and avoid infinite loops?"
> **Answer:** *"All workflow tasks are modeled as Directed Acyclic Graphs (DAGs). The backend WorkflowExecutionEngine performs a topological sort using Kahn's algorithm before execution starts. If any cycle is detected, graph validation immediately rejects it with a 400 error. Tasks execute strictly in dependency order."*

#### Q3: "How does real-time streaming work between Flask and React?"
> **Answer:** *"Instead of inefficient HTTP polling every second, we implemented Server-Sent Events (SSE) via `/api/v1/execution-stream/<job_id>`. The client uses the native EventSource API. As agents emit events in the execution loop, Flask yields chunked HTTP responses (`mimetype='text/event-stream'`), streaming logs with sub-millisecond latency to the LiveTerminal React component."*

#### Q4: "What security measures have you implemented?"
> **Answer:** *"We implemented enterprise multi-tenant security:
> 1. JWT authentication with token revocation blocklist in Redis/database.
> 2. IP-based rate limiting on sensitive endpoints.
> 3. Security Analysis Agent that scans incoming payloads for Prompt Injection and PII.
> 4. SSRF protection on HTTP Webhook Agent against private RFC1918 subnets.
> 5. Role-Based Access Control (RBAC) and full audit trail logging."*

#### Q5: "How many tests have you written to verify this codebase?"
> **Answer:** *"The project contains an extensive automated test suite with **343 unit and integration tests** covering RBAC, DAG validation, agent execution, streaming, concurrency, and error recovery, all passing with a 100% pass rate in Pytest."*

---

## 🚀 6. Startup Commands

### Start Backend (Flask):
```powershell
# Open terminal 1 in project root
python run.py
# Backend runs on http://127.0.0.1:5000
```

### Start Frontend (React/Vite):
```powershell
# Open terminal 2 in frontend/ directory
cd frontend
npm run dev
# Frontend runs on http://127.0.0.1:5173
```

### Run Test Suite:
```powershell
python -m pytest -q
# Output: 343 passed
```

---

*Submitted for Semester 5 Project Examination & Evaluation.*
