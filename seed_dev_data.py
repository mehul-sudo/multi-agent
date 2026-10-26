"""
Seed initial dev data for OrchestrAI Multi-Agent System.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models.user import User, ROLE_ADMIN, ROLE_USER
from app.services.user_service import create_user, find_by_username
from app.services.agent_service import create_agent
from app.services.workflow_service import (
    create_workflow,
    add_node_to_workflow,
    add_dependency_to_workflow,
    activate_workflow,
)

def seed():
    app = create_app("development")
    with app.app_context():
        db.create_all()

        # 1. Admin User
        admin = find_by_username("admin")
        if not admin:
            admin = create_user(
                username="admin",
                email="admin@example.com",
                password="AdminPassword123!",
                first_name="System",
                last_name="Administrator"
            )
            admin.role = ROLE_ADMIN
            db.session.commit()
            print("Created admin user: admin / AdminPassword123!")
        else:
            print("Admin user already exists.")

        # 2. Demo User
        demo = find_by_username("demo_user")
        if not demo:
            demo = create_user(
                username="demo_user",
                email="demo@example.com",
                password="DemoPassword123!",
                first_name="Demo",
                last_name="User"
            )
            print("Created demo user: demo_user / DemoPassword123!")
        else:
            print("Demo user already exists.")

        # 3. Create Specialized Agents for admin
        agents_def = [
            {
                "name": "Executive Email Agent",
                "description": "Enterprise email drafting, validation, and delivery agent.",
                "agent_type": "email",
                "system_instructions": "Compose concise, professional executive communications and route alerts.",
                "provider": "mock",
                "model": "mock-email-v1",
            },
            {
                "name": "Market & Data Analysis Agent",
                "description": "Performs statistical trend calculation, anomaly detection, and data summaries.",
                "agent_type": "data_analysis",
                "system_instructions": "Ingest tabular datasets, extract summary statistics, and detect critical growth anomalies.",
                "provider": "mock",
                "model": "mock-analyst-v1",
            },
            {
                "name": "Executive Report Publisher",
                "description": "Compiles multi-source intelligence into polished PDF/Markdown reports.",
                "agent_type": "report_generation",
                "system_instructions": "Transform structured metrics into formatted executive briefings.",
                "provider": "mock",
                "model": "mock-writer-v1",
            },
            {
                "name": "Enterprise Webhook / HTTP Agent",
                "description": "Dispatches secure REST payloads and triggers third-party webhooks.",
                "agent_type": "http_webhook",
                "system_instructions": "Make outbound HTTP calls with exponential backoff and domain validation.",
                "provider": "mock",
                "model": "mock-http-v1",
            },
            {
                "name": "Security & Vulnerability Scanner",
                "description": "Audits configuration, analyzes prompt injection risks, and inspects tokens.",
                "agent_type": "security_analysis",
                "system_instructions": "Scan payloads for security threats, OWASP vulnerabilities, and data leakage.",
                "provider": "mock",
                "model": "mock-security-v1",
            },
            {
                "name": "SQL & Business Intelligence Agent",
                "description": "Executes read-only analytical queries against corporate data stores.",
                "agent_type": "database_bi",
                "system_instructions": "Translate natural language questions into safe SELECT queries.",
                "provider": "mock",
                "model": "mock-bi-v1",
            },
            {
                "name": "Document Research & Synthesis Agent",
                "description": "Extracts semantic knowledge, summaries, and key findings from documents.",
                "agent_type": "document_research",
                "system_instructions": "Parse PDFs, documents, and web briefings to synthesize concise research dossiers.",
                "provider": "mock",
                "model": "mock-research-v1",
            },
        ]

        created_agents = {}
        for a_def in agents_def:
            from app.models.agent import Agent
            existing = Agent.query.filter_by(name=a_def["name"], user_id=admin.id).first()
            if not existing:
                agent = create_agent(admin.id, a_def)
                created_agents[a_def["name"]] = agent
                print(f"Created agent: {a_def['name']}")
            else:
                created_agents[a_def["name"]] = existing

        # 4. Create Sample Workflow
        from app.models.workflow import Workflow
        wf_name = "Quarterly Business Intelligence & Executive Briefing"
        existing_wf = Workflow.query.filter_by(name=wf_name, user_id=admin.id).first()
        if not existing_wf:
            wf = create_workflow(admin.id, {
                "name": wf_name,
                "description": "Automated pipeline: data analysis -> report drafting -> human review -> executive email dispatch.",
                "priority": 1
            })

            n1, _ = add_node_to_workflow(wf, admin.id, {
                "name": "Analyze Revenue Metrics",
                "task_type": "agent_task",
                "agent_id": created_agents["Market & Data Analysis Agent"].public_id,
                "instructions": "Calculate Q3 vs Q2 YoY growth, margin shifts, and regional revenue variance.",
                "output_key": "q3_metrics",
                "position": {"x": 100, "y": 150}
            })

            n2, _ = add_node_to_workflow(wf, admin.id, {
                "name": "Generate Executive Dossier",
                "task_type": "agent_task",
                "agent_id": created_agents["Executive Report Publisher"].public_id,
                "instructions": "Format the Q3 metrics into executive summary sections with key risks.",
                "output_key": "exec_report",
                "position": {"x": 350, "y": 150}
            })

            n3, _ = add_node_to_workflow(wf, admin.id, {
                "name": "Security Compliance Audit",
                "task_type": "agent_task",
                "agent_id": created_agents["Security & Vulnerability Scanner"].public_id,
                "instructions": "Audit generated report for PII and sensitive internal credentials before sharing.",
                "output_key": "sec_audit",
                "position": {"x": 350, "y": 300}
            })

            n4, _ = add_node_to_workflow(wf, admin.id, {
                "name": "Dispatch Executive Briefing Email",
                "task_type": "agent_task",
                "agent_id": created_agents["Executive Email Agent"].public_id,
                "instructions": "Send final Q3 briefing to board@company.com with report attachment.",
                "output_key": "email_result",
                "position": {"x": 600, "y": 225}
            })

            # Add DAG dependencies
            add_dependency_to_workflow(wf, admin.id, {
                "source_node_id": n1.public_id,
                "target_node_id": n2.public_id
            })
            add_dependency_to_workflow(wf, admin.id, {
                "source_node_id": n1.public_id,
                "target_node_id": n3.public_id
            })
            add_dependency_to_workflow(wf, admin.id, {
                "source_node_id": n2.public_id,
                "target_node_id": n4.public_id
            })
            add_dependency_to_workflow(wf, admin.id, {
                "source_node_id": n3.public_id,
                "target_node_id": n4.public_id
            })

            success, res = activate_workflow(wf, admin.id)
            print(f"Workflow '{wf_name}' created and activated: {success}")
        else:
            print("Sample workflow already exists.")

if __name__ == "__main__":
    seed()
