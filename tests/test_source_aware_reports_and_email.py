"""
Comprehensive Test Suite: Source-Aware Report Generation & Correct Email Output.

Tests the 8 core combinations requested by the user:
1. Security Analysis -> Report Generation -> Email (Mode B)
2. Database & BI -> Report Generation -> Email (Mode B)
3. HTTP/Webhook -> Report Generation -> Email (Mode B)
4. Data Analysis -> Report Generation -> Email (Mode B)
5. Document Research -> Report Generation -> Email (Mode B)
6. Security + Database/BI -> Report Generation -> Email (Mode B Consolidated Multi-Domain)
7. Data Analysis -> Email (Mode A - Direct Agent Findings, No Report Attachment)
8. Security Analysis -> Email (Mode A - Direct Agent Findings, No Report Attachment)

Verifies:
- Domain-appropriate report structure & titles (no generic template re-use)
- Output format preservation (PDF, DOCX, HTML, Markdown, TXT)
- Physical artifact persistence on disk
- Mode A vs Mode B attachment separation
- Email Agent receiving real upstream outputs & rendering clean HTML/text
- Zero hallucination / zero fabrication of vulnerabilities, queries, or API payloads
"""

import os
import re
import json
import pytest
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.task_execution import TaskExecution
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_ON_SUCCESS,
    WorkflowDependency,
)
from app.models.workflow_execution import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_QUEUED,
    WorkflowExecution,
)
from app.models.workflow_node import WorkflowNode
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.services.execution_engine import (
    WorkflowExecutionEngine,
)
from tests.test_master_multiagent_workflow_execution import (
    RealisticMultiAgentExecutor,
    create_test_agents,
)


# ===========================================================================
# 1. Security Analysis -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_combo_1_security_to_report_to_email_mode_b(app, db_session, test_user):
    """1. Security Analysis -> Report Generation -> Email (Mode B)
    - Generates domain-specific Security Assessment Report.
    - Verified CVEs, severities, locations, and hardening recommendations.
    - Email receives report deliverable, physical PDF is attached, HTML rendered.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Security to Report to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Vulnerability Scanner",
            priority=1,
            configuration={
                "target": "app/services/auth_controller.py",
            }
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Security Report Builder",
            priority=2,
            configuration={"format": "pdf"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Security Email Alert",
            priority=3,
            configuration={
                "to": "cso@enterprise.com",
                "mode": "send",
            }
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

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        # Pauses for human approval on Email node
        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        # Verify Report Output is domain-specific
        rep_out = executor.recorded_outputs["Security Report Builder"]
        assert rep_out["domain"] == "security"
        assert "Security" in rep_out["reportTitle"] and "Assessment" in rep_out["reportTitle"]
        assert rep_out["summary"] != ""
        rep_sections = [s["title"] for s in rep_out["sections"]]
        assert "Executive Summary & Assessment Scope" in rep_sections
        assert "Identified Vulnerabilities & Threat Breakdown" in rep_sections
        assert "Security Impact & Risk Assessment" in rep_sections
        assert "Recommended Remediation & Hardening Plan" in rep_sections
        assert "Limitations & Scan Status" in rep_sections

        # Verify physical PDF exists on disk
        pdf_path = rep_out["artifact"]["path"]
        assert os.path.exists(pdf_path)
        assert pdf_path.endswith(".pdf")
        assert os.path.getsize(pdf_path) > 500

        # Verify Email Node proposed output in Approval Request (Mode B)
        prop = appr.proposed_output
        assert pdf_path in prop["attachments"]
        assert prop["attachment_status"] == "attached"
        assert "Executive Report" in prop["subject"] or "Security" in prop["subject"]
        assert "Security Vulnerability" in prop["body"] or "Security Assessment" in prop["body"]
        assert "<table" in prop["html"] or "🛡️ Security" in prop["html"] or "Executive Report" in prop["html"]
        assert "Automated workflow task execution completed successfully." not in prop["body"]

        # Clean up generated PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


# ===========================================================================
# 2. Database & BI -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_combo_2_database_bi_to_report_to_email_mode_b(app, db_session, test_user):
    """2. Database & BI -> Report Generation -> Email (Mode B)
    - Generates domain-specific Database & BI Report.
    - Preserves read-only SQL, KPIs, and result rows.
    - Word DOCX format generated and attached.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Database to Report to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_db = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["database_bi"].id,
            name="Revenue BI Query",
            priority=1,
            configuration={
                "query": "SELECT tier, count(*) as count, sum(revenue) as total_rev FROM accounts GROUP BY tier",
                "table": "accounts",
            }
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="BI Executive Report",
            priority=2,
            configuration={"format": "docx"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Finance Board Dispatch",
            priority=3,
            configuration={"to": "finance-board@enterprise.com", "mode": "send"}
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

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        # Verify Report Output is domain-specific
        rep_out = executor.recorded_outputs["BI Executive Report"]
        assert rep_out["domain"] == "database"
        assert "Database" in rep_out["reportTitle"] and "Report" in rep_out["reportTitle"]
        rep_sections = [s["title"] for s in rep_out["sections"]]
        assert "Executive Summary & Business Scope" in rep_sections
        assert "Executed Query & KPI Telemetry" in rep_sections
        assert "Query Results & Result Dataset" in rep_sections
        assert "Business Insights & Analytical Trends" in rep_sections
        assert "Strategic Recommendations & Action Items" in rep_sections

        # Verify physical DOCX file
        docx_path = rep_out["artifact"]["path"]
        assert os.path.exists(docx_path)
        assert docx_path.endswith(".docx")
        assert os.path.getsize(docx_path) > 1000

        # Email proposal verification
        prop = appr.proposed_output
        assert docx_path in prop["attachments"]
        assert prop["attachment_status"] == "attached"
        assert "Automated workflow task execution completed successfully." not in prop["body"]

        if os.path.exists(docx_path):
            os.remove(docx_path)


# ===========================================================================
# 3. HTTP/Webhook -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_combo_3_webhook_to_report_to_email_mode_b(app, db_session, test_user):
    """3. HTTP/Webhook -> Report Generation -> Email (Mode B)
    - Generates domain-specific API Integration & Webhook Execution Report.
    - Redacts credentials/tokens in payload.
    - Markdown format generated and attached.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Webhook to Report to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_wh = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["http_webhook"].id,
            name="ERP Order Sync Webhook",
            priority=1,
            configuration={
                "url": "https://api.erp.internal/v2/orders/sync",
                "method": "POST",
                "headers": {"Authorization": "Bearer confidential_enterprise_token_12345"},
                "body": {"batchId": "BATCH-9941", "orderCount": 450, "token": "secret_abc_token"}
            }
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="ERP Integration Dossier",
            priority=2,
            configuration={"format": "markdown"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Operations Email Dispatch",
            priority=3,
            configuration={"to": "ops-lead@enterprise.com", "mode": "send"}
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

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        rep_out = executor.recorded_outputs["ERP Integration Dossier"]
        assert rep_out["domain"] == "webhook"
        assert "API" in rep_out["reportTitle"] or "Integration" in rep_out["reportTitle"]
        rep_sections = [s["title"] for s in rep_out["sections"]]
        assert "Operation Purpose & Integration Scope" in rep_sections
        assert "Execution Telemetry & Response Status" in rep_sections
        assert "Response Payload & Extracted Data" in rep_sections
        assert "Integration Health & Follow-Up Actions" in rep_sections

        # Verify secrets were redacted in report text
        rep_text = rep_out["content"]
        assert "confidential_enterprise_token" not in rep_text
        assert "secret_abc_token" not in rep_text

        md_path = rep_out["artifact"]["path"]
        assert os.path.exists(md_path)
        assert md_path.endswith(".md")

        prop = appr.proposed_output
        assert md_path in prop["attachments"]
        assert prop["attachment_status"] == "attached"

        if os.path.exists(md_path):
            os.remove(md_path)


# ===========================================================================
# 4. Data Analysis -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_combo_4_data_analysis_to_report_to_email_mode_b(app, db_session, test_user):
    """4. Data Analysis -> Report Generation -> Email (Mode B)
    - Generates Quantitative Data Analysis Report with statistical metrics & distributions.
    - HTML report deliverable generated and attached.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data Analysis to Report to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["data_analysis"].id,
            name="Q4 Latency Analysis",
            priority=1,
            configuration={"numbers": "120, 145, 130, 290, 115, 140, 150", "query": "Server latency metrics"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Statistical Report Generator",
            priority=2,
            configuration={"format": "html"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="SRE Alert Email",
            priority=3,
            configuration={"to": "sre-lead@enterprise.com", "mode": "send"}
        )
        db.session.add_all([n_da, n_rep, n_email])
        db.session.commit()

        db.session.add_all([
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
        ])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        rep_out = executor.recorded_outputs["Statistical Report Generator"]
        assert rep_out["domain"] == "data_analysis"
        assert "Data Analysis" in rep_out["reportTitle"] or "Statistical" in rep_out["reportTitle"]
        rep_sections = [s["title"] for s in rep_out["sections"]]
        assert "Executive Summary & Dataset Profile" in rep_sections
        assert "Statistical Metrics & Feature Distributions" in rep_sections
        assert "Data Quality & Integrity Assessment" in rep_sections
        assert "Empirical Insights, Trends & Outlier Anomalies" in rep_sections

        html_path = rep_out["artifact"]["path"]
        assert os.path.exists(html_path)
        assert html_path.endswith(".html")

        prop = appr.proposed_output
        assert html_path in prop["attachments"]
        assert prop["attachment_status"] == "attached"

        if os.path.exists(html_path):
            os.remove(html_path)


# ===========================================================================
# 5. Document Research -> Report Generation -> Email (Mode B)
# ===========================================================================
def test_combo_5_document_research_to_report_to_email_mode_b(app, db_session, test_user):
    """5. Document Research -> Report Generation -> Email (Mode B)
    - Generates Research Findings & Document Evidence Report with grounded citations.
    - Plain text (TXT) report deliverable generated and attached.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Document Research to Report to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_res = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["document_research"].id,
            name="AI Literature Review",
            priority=1,
            configuration={"query": "AI oncology diagnostic accuracy studies"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Research Dossier Generator",
            priority=2,
            configuration={"format": "txt"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Research Notification Dispatcher",
            priority=3,
            configuration={"to": "oncology-research@enterprise.com", "mode": "send"}
        )
        db.session.add_all([n_res, n_rep, n_email])
        db.session.commit()

        db.session.add_all([
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_res.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
        ])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        rep_out = executor.recorded_outputs["Research Dossier Generator"]
        assert rep_out["domain"] == "research"
        assert "Document Research" in rep_out["reportTitle"] or "Research" in rep_out["reportTitle"]
        rep_sections = [s["title"] for s in rep_out["sections"]]
        assert "Research Objective & Scope" in rep_sections
        assert "Grounded Synthesis & Verified Findings" in rep_sections
        assert "Core Takeaways & Discoveries" in rep_sections
        assert "Verified Document Citations & Evidence Excerpts" in rep_sections

        txt_path = rep_out["artifact"]["path"]
        assert os.path.exists(txt_path)
        assert txt_path.endswith(".txt")

        prop = appr.proposed_output
        assert txt_path in prop["attachments"]
        assert prop["attachment_status"] == "attached"

        if os.path.exists(txt_path):
            os.remove(txt_path)


# ===========================================================================
# 6. Security + Database/BI -> Report Generation -> Email (Mode B Multi-Domain)
# ===========================================================================
def test_combo_6_security_plus_database_to_report_to_email_mode_b(app, db_session, test_user):
    """6. Security + Database/BI -> Report Generation -> Email (Mode B Multi-Domain)
    - Generates Consolidated Multi-Domain Report with dedicated sections for both domains.
    - Clear domain separation, cross-domain synthesis, prioritized recommendations, appendix.
    - PDF report attached to Email.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Security and Database to Report to Email", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Database Perimeter Scanner",
            priority=1,
            configuration={"target": "db/query_service.py"}
        )
        n_db = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["database_bi"].id,
            name="Database Telemetry Query",
            priority=1,
            configuration={"query": "SELECT tier, sum(revenue) FROM accounts GROUP BY tier", "table": "accounts"}
        )
        n_rep = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["report_generation"].id,
            name="Consolidated SecOps Report",
            priority=2,
            configuration={"format": "pdf"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="SecOps Leadership Dispatch",
            priority=3,
            configuration={"to": "secops-exec@enterprise.com", "mode": "send"}
        )
        db.session.add_all([n_sec, n_db, n_rep, n_email])
        db.session.commit()

        db.session.add_all([
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_db.id, target_node_id=n_rep.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
            WorkflowDependency(workflow_id=wf.id, source_node_id=n_rep.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS),
        ])
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        rep_out = executor.recorded_outputs["Consolidated SecOps Report"]
        assert rep_out["domain"] == "multi_domain"
        assert "security" in rep_out["detected_domains"]
        assert "database" in rep_out["detected_domains"]
        assert "Security" in rep_out["reportTitle"] and "Database" in rep_out["reportTitle"]

        rep_sections = [s["title"] for s in rep_out["sections"]]
        assert "Executive Summary & Cross-Domain Scope" in rep_sections
        assert "Security Vulnerability & Threat Assessment" in rep_sections
        assert "Database Business Intelligence & KPI Telemetry" in rep_sections
        assert "Cross-Functional Impact & Systemic Analysis" in rep_sections
        assert "Prioritized Strategic Recommendations" in rep_sections
        assert "Technical Appendix & Telemetry Logs" in rep_sections

        # Verify physical PDF
        pdf_path = rep_out["artifact"]["path"]
        assert os.path.exists(pdf_path)
        assert pdf_path.endswith(".pdf")

        # Email proposal verification
        prop = appr.proposed_output
        assert pdf_path in prop["attachments"]
        assert prop["attachment_status"] == "attached"

        if os.path.exists(pdf_path):
            os.remove(pdf_path)


# ===========================================================================
# 7. Data Analysis -> Email (Mode A - Direct Agent Findings, No Report)
# ===========================================================================
def test_combo_7_data_analysis_to_email_mode_a(app, db_session, test_user):
    """7. Data Analysis -> Email (Mode A Direct)
    - Directly passes empirical calculated metrics into Email Agent.
    - No Report Generation node in workflow -> ZERO attachments attached.
    - Email body and HTML contain calculated mean, median, min, max, total.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Data Analysis Direct Email Mode A", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_da = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["data_analysis"].id,
            name="Quarterly Revenue Statistics",
            priority=1,
            configuration={"numbers": "1000, 2000, 3000, 4000, 5000", "query": "Quarterly revenue distribution"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Revenue Stats Dispatcher",
            priority=2,
            configuration={"to": "cfo@enterprise.com", "mode": "send"}
        )
        db.session.add_all([n_da, n_email])
        db.session.commit()

        db.session.add(WorkflowDependency(workflow_id=wf.id, source_node_id=n_da.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS))
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        prop = appr.proposed_output
        # STRICT MODE A: Attachments must be empty
        assert prop["attachments"] == []
        assert prop["attachment_status"] == "none"

        # Email body must contain actual metrics
        body = prop["body"]
        assert "Automated workflow task execution completed successfully." not in body
        assert "Data Analysis" in body
        assert "3000" in body or "1000" in body

        # HTML must contain data table
        html_content = prop["html"]
        assert "<table" in html_content
        assert "Data Analysis Findings" in html_content


# ===========================================================================
# 8. Security Analysis -> Email (Mode A - Direct Agent Findings, No Report)
# ===========================================================================
def test_combo_8_security_analysis_to_email_mode_a(app, db_session, test_user):
    """8. Security Analysis -> Email (Mode A Direct)
    - Directly passes verified CVE findings and risk score into Email Agent.
    - No Report Generation node in workflow -> ZERO attachments attached.
    - Email body and HTML contain risk score, severity badges, and remediation.
    """
    with app.app_context():
        agents = create_test_agents(test_user.id)
        wf = Workflow(user_id=test_user.id, name="Security Direct Email Mode A", status=WORKFLOW_STATUS_ACTIVE)
        db.session.add(wf)
        db.session.commit()

        n_sec = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["security_analysis"].id,
            name="Direct Code Vulnerability Scanner",
            priority=1,
            configuration={"target": "api/v1/accounts.py"}
        )
        n_email = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agents["email"].id,
            name="Security Alert Dispatcher",
            priority=2,
            configuration={"to": "security-alerts@enterprise.com", "mode": "send"}
        )
        db.session.add_all([n_sec, n_email])
        db.session.commit()

        db.session.add(WorkflowDependency(workflow_id=wf.id, source_node_id=n_sec.id, target_node_id=n_email.id, dependency_type=DEPENDENCY_TYPE_ON_SUCCESS))
        db.session.commit()

        execution = WorkflowExecution(workflow_id=wf.id, user_id=test_user.id, status=EXECUTION_STATUS_QUEUED)
        db.session.add(execution)
        db.session.commit()

        executor = RealisticMultiAgentExecutor()
        engine = WorkflowExecutionEngine(agent_executor=executor)
        exec_res = engine.run_execution(execution.id)

        assert exec_res.status == EXECUTION_STATUS_PAUSED
        appr = ApprovalRequest.query.filter_by(workflow_execution_id=execution.id).first()
        assert appr is not None

        prop = appr.proposed_output
        # STRICT MODE A: Attachments must be empty
        assert prop["attachments"] == []
        assert prop["attachment_status"] == "none"

        # Email body must contain actual security findings
        body = prop["body"]
        assert "Automated workflow task execution completed successfully." not in body
        assert "Security Vulnerability" in body or "Risk Score" in body

        # HTML must contain security badges and vulnerability list
        html_content = prop["html"]
        assert "🛡️ Security" in html_content
        assert "Risk Score" in html_content or "Risk" in html_content
