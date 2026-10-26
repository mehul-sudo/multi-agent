"""
Fix user john's agents and email workflow.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.agent import Agent, AGENT_STATUS_ACTIVE
from app.models.workflow import Workflow, WORKFLOW_STATUS_ACTIVE
from app.models.workflow_node import WorkflowNode
from app.services.agent_service import create_agent
from app.services.workflow_service import add_node_to_workflow, activate_workflow

DEFAULT_AGENTS = [
    {
        "name": "Executive Email Agent",
        "description": "Enterprise email drafting, validation, and delivery agent.",
        "agent_type": "email",
        "system_instructions": "Compose concise, professional executive communications and route alerts to recipients.",
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

def fix_data():
    app = create_app("development")
    with app.app_context():
        # Find all users
        users = User.query.all()
        for u in users:
            print(f"Checking user: {u.username} (id: {u.id})")
            # Update any custom agent with 'email' in name to agent_type='email'
            for a in u.agents:
                if "email" in a.name.lower() and a.agent_type == "custom":
                    a.agent_type = "email"
                    print(f"  Updated agent {a.name} to agent_type='email'")

            # Ensure all 7 default agents exist for this user
            existing_agent_types = {a.agent_type for a in u.agents}
            for a_def in DEFAULT_AGENTS:
                if a_def["agent_type"] not in existing_agent_types:
                    create_agent(u.id, a_def)
                    print(f"  Created agent '{a_def['name']}' for {u.username}")

            db.session.commit()

        # Specifically fix 'email workflow' for john (or any user who has an empty 'email workflow')
        wf = Workflow.query.filter_by(name="email workflow").first()
        if wf:
            user = User.query.get(wf.user_id)
            print(f"Configuring 'email workflow' for {user.username}...")
            # Find an email agent for this user
            email_agent = Agent.query.filter_by(user_id=user.id, agent_type="email").first()
            if not email_agent:
                email_agent = Agent.query.filter_by(user_id=user.id).first()

            # If workflow has 0 nodes, add an email node
            if len(wf.nodes) == 0:
                node, err = add_node_to_workflow(wf, user.id, {
                    "name": "Send Real-Time Notification Email",
                    "task_type": "agent_task",
                    "agent_id": email_agent.public_id if email_agent else None,
                    "instructions": "Send notification email to recipient with subject and content.",
                    "output_key": "email_result",
                    "position": {"x": 250, "y": 150}
                })
                print(f"Added email node to 'email workflow': {node.name if node else err}")

            # Activate the workflow
            success, val_res = activate_workflow(wf, user.id)
            print(f"'email workflow' status is now: {wf.status} (activated: {success})")
            db.session.commit()

if __name__ == "__main__":
    fix_data()
