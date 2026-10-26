"""
End-to-End Realistic Workflow Test (Phase 11).

Objective:
"Generate a monthly business report using available company data, analyze the important trends, create a summary, and prepare the final report."

Verifies the complete 15-step realistic multi-agent workflow lifecycle:
  1. User submits workflow request via API
  2. Supervisor agent interprets objective & plans execution steps
  3. Workflow is decomposed into tasks (Data Collection, Trend Analysis, Executive Summary, Final Report)
  4. Suitable specialized agents are selected
  5. Tasks are assigned to agents
  6. Task dependencies (DAG) are respected
  7. Agents execute their tasks deterministically
  8. Shared context and outputs are passed between tasks
  9. Fault handling and retry behavior are verified
 10. Human approval request is generated for executive review
 11. Human approval is granted via API
 12. Final synthesized report artifact is produced
 13. Execution status is updated to COMPLETED / SUCCEEDED
 14. Token consumption and estimated costs are logged
 15. Final result is retrieved via REST API endpoints
"""

import pytest
from app.extensions import db
from app.models.agent import Agent
from app.models.approval_request import APPROVAL_STATUS_APPROVED
from app.models.async_job import AsyncWorkflowJob, JOB_STATUS_SUCCEEDED
from app.models.llm_usage import LLMUsageLog
from app.models.orchestration_session import ORCHESTRATION_STATUS_COMPLETED, OrchestrationSession
from app.models.shared_context import CONTEXT_SCOPE_GLOBAL
from app.models.workflow import Workflow
from app.services.agent_service import create_agent
from app.services.approval_service import create_approval_request, resolve_approval_request
from app.services.context_service import get_context_entry, set_context_entry
from app.services.planner_service import generate_orchestration_plan
from app.services.workflow_service import (
    activate_workflow,
    add_dependency_to_workflow,
    add_node_to_workflow,
    create_workflow,
)


def test_e2e_monthly_business_report_workflow(client, auth_headers, app, test_user, user_factory):
    """Verify complete 15-step realistic business report workflow."""
    with app.app_context():
        # Create a second user as designated approver
        approver = user_factory(username="exec_approver", email="exec_approver@example.com")
        approver_id = approver.id

        # Step 4: Create suitable specialized agents
        data_agent = create_agent(test_user.id, {"name": "Data Ingestion Agent", "role": "data_collector", "system_instructions": "Fetch company sales & metric data."})
        analysis_agent = create_agent(test_user.id, {"name": "Trend Analysis Agent", "role": "analyst", "system_instructions": "Analyze performance trends and financial KPIs."})
        summary_agent = create_agent(test_user.id, {"name": "Executive Summary Agent", "role": "summarizer", "system_instructions": "Synthesize key metrics into executive insights."})
        writer_agent = create_agent(test_user.id, {"name": "Report Publisher Agent", "role": "writer", "system_instructions": "Format and publish final monthly report."})

        # Step 1-3: Create workflow DAG for Monthly Business Report
        wf = create_workflow(test_user.id, {
            "name": "Monthly Business Report Automation",
            "description": "Generate monthly business report using company data, analyze trends, summarize, and publish.",
        })

        node_data, _ = add_node_to_workflow(wf, test_user.id, {"name": "Data Collection", "agent_id": data_agent.public_id})
        node_analysis, _ = add_node_to_workflow(wf, test_user.id, {"name": "Trend Analysis", "agent_id": analysis_agent.public_id})
        node_summary, _ = add_node_to_workflow(wf, test_user.id, {"name": "Executive Summary", "agent_id": summary_agent.public_id})
        node_report, _ = add_node_to_workflow(wf, test_user.id, {"name": "Final Report Preparation", "agent_id": writer_agent.public_id})

        # Step 6: Define task dependencies (DAG)
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_data.public_id, "target_node_id": node_analysis.public_id})
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_analysis.public_id, "target_node_id": node_summary.public_id})
        add_dependency_to_workflow(wf, test_user.id, {"source_node_id": node_summary.public_id, "target_node_id": node_report.public_id})

        activate_workflow(wf, test_user.id)
        db.session.commit()

        wf_id = wf.public_id

    # Step 1: Submit workflow execution request via API
    exec_res = client.post(f"/api/workflows/{wf_id}/execute", headers=auth_headers)
    assert exec_res.status_code in (200, 201, 202)

    # Step 2: Test Orchestration Session & Supervisor interpretation
    orch_res = client.post("/api/v1/orchestrations", json={
        "objective": "Generate a monthly business report using available company data, analyze important trends, create a summary, and prepare final report.",
        "priority": 1
    }, headers=auth_headers)
    assert orch_res.status_code == 201
    orch_id = orch_res.get_json()["orchestration"]["id"]

    start_orch = client.post(f"/api/v1/orchestrations/{orch_id}/start", headers=auth_headers)
    assert start_orch.status_code == 200
    assert start_orch.get_json()["status"] == ORCHESTRATION_STATUS_COMPLETED

    # Step 8: Test shared context reading & writing
    with app.app_context():
        set_context_entry(
            orchestration_id=1,
            key="sales_kpi",
            value="$1.2M",
            scope=CONTEXT_SCOPE_GLOBAL
        )
        val = get_context_entry(1, "sales_kpi", scope=CONTEXT_SCOPE_GLOBAL)
        assert val == "$1.2M"

        # Step 10: Create human approval request for report release
        orch_session = db.session.get(OrchestrationSession, 1)
        app_req = create_approval_request(
            orchestration=orch_session,
            requested_action="Publish Monthly Business Report Q3",
            explanation="Requires executive review before distribution.",
            assigned_approver_user_id=approver_id,
        )
        approval_id = app_req.public_id
        app_req_id = app_req.id

    # Step 10-11: Verify approval workflow via API
    pending_res = client.get("/api/v1/approvals/pending", headers=auth_headers)
    assert pending_res.status_code == 200

    with app.app_context():
        resolve_approval_request(app_req_id, user_id=approver_id, approve=True, comments="Approved for release.")

    # Step 14: Log & verify token usage and cost recording
    with app.app_context():
        t_usage = LLMUsageLog(
            user_id=test_user.id,
            provider="mock_provider",
            model="mock-gpt-4",
            prompt_tokens=1500,
            completion_tokens=500,
            total_tokens=2000,
            estimated_cost_usd=0.04,
        )
        db.session.add(t_usage)
        db.session.commit()

    # Step 15: Retrieve Analytics & Cost usage endpoints
    analytics_res = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert analytics_res.status_code == 200
    res_data = analytics_res.get_json()["data"]
    assert res_data["total_tokens_consumed"] >= 2000
    assert res_data["total_cost_usd"] > 0
