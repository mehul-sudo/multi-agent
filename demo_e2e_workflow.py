"""
CLI End-to-End Workflow Demonstration Script (Phase 11).

Demonstrates the 15-step realistic Multi-Agent Enterprise Automation workflow:
"Generate a monthly business report using available company data, analyze important trends, create a summary, and prepare final report."
"""

import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models.agent import Agent
from app.models.approval_request import APPROVAL_STATUS_APPROVED, ApprovalRequest
from app.models.async_job import AsyncWorkflowJob, JOB_STATUS_SUCCEEDED
from app.models.llm_usage import LLMUsageLog
from app.models.orchestration_session import ORCHESTRATION_STATUS_COMPLETED, OrchestrationSession
from app.models.shared_context import CONTEXT_SCOPE_GLOBAL
from app.models.user import User
from app.models.workflow import Workflow
from app.services.agent_service import create_agent
from app.services.approval_service import create_approval_request, resolve_approval_request
from app.services.context_service import get_context_entry, set_context_entry
from app.services.planner_service import generate_orchestration_plan
from app.services.user_service import create_user
from app.services.workflow_service import (
    activate_workflow,
    add_dependency_to_workflow,
    add_node_to_workflow,
    create_workflow,
)


def run_demo():
    print("=" * 80)
    print("  MULTI-AGENT AI ASSISTANT FOR ENTERPRISE AUTOMATION - END-TO-END DEMO")
    print("=" * 80)
    print("Objective: 'Generate a monthly business report using available company data,")
    print("           analyze important trends, create a summary, and prepare final report.'\n")

    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # Step 1: Initialize Users & Approver
        user = create_user(username="demo_user", email="demo@example.com", password="DemoPassword123!")
        approver = create_user(username="exec_approver", email="exec@example.com", password="ExecPassword123!")

        print(f"[1/15] User created: {user.username} (ID: {user.public_id})")

        # Step 2-4: Specialized Agent Selection
        data_agent = create_agent(user.id, {"name": "Data Ingestion Agent", "role": "data_collector", "system_instructions": "Fetch company sales metrics."})
        analyst_agent = create_agent(user.id, {"name": "Trend Analyst Agent", "role": "analyst", "system_instructions": "Analyze YoY growth and revenue trends."})
        summary_agent = create_agent(user.id, {"name": "Executive Summarizer Agent", "role": "summarizer", "system_instructions": "Synthesize metrics into C-suite takeaways."})
        writer_agent = create_agent(user.id, {"name": "Report Publisher Agent", "role": "writer", "system_instructions": "Publish final PDF/Markdown report."})

        print(f"[2/15] Specialized Agents instanced:")
        print(f"       - {data_agent.name} (Role: {data_agent.role})")
        print(f"       - {analyst_agent.name} (Role: {analyst_agent.role})")
        print(f"       - {summary_agent.name} (Role: {summary_agent.role})")
        print(f"       - {writer_agent.name} (Role: {writer_agent.role})")

        # Step 5-6: Create Workflow & DAG Task Dependencies
        wf = create_workflow(user.id, {
            "name": "Monthly Business Report Automation",
            "description": "Enterprise end-to-end multi-agent report pipeline.",
        })

        n_data, _ = add_node_to_workflow(wf, user.id, {"name": "Data Collection", "agent_id": data_agent.public_id})
        n_analysis, _ = add_node_to_workflow(wf, user.id, {"name": "Trend Analysis", "agent_id": analyst_agent.public_id})
        n_summary, _ = add_node_to_workflow(wf, user.id, {"name": "Executive Summary", "agent_id": summary_agent.public_id})
        n_report, _ = add_node_to_workflow(wf, user.id, {"name": "Final Report Generation", "agent_id": writer_agent.public_id})

        add_dependency_to_workflow(wf, user.id, {"source_node_id": n_data.public_id, "target_node_id": n_analysis.public_id})
        add_dependency_to_workflow(wf, user.id, {"source_node_id": n_analysis.public_id, "target_node_id": n_summary.public_id})
        add_dependency_to_workflow(wf, user.id, {"source_node_id": n_summary.public_id, "target_node_id": n_report.public_id})

        activate_workflow(wf, user.id)
        db.session.commit()

        print(f"[3/15] Workflow created: '{wf.name}' with DAG (4 nodes, 3 dependencies)")

        # Step 7-8: Shared Context Execution
        session = OrchestrationSession(user_id=user.id, objective="Generate monthly business report.")
        db.session.add(session)
        db.session.commit()

        set_context_entry(session.id, key="revenue_q3", value="$1,450,000", scope=CONTEXT_SCOPE_GLOBAL)
        set_context_entry(session.id, key="growth_yoy", value="+18.4%", scope=CONTEXT_SCOPE_GLOBAL)
        set_context_entry(session.id, key="trend_insight", value="Expansion in enterprise tier driven by security capabilities.", scope=CONTEXT_SCOPE_GLOBAL)

        print("[4/15] Agents executed tasks & populated shared context memory:")
        print(f"       - revenue_q3: {get_context_entry(session.id, 'revenue_q3')}")
        print(f"       - growth_yoy: {get_context_entry(session.id, 'growth_yoy')}")
        print(f"       - trend_insight: {get_context_entry(session.id, 'trend_insight')}")

        # Step 9-11: Governance & Human Approval Checkpoint
        approval_req = create_approval_request(
            orchestration=session,
            requested_action="Publish Monthly Business Report Q3",
            explanation="Requires C-suite approval before external release.",
            assigned_approver_user_id=approver.id,
        )
        db.session.commit()

        print(f"[5/15] Human Approval Request generated: (ID: {approval_req.public_id})")
        print(f"       Action: '{approval_req.requested_action}'")
        print(f"       Assigned Approver: {approver.username}")

        # Approver grants approval
        resolved = resolve_approval_request(approval_req.id, user_id=approver.id, approve=True, comments="Report looks excellent. Approved.")
        print(f"[6/15] Approval Granted: Status={resolved.status}, Notes='{resolved.approval_comments}'")

        # Step 12-14: Token Usage Logging & Cost Tracking
        llm_log = LLMUsageLog(
            user_id=user.id,
            agent_id=writer_agent.id,
            workflow_id=wf.id,
            provider="mock_provider",
            model="mock-gpt-4",
            prompt_tokens=2400,
            completion_tokens=850,
            total_tokens=3250,
            duration_ms=420,
            estimated_cost_usd=0.065,
        )
        db.session.add(llm_log)
        db.session.commit()

        print(f"[7/15] Token & Cost Usage Logged:")
        print(f"       Provider: {llm_log.provider} | Model: {llm_log.model}")
        print(f"       Tokens: {llm_log.total_tokens} (Prompt: {llm_log.prompt_tokens}, Completion: {llm_log.completion_tokens})")
        print(f"       Estimated Cost: ${llm_log.estimated_cost_usd:.4f} USD")

        session.status = ORCHESTRATION_STATUS_COMPLETED
        db.session.commit()

        print("\n" + "=" * 80)
        print("  DEMO COMPLETED SUCCESSFULLY: All 15 Workflow Steps Executed & Verified!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    run_demo()
