# Multi-Agent AI Assistant for Enterprise Automation

![Backend Version](https://img.shields.io/badge/Backend-Phase_12_Verified-green.svg)
![Frontend](https://img.shields.io/badge/Frontend-React_18_+_Vite-blue.svg)
![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)
![Framework](https://img.shields.io/badge/Flask-3.0+-lightgrey.svg)
![Tests](https://img.shields.io/badge/Tests-343_Passed_100%25-brightgreen.svg)
![Status](https://img.shields.io/badge/Production_Ready-Verified-brightgreen.svg)

An enterprise-grade, full-stack multi-agent automation platform featuring interactive DAG workflow execution, specialized autonomous agents, human-in-the-loop approvals, plug-and-play LLM adapters, circuit breaker resilience, and real-time execution analytics.

> 🎓 **Semester 5 Project Submission:**
> Comprehensive Project Documentation, Architecture Diagrams, and Complete Viva Q&A Guide are available in [`SEMESTER_5_PROJECT_REPORT_AND_VIVA_GUIDE.md`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/SEMESTER_5_PROJECT_REPORT_AND_VIVA_GUIDE.md).

---

## Table of Contents

1. [Architecture & System Overview](#1-architecture--system-overview)
2. [Why External Services (Google/APIs) Were Decoupled by Default](#2-why-external-services-googleapis-were-decoupled-by-default)
3. [How to Connect Real-Time Live Providers (Step-by-Step)](#3-how-to-connect-real-time-live-providers-step-by-step)
   - [A. Google Gmail Setup (For Real Inbox Email Delivery)](#a-google-gmail-setup-for-real-inbox-email-delivery)
   - [B. Google Calendar API Setup](#b-google-calendar-api-setup)
   - [C. OpenAI / Anthropic / Gemini LLM Setup](#c-openai--anthropic--gemini-llm-setup)
   - [D. Slack / Discord / Custom Webhook Setup](#d-slack--discord--custom-webhook-setup)
   - [E. Real PostgreSQL / MySQL Database Setup](#e-real-postgresql--mysql-database-setup)
4. [Deep Dive: All 8 Specialized Agents](#4-deep-dive-all-8-specialized-agents)
   - [Agent 1: Email Agent](#agent-1-email-agent)
   - [Agent 2: Calendar Agent](#agent-2-calendar-agent)
   - [Agent 3: Data Analysis Agent](#agent-3-data-analysis-agent)
   - [Agent 4: Report Generation Agent](#agent-4-report-generation-agent)
   - [Agent 5: HTTP / Webhook Agent](#agent-5-http--webhook-agent)
   - [Agent 6: Security Analysis Agent](#agent-6-security-analysis-agent)
   - [Agent 7: Database BI Agent](#agent-7-database-bi-agent)
   - [Agent 8: Document Research Agent](#agent-8-document-research-agent)
5. [Human-in-the-Loop Approval System](#5-human-in-the-loop-approval-system)
6. [Frontend UI & 3-Tier Execution View](#6-frontend-ui--3-tier-execution-view)
7. [Installation & How to Run the Entire Project](#7-installation--how-to-run-the-entire-project)
8. [Testing & Verification Suites](#8-testing--verification-suites)
9. [Configuration Reference (`.env`)](#9-configuration-reference-env)

---

## 1. Architecture & System Overview

The system is split into a **Flask 3.0 REST Backend** and a **React 18 (Vite) Frontend**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           React 18 Frontend (Vite)                              │
│  - Dashboard & Analytics       - Interactive DAG Workflow Designer              │
│  - Human Approvals Console     - 3-Tier Human-Readable Execution Viewer          │
│  - Agents Management           - Live Integration Status Monitor                │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ HTTP REST (JWT Bearer Auth)
┌──────────────────────────────────────▼──────────────────────────────────────────┐
│                            Flask 3.0 API Gateway                                │
│  - Blueprints: /auth, /workflows, /executions, /agents, /approvals, /analytics  │
│  - Security: JWT Identity, Rate Limiting, RBAC Enforcer, Audit Logger           │
└───────────────────┬─────────────────────────────────────┬───────────────────────┘
                    │                                     │
┌───────────────────▼──────────────────────┐   ┌──────────▼───────────────────────┐
│     Workflow DAG Execution Engine        │   │    Supervisor / Plan Engine      │
│  - Topological Sort & Dependency Check   │   │  - Orchestration Sessions        │
│  - Pause & Resume State Machine          │   │  - Multi-agent Task Decomposition│
│  - Human-in-the-Loop Interceptor         │   │  - Delegations & Fallbacks       │
└───────────────────┬──────────────────────┘   └──────────┬───────────────────────┘
                    │                                     │
┌───────────────────▼─────────────────────────────────────▼───────────────────────┐
│                        Specialized Agent Subsystems                             │
│  - Email Agent          - Calendar Agent           - Data Analysis Agent        │
│  - Webhook/HTTP Agent   - Report Generation Agent  - Security Analysis Agent    │
│  - Document Research    - Database BI Agent                                     │
└───────────────────┬─────────────────────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────────────────────┐
│                       External Services & LLM Adapters                          │
│  - Real / Mock Adapters: OpenAI, Anthropic, Gemini, SMTP, IMAP, Google Cal     │
│  - Celery Worker / Eager Fallback  |  SQLite (dev.db) / PostgreSQL Engine       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Why External Services (Google/APIs) Were Decoupled by Default

A common question is: **"Why doesn't the project connect to my real Google Gmail or OpenAI right after cloning?"**

There are three critical reasons for this enterprise design:

1. **Security & Zero-Leakage Policy**:
   - Google Gmail and Google Calendar require **personal credentials**, OAuth Secrets, or a 16-character **Google App Password**.
   - Committing real passwords or API keys inside source code is a major security vulnerability. By decoupling provider adapters, your real credentials stay strictly in your local private `.env` file and are never leaked.
2. **Immediate Local Runnability (Zero Barrier to Entry)**:
   - If live Google, OpenAI, Anthropic, and Redis accounts were mandatory from day one, nobody could run or test the project without first signing up for 5+ paid SaaS subscriptions.
   - The decoupled architecture allows anyone to run, test, build, and interact with the full DAG workflow engine and approvals **100% locally with zero cost and zero setup barrier**.
3. **Provider Flexibility**:
   - The system is not vendor-locked. By changing a single line in `.env`, you can switch Email from **Google Gmail** to **SendGrid**, **Amazon SES**, or **Mock**, and LLM from **OpenAI** to **Anthropic Claude**, **Google Gemini**, or **Local Mock**.

---

## 3. How to Connect Real-Time Live Providers (Step-by-Step)

### A. Google Gmail Setup (For Real Inbox Email Delivery)

By default, the backend runs with `EMAIL_PROVIDER=mock`, which safely simulates sending emails. To make emails **actually land inside a real recipient's Gmail inbox**:

1. **Generate a 16-Character Google App Password**:
   - Open your Google Account Security: [https://myaccount.google.com/security](https://myaccount.google.com/security)
   - Ensure **2-Step Verification** is turned **ON**.
   - Go to App Passwords: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Enter App Name: `Enterprise AI Assistant` and click **Create**.
   - Google will display a 16-character code (e.g., `abcd efgh ijkl mnop`). Copy this code.
2. **Configure `.env`**:
   Open `.env` in the project root and update these lines:
   ```env
   EMAIL_PROVIDER=smtp
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_TLS=true
   SMTP_USER=your_sender_email@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   EMAIL_FROM=your_sender_email@gmail.com
   ```
3. **Run your workflow**:
   - Trigger the Email Agent workflow.
   - When the task pauses, go to **Approvals** and click **Confirm Approval**.
   - The backend connects via TLS to `smtp.gmail.com:587`, authenticates, and dispatches the email straight into the recipient's Gmail inbox within seconds!

---

### B. Google Calendar API Setup

To enable real-time calendar booking on Google Calendar:

1. Open Google Cloud Console: [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a project: `Enterprise-AI-Assistant`.
3. Enable **Google Calendar API** under **APIs & Services > Library**.
4. Go to **Credentials > Create Credentials > Service Account**.
5. Create a key in **JSON** format, download it, and save it in the project as:
   `instance/google_calendar_credentials.json`
6. Share your Google Calendar with the Service Account email (give "Make changes to events" permission).
7. Configure `.env`:
   ```env
   CALENDAR_PROVIDER=google
   GOOGLE_CALENDAR_CREDENTIALS=instance/google_calendar_credentials.json
   GOOGLE_CALENDAR_ID=your_calendar_id@gmail.com
   ```

---

### C. OpenAI / Anthropic / Gemini LLM Setup

To switch from Mock LLM to real frontier models:

1. Obtain your API key from [OpenAI](https://platform.openai.com/), [Anthropic](https://console.anthropic.com/), or [Google AI Studio](https://aistudio.google.com/).
2. Configure `.env`:
   ```env
   USE_MOCK_LLM=False
   LLM_PROVIDER=openai          # or 'anthropic' or 'gemini'
   OPENAI_API_KEY=sk-proj-your-real-openai-api-key
   ANTHROPIC_API_KEY=sk-ant-your-real-anthropic-key
   GEMINI_API_KEY=your-gemini-api-key
   LLM_MODEL=gpt-4o-mini        # or 'claude-3-5-sonnet', 'gemini-1.5-pro'
   ```

---

### D. Slack / Discord / Custom Webhook Setup

The HTTP Webhook Agent enforces SSRF security by whitelisting destination domains:

1. Get your incoming webhook URL (e.g., Slack Webhook: `https://hooks.slack.com/services/T00/B00/XXXX`).
2. Add the host domain to `ALLOWED_WEBHOOK_DOMAINS` in `.env`:
   ```env
   ALLOWED_WEBHOOK_DOMAINS=example.com,api.github.com,httpbin.org,hooks.slack.com
   ```
3. Set the node URL to your webhook in the workflow designer.

---

### E. Real PostgreSQL / MySQL Database Setup

To run against a production relational database instead of SQLite:

1. Configure `DATABASE_URL` in `.env`:
   ```env
   DATABASE_URL=postgresql://postgres_user:strong_password@localhost:5432/enterprise_automation
   ```
2. Apply database migrations:
   ```bash
   flask db upgrade
   ```

---

## 4. Deep Dive: All 8 Specialized Agents

The project contains 8 pre-built specialized agents located in [`app/agents/`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/):

---

### Agent 1: Email Agent (`EmailAgent`)
- **File**: [`app/agents/email_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/email_agent.py)
- **Role**: Automated drafting and verified dispatch of corporate communications.
- **Input Parameters**:
  - `to` *(string | list)*: Recipient email address (e.g. `mehulmahajan9898@gmail.com`).
  - `subject` *(string)*: Subject line.
  - `body` / `message` *(string)*: Message text content.
  - `mode` *(string)*: `'draft'` (generates artifact) or `'send'` (triggers approval & dispatch).
  - `attachments` *(list)*: Local file paths to attach.
- **Intelligent Instruction Parsing**:
  If explicit inputs are omitted, the agent uses regex patterns to extract recipient addresses and quoted message bodies directly from human text (e.g., `Send email to test@company.com saying "Report is ready"`).
- **Approval Checkpoint**:
  Sending an email is a side-effect action. It halts the workflow (`PAUSED`), marks the step `BLOCKED`, and generates an `ApprovalRequest`.
- **UI Visualization**:
  Displays a dedicated Email Card with recipient badge chips, subject header, formatted message preview, and live/mock provider indicators.

---

### Agent 2: Calendar Agent (`CalendarAgent`)
- **File**: [`app/agents/calendar_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/calendar_agent.py)
- **Role**: Corporate schedule management, conflict avoidance, and calendar event booking.
- **Input Parameters**:
  - `title` *(string)*: Event name (e.g. `Q3 Executive Strategy Meeting`).
  - `start` / `end` *(ISO 8601 string)*: `2026-09-24T10:00:00Z`.
  - `attendees` *(list)*: Email addresses of participants.
  - `location` *(string)*: Physical address or Google Meet/Zoom link.
- **How it Works**:
  1. Validates ISO timestamp formatting.
  2. Queries existing events within the interval to flag scheduling collisions.
  3. Halts for human approval prior to committing external invites.
  4. Dispatches to Google Calendar API or generates `.ics` calendar files.
- **UI Visualization**:
  Calendar Event Card with time chips, duration calculation, attendee pills, and status badges.

---

### Agent 3: Data Analysis Agent (`DataAnalysisAgent`)
- **File**: [`app/agents/data_analysis_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/data_analysis_agent.py)
- **Role**: Statistical computation, metric aggregation, data quality scoring, and anomaly detection.
- **Input Parameters**:
  - `dataset` *(list | dict)*: Array of numerical records or column key-value maps.
  - `analysis_type` *(string)*: `'descriptive_statistics'`, `'correlation'`, or `'data_quality'`.
- **How it Works**:
  Executes high-performance numerical analysis in Python. Computes count, mean, median, min, max, variance, standard deviation, and missing values. Generates an objective Data Quality Score (0–100).
- **UI Visualization**:
  Clean tabular layout with summary statistics, score meters, and highlighted metric indicators.

---

### Agent 4: Report Generation Agent (`ReportGenerationAgent`)
- **File**: [`app/agents/report_generation_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/report_generation_agent.py)
- **Role**: Synthesizes workflow data into executive-ready business reports.
- **Input Parameters**:
  - `title` *(string)*: Report title.
  - `sections` *(list | dict)*: Headings and section content.
  - `format` *(string)*: `'markdown'` or `'html'`.
- **How it Works**:
  Aggregates data piped from upstream agents (Data Analysis, Security Audit) and compiles a multi-section document with Executive Summary, Findings, and Recommendations. Emits downloadable artifacts.
- **UI Visualization**:
  Document viewer with section tabs, word count statistics, and one-click copy/download.

---

### Agent 5: HTTP / Webhook Agent (`HttpWebhookAgent`)
- **File**: [`app/agents/http_webhook_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/http_webhook_agent.py)
- **Role**: Inter-service communication, webhook triggers, and third-party API integration.
- **Input Parameters**:
  - `url` *(string)*: Target HTTP/HTTPS endpoint.
  - `method` *(string)*: `GET`, `POST`, `PUT`, `DELETE`.
  - `headers` *(dict)*: Request headers (e.g. Authorization, Content-Type).
  - `payload` *(dict)*: Request body.
- **Security Guardrails**:
  Enforces Server-Side Request Forgery (SSRF) protection. Target domains must be present in `ALLOWED_WEBHOOK_DOMAINS`.
- **UI Visualization**:
  HTTP Inspector Card showing status code badge (e.g. `200 OK`), request URL, method, and latency.

---

### Agent 6: Security Analysis Agent (`SecurityAnalysisAgent`)
- **File**: [`app/agents/security_analysis_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/security_analysis_agent.py)
- **Role**: Automated security review, vulnerability pattern scanning, and configuration auditing.
- **Input Parameters**:
  - `target_content` *(string | dict)*: Configuration files, JSON manifests, or code snippets.
  - `ruleset` *(string)*: `'owasp_top_10'`, `'secrets_scan'`, or `'compliance'`.
- **How it Works**:
  Scans inputs for exposed tokens, SQL injection vectors, permissive CORS, and unencrypted transmission. Emits an overall risk grade (Low / Medium / High / Critical) and concrete remediation steps.
- **UI Visualization**:
  Security Audit Dashboard with vulnerability chips and severity score indicators.

---

### Agent 7: Database BI Agent (`DatabaseBIAgent`)
- **File**: [`app/agents/database_bi_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/database_bi_agent.py)
- **Role**: Read-only business intelligence querying over SQL databases.
- **Input Parameters**:
  - `query` *(string)*: SQL SELECT statement or natural language data query.
  - `limit` *(int)*: Maximum rows to return (default: 100).
- **Security Guardrails**:
  Strictly verifies that statements are non-destructive (`SELECT` only). Any statement containing `DROP`, `DELETE`, `INSERT`, `ALTER`, or `UPDATE` is instantly blocked.
- **UI Visualization**:
  Interactive SQL result grid showing row counts, execution time, and query syntax.

---

### Agent 8: Document Research Agent (`DocumentResearchAgent`)
- **File**: [`app/agents/document_research_agent.py`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/app/agents/document_research_agent.py)
- **Role**: Semantic text extraction, keyword extraction, and document synthesis.
- **Input Parameters**:
  - `documents` *(list)*: Text strings, file paths, or research notes.
  - `query` *(string)*: Specific question or topic to research.
- **How it Works**:
  Parses documents, filters out noise, indexes semantic keywords, and outputs a concise bulleted briefing for downstream consumption.
- **UI Visualization**:
  Research dossier card with highlighted key findings and source citations.

---

## 5. Human-in-the-Loop Approval System

High-risk operations (e.g. sending real emails, modifying production databases, booking calendar events) must never execute autonomously without human verification.

### How the Pause & Resume State Machine Works:

1. **Interception**: When a node requiring approval executes, the engine sets:
   - `TaskExecution.status = 'blocked'`
   - `WorkflowExecution.status = 'paused'`
   - Inserts an `ApprovalRequest` record containing the proposed action, risk level, and payload preview.
2. **Review**: The user navigates to the **Approvals** tab in the UI (`/approvals`) to inspect the pending request.
3. **Decision**:
   - **Approve**: Calling `POST /api/v1/approvals/<id>/approve` triggers `WorkflowExecutionEngine.resume_execution_after_approval()`. The side-effect executes, the task completes, and downstream nodes resume.
   - **Reject**: Calling `POST /api/v1/approvals/<id>/reject` transitions the task and execution to `failed`, stopping further downstream execution.
4. **Production Self-Approval Guardrail**:
   - In production (`FLASK_ENV=production`), a user cannot approve their own request under any circumstance (Separation of Duties).
   - In local development (`FLASK_ENV=development`), self-approval is automatically permitted so a single developer can test end-to-end flows.

---

## 6. Frontend UI & 3-Tier Execution View

The execution step drawer ([`AgentResultRenderer.tsx`](file:///c:/Users/Mehul/Downloads/muti%20agent%20ai%20backend/frontend/src/components/AgentResultRenderer.tsx)) replaces raw JSON dumps with a **3-Tier Presentation**:

1. **Tier 1: Human-Readable Cards**:
   - Tailored specifically to the agent type (e.g., Email recipient chips, subject line, body preview; Calendar event pill and date/time; Analysis table).
2. **Tier 2: Collapsible Technical Details**:
   - Displays Message ID, Event ID, Provider used, execution duration in milliseconds, and agent metadata in a clean accordion.
3. **Tier 3: Collapsible Raw JSON**:
   - Complete, syntax-highlighted JSON payload with a 1-click **"Copy JSON"** button for developers and auditing.

---

## 7. Installation & How to Run the Entire Project

### Prerequisites
- Python 3.13+ installed
- Node.js 18+ and npm installed

---

### Step 1: Start the Backend Server

```powershell
# Open terminal in project root
cd "c:\Users\Mehul\Downloads\muti agent ai backend"

# Install Python dependencies (first time only)
pip install -r requirements.txt

# Run the Flask API server
python run.py
```
*The backend server will start on **`http://127.0.0.1:5000`**.*

---

### Step 2: Start the React Frontend Server

```powershell
# Open a second terminal in the frontend directory
cd "c:\Users\Mehul\Downloads\muti agent ai backend\frontend"

# Install frontend dependencies (first time only)
npm install

# Start Vite development server
npm run dev
```
*The frontend will be accessible at **`http://localhost:5173`**.*

---

### Step 3: Open in Browser
Open **`http://localhost:5173`** in your browser. You can register a new user account or log in with your credentials to start building and executing workflows!

---

## 8. Testing & Verification Suites

The codebase includes an extensive automated test suite covering units, integration, RBAC, DAG execution, and async Celery jobs.

### Run All 343 Pytest Tests:
```powershell
python -m pytest
```
*Expected result: `343 passed in ~57s`.*

### Run End-to-End Approval & Rejection Verification:
```powershell
python verify_e2e_approval_flow.py
```
*Verifies: Workflow trigger -> Execution paused -> Task blocked -> Approval granted -> Resume execution -> Email dispatched -> Workflow completed -> Rejection cleanly marks failed.*

### Run Frontend TypeScript Check & Production Build:
```powershell
cd frontend
npx tsc --noEmit
npm run build
```
*Expected result: `0 errors, built in ~600ms`.*

---

## 9. Configuration Reference (`.env`)

| Variable | Default Value | Description |
|---|---|---|
| `FLASK_ENV` | `development` | Environment mode (`development`, `testing`, `production`) |
| `DATABASE_URL` | `sqlite:///dev.db` | Database connection URI (SQLite for local, PostgreSQL for prod) |
| `SECRET_KEY` | `dev-secret-key-...` | Flask session cryptographic secret |
| `JWT_SECRET_KEY` | `dev-jwt-secret-...` | JWT signing secret |
| `ALLOW_SELF_APPROVAL_IN_DEVELOPMENT` | `true` | Allows requester to approve their own actions in development |
| `USE_MOCK_LLM` | `True` | Set to `False` when using real OpenAI/Anthropic/Gemini keys |
| `LLM_PROVIDER` | `mock` | `openai`, `anthropic`, `gemini`, or `mock` |
| `OPENAI_API_KEY` | `mock-key` | Real OpenAI API key (`sk-proj-...`) |
| `EMAIL_PROVIDER` | `mock` | `smtp` for real Gmail/SMTP, `mock` for safe local simulation |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP host server |
| `SMTP_PORT` | `587` | SMTP TLS port |
| `SMTP_USER` | *(empty)* | Real sending Gmail address |
| `SMTP_PASSWORD` | *(empty)* | 16-character Google App Password |
| `CALENDAR_PROVIDER` | `mock` | `google` for real Google Calendar, `mock` for simulation |
| `ALLOWED_WEBHOOK_DOMAINS` | `example.com,httpbin.org` | Whitelist of allowed external HTTP webhook destinations |
| `CELERY_TASK_ALWAYS_EAGER` | `True` | Enables synchronous in-process task execution without Redis |

---

## License

Enterprise Automation Assistant is licensed under the Apache 2.0 License.
