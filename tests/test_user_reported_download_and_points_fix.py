"""
Verification test suite for:
1. Download links in emails: Must be absolute URLs (e.g. http://localhost:5000/api/v1/reports/download/<filename>)
   so that clicking [Download MD], [Download HTML], [Download DOCX], [Download PDF], [Download TXT] in email clients
   (like Gmail) works and triggers physical file download for all formats.
2. Endpoint /api/v1/reports/download/<filename> returns 200 with proper MIME types, CORS, and Content-Disposition.
3. Database & BI -> Report Generation: Output report is structured in clean, empirical bullet points.
4. HTTP / Webhook -> Report Generation: Output report is structured in clean, empirical bullet points.
5. Email Agent body display: Rich domain sections and bullet points appear directly inside the email body
   for Security, Database BI, and Webhook workflows.
"""

import os
import re
import pytest
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models.agent import Agent, AGENT_STATUS_ACTIVE
from app.models.workflow import (
    Workflow,
    WORKFLOW_STATUS_ACTIVE,
)
from app.models.workflow_node import WorkflowNode
from app.models.workflow_dependency import (
    WorkflowDependency,
    DEPENDENCY_TYPE_ON_SUCCESS,
)
from app.models.workflow_execution import WorkflowExecution, EXECUTION_STATUS_QUEUED, EXECUTION_STATUS_COMPLETED
from app.models.task_execution import TaskExecution, TASK_STATUS_COMPLETED
from app.models.approval_request import ApprovalRequest, APPROVAL_STATUS_PENDING
from app.services.execution_engine import WorkflowExecutionEngine
from app.services.approval_service import resolve_approval_request


def _get_or_create_agents(user_id):
    agent_specs = [
        ("Security Analysis Agent", "security_analysis"),
        ("Database BI Agent", "database_bi"),
        ("HTTP Webhook Agent", "http_webhook"),
        ("Report Generation Agent", "report_generation"),
        ("Email Agent", "email"),
    ]
    agents = {}
    for name, ag_type in agent_specs:
        ag = Agent.query.filter_by(agent_type=ag_type, user_id=user_id).first()
        if not ag:
            ag = Agent(
                name=name,
                agent_type=ag_type,
                system_instructions=f"Execute {name} domain operations.",
                user_id=user_id,
                status=AGENT_STATUS_ACTIVE,
            )
            db.session.add(ag)
            db.session.commit()
        agents[ag_type] = ag
    return agents


def test_security_to_report_to_email_downloads_and_body(app, db_session, test_user, client):
    """Verify Security Analysis -> Report Generation -> Email:
    1. All 5 formats are generated and exist on disk.
    2. Download buttons in email HTML have absolute URLs.
    3. Every download URL works via HTTP GET and downloads the file.
    4. Email HTML body renders the actual security sections and findings.
    """
    with app.app_context():
        agents = _get_or_create_agents(test_user.id)

        wf = Workflow(user_id=test_user.id, name="Security Download & Body Verification", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Security Vulnerability Audit",
            priority=1,
            configuration={
                "code": "def login(user, pw):\n    q = 'SELECT * FROM users WHERE user=' + user\n    token = 'ghp_123456789012345678901234567890123456'\n    return db.execute(q)",
                "target": "auth_service.py",
            },
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Security Executive Report",
            priority=2,
            configuration={"format": "pdf", "title": "Enterprise Security Vulnerability Audit"},
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Security Dispatcher",
            priority=3,
            configuration={"to": "cso@enterprise.com", "mode": "send"},
        )
        db.session.add_all([n_sec, n_rep, n_email])
        db.session.commit()

        db.session.add_all([
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
        ])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"id": "re_sec_download_test_123"}
        mock_post.text = '{"id": "re_sec_download_test_123"}'

        with patch("requests.post", return_value=mock_post):
            engine = WorkflowExecutionEngine()
            engine.run_execution(execution.id)

            appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
            assert appr is not None

            # Approve email dispatch
            resolve_approval_request(appr.id, user_id=test_user.id, approve=True, prevent_self_approval=False, engine=engine)

            db.session.refresh(execution)
            assert execution.status == EXECUTION_STATUS_COMPLETED

            te_email = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_email.id).first()
            assert te_email.status == TASK_STATUS_COMPLETED

            html = te_email.output_data.get("html", "")

            # 1. Verify download buttons use absolute URLs
            button_links = re.findall(r'<a\s+href=[\'\"]([^\'\"]+)[\'\"][^>]*>Download\s+([A-Z]+)</a>', html)
            assert len(button_links) >= 5, f"Expected at least 5 download buttons, found: {button_links}"
            for url, fmt in button_links:
                assert url.startswith("http://") or url.startswith("https://"), f"URL must be absolute: {url}"
                assert "/api/v1/reports/download/" in url, f"URL must point to report download endpoint: {url}"

                # Test download endpoint directly via Flask test client
                rel_path = url[url.find("/api/v1/reports/download/"):]
                resp = client.get(rel_path)
                assert resp.status_code == 200, f"Download failed for {rel_path} with status {resp.status_code}"
                assert "attachment;" in resp.headers.get("Content-Disposition", "")
                assert len(resp.data) > 0

            # 2. Verify security findings and sections are clearly rendered in email HTML body
            assert "Security Vulnerability" in html or "Enterprise Security" in html
            assert "Executive Report Generated" in html
            assert "Vulnerabilities" in html or "Threat" in html or "Findings" in html
            assert "Download MD" in html
            assert "Download HTML" in html
            assert "Download DOCX" in html
            assert "Download PDF" in html
            assert "Download TXT" in html


def test_database_bi_to_report_to_email_points_format_and_body(app, db_session, test_user, client):
    """Verify Database & BI -> Report Generation -> Email:
    1. Report Generation output is structured in clean, empirical bullet points.
    2. Email HTML body clearly displays the SQL query, row count, KPIs, and data points.
    3. Download buttons are absolute URLs.
    """
    with app.app_context():
        agents = _get_or_create_agents(test_user.id)

        wf = Workflow(user_id=test_user.id, name="Database BI Points Verification", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_db = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["database_bi"].id,
            name="Quarterly User Statistics Query",
            priority=1,
            configuration={"query": "SELECT count(*) as total_users FROM users"},
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Database Executive Report",
            priority=2,
            configuration={"format": "docx", "title": "User Database Intelligence Briefing"},
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="BI Email Dispatcher",
            priority=3,
            configuration={"to": "cfo@enterprise.com", "mode": "send"},
        )
        db.session.add_all([n_db, n_rep, n_email])
        db.session.commit()

        db.session.add_all([
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_db.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
        ])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"id": "re_db_points_test_456"}
        mock_post.text = '{"id": "re_db_points_test_456"}'

        with patch("requests.post", return_value=mock_post):
            engine = WorkflowExecutionEngine()
            engine.run_execution(execution.id)

            appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
            assert appr is not None
            resolve_approval_request(appr.id, user_id=test_user.id, approve=True, prevent_self_approval=False, engine=engine)

            te_rep = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_rep.id).first()
            te_email = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_email.id).first()

            # 1. Verify Report sections are structured in bullet points
            rep_sections = te_rep.output_data.get("sections", [])
            assert len(rep_sections) >= 5
            exec_sec = rep_sections[0]
            assert "- **Execution Policy:**" in exec_sec["content"]
            assert "- **Total Records Retrieved:**" in exec_sec["content"]

            # 2. Verify summary is crisp bullet points
            summary = te_rep.output_data.get("summary", "")
            assert "• Query:" in summary
            assert "• Retrieved:" in summary

            # 3. Verify Email body contains the SQL telemetry and points
            email_html = te_email.output_data.get("html", "")
            assert "SELECT count(*) as total_users FROM users" in email_html or "total_users" in email_html
            assert "Records Retrieved" in email_html or "Total Records" in email_html
            assert "Download DOCX" in email_html
            assert "Download PDF" in email_html

            # 4. Verify absolute download URLs
            button_links = re.findall(r'<a\s+href=[\'\"]([^\'\"]+)[\'\"][^>]*>Download\s+([A-Z]+)</a>', email_html)
            for url, fmt in button_links:
                assert url.startswith("http://") or url.startswith("https://")


def test_webhook_to_report_to_email_points_format_and_body(app, db_session, test_user, client):
    """Verify HTTP/Webhook -> Report Generation -> Email:
    1. Report Generation output is structured in clean, empirical bullet points.
    2. Email HTML body clearly displays the endpoint, status code, latency, and response data points.
    3. Download buttons are absolute URLs.
    """
    with app.app_context():
        agents = _get_or_create_agents(test_user.id)

        wf = Workflow(user_id=test_user.id, name="Webhook Points Verification", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["http_webhook"].id,
            name="External Payment Gateway Sync",
            priority=1,
            configuration={
                "url": "https://api.github.com/zen",
                "method": "GET",
            },
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="API Execution Report",
            priority=2,
            configuration={"format": "markdown", "title": "API Gateway Telemetry Report"},
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="DevOps Dispatcher",
            priority=3,
            configuration={"to": "devops@enterprise.com", "mode": "send"},
        )
        db.session.add_all([n_wh, n_rep, n_email])
        db.session.commit()

        db.session.add_all([
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_wh.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
        ])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        mock_wh_resp = MagicMock()
        mock_wh_resp.status_code = 200
        mock_wh_resp.json.return_value = {"message": "Non-blocking is better than blocking."}
        mock_wh_resp.text = '{"message": "Non-blocking is better than blocking."}'

        mock_email_resp = MagicMock()
        mock_email_resp.status_code = 200
        mock_email_resp.json.return_value = {"id": "re_wh_points_test_789"}
        mock_email_resp.text = '{"id": "re_wh_points_test_789"}'

        with patch("requests.get", return_value=mock_wh_resp), patch("requests.post", return_value=mock_email_resp):
            engine = WorkflowExecutionEngine()
            engine.run_execution(execution.id)

            appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id, status=APPROVAL_STATUS_PENDING).first()
            assert appr is not None
            resolve_approval_request(appr.id, user_id=test_user.id, approve=True, prevent_self_approval=False, engine=engine)

            te_rep = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_rep.id).first()
            te_email = TaskExecution.query.filter_by(workflow_execution_id=execution.id, workflow_node_id=n_email.id).first()

            # 1. Verify Report sections are structured in bullet points
            rep_sections = te_rep.output_data.get("sections", [])
            assert len(rep_sections) >= 4
            sec0 = rep_sections[0]
            assert "- **Target Endpoint:**" in sec0["content"]
            assert "- **HTTP Method:**" in sec0["content"]

            sec1 = rep_sections[1]
            assert "- **HTTP Response Status:**" in sec1["content"]
            assert "- **Execution Latency:**" in sec1["content"]

            # 2. Verify summary is crisp bullet points
            summary = te_rep.output_data.get("summary", "")
            assert "• Endpoint:" in summary
            assert "• Response Status:" in summary

            # 3. Verify Email body contains webhook telemetry and points
            email_html = te_email.output_data.get("html", "")
            assert "api.github.com/zen" in email_html
            assert "HTTP 200" in email_html
            assert "Download MD" in email_html

            # 4. Verify absolute download URLs
            button_links = re.findall(r'<a\s+href=[\'\"]([^\'\"]+)[\'\"][^>]*>Download\s+([A-Z]+)</a>', email_html)
            for url, fmt in button_links:
                assert url.startswith("http://") or url.startswith("https://")
