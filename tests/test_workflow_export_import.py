"""
Tests for Workflow Copy, Export, Import, Secret Sanitization, and Cross-Account Isolation.
"""

import json
import pytest
from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.user import User
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_ON_SUCCESS,
    WorkflowDependency,
)
from app.models.workflow_node import WorkflowNode
from app.services.workflow_service import (
    duplicate_workflow,
    export_workflow,
    import_workflow,
)


def test_workflow_export_secret_sanitization(app, db_session, test_user):
    """Verify that exporting a workflow strips all secrets, API keys, tokens, and private identifiers."""
    with app.app_context():
        agent = Agent(
            name="Email Dispatcher",
            agent_type="email",
            system_instructions="Manage notifications.",
            user_id=test_user.id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add(agent)
        db.session.commit()

        wf = Workflow(
            user_id=test_user.id,
            name="Executive Sync Pipeline",
            description="Confidential workflow with secrets",
            status=WORKFLOW_STATUS_ACTIVE,
            metadata_json={"api_key": "raw_secret_key_12345", "department": "Executive Operations"},
        )
        db.session.add(wf)
        db.session.commit()

        node = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agent.id,
            name="Sync Notification",
            configuration={
                "client_secret": "confidential_client_secret_xyz",
                "safe_param": "public_meeting_room_A",
                "user_id": test_user.id,
            },
            input_mapping={
                "token": "bearer_token_abc_hidden",
                "title": "Quarterly Planning",
            },
        )
        db.session.add(node)
        db.session.commit()

        exported = export_workflow(wf)

        # 1. Verify Schema Version
        assert exported["schema_version"] == "1.0"
        assert exported["name"] == "Executive Sync Pipeline"

        # 2. Convert to string and ensure NO secrets leaked
        export_str = json.dumps(exported)
        assert "raw_secret_key_12345" not in export_str
        assert "confidential_client_secret_xyz" not in export_str
        assert "bearer_token_abc_hidden" not in export_str
        assert "api_key" not in export_str
        assert "client_secret" not in export_str

        # 3. Ensure safe non-sensitive parameters preserved
        assert "public_meeting_room_A" in export_str
        assert "Quarterly Planning" in export_str
        assert "Executive Operations" in export_str


def test_workflow_cross_account_import_isolation_and_warnings(app, db_session, test_user):
    """Verify importing a workflow into another account regenerates IDs, isolates entities, and reports advisory warnings."""
    with app.app_context():
        # User B imports a workflow
        user_b = User(
            email="user_b@enterprise.corp",
            username="user_b_admin",
            password_hash="hashed_pw_test",
            is_active=True,
        )
        db.session.add(user_b)
        db.session.commit()

        # Create database_bi & email agents for user B
        agent_db = Agent(
            name="User B Database BI Agent",
            agent_type="database_bi",
            system_instructions="Handle analytics.",
            user_id=user_b.id,
            status=AGENT_STATUS_ACTIVE,
        )
        agent_email = Agent(
            name="User B Email Agent",
            agent_type="email",
            system_instructions="Handle emails.",
            user_id=user_b.id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add_all([agent_db, agent_email])
        db.session.commit()

        import_payload = {
            "schema_version": "1.0",
            "name": "Imported Cross-Account Orchestration",
            "description": "Multi-agent pipeline from external team",
            "priority": 2,
            "nodes": [
                {
                    "id": "step_1",
                    "name": "Query Database Analytics",
                    "agent_type": "database_bi",
                    "instructions": "Query revenue metrics.",
                    "position": {"x": 100, "y": 100},
                },
                {
                    "id": "step_2",
                    "name": "Send Confirmation Email",
                    "agent_type": "email",
                    "instructions": "Dispatch email to attendees.",
                    "position": {"x": 300, "y": 100},
                }
            ],
            "dependencies": [
                {
                    "source_node_id": "step_1",
                    "target_node_id": "step_2",
                    "dependency_type": "on_success",
                }
            ]
        }

        imported_wf, warnings, err = import_workflow(user_b.id, import_payload)

        assert err is None
        assert imported_wf is not None
        assert imported_wf.user_id == user_b.id
        assert imported_wf.name == "Imported Cross-Account Orchestration"

        # Verify 2 nodes and 1 dependency created
        assert len(imported_wf.nodes) == 2
        assert len(imported_wf.dependencies) == 1

        # Verify nodes belong to user B's agents
        node_agent_ids = [n.agent_id for n in imported_wf.nodes]
        assert agent_db.id in node_agent_ids
        assert agent_email.id in node_agent_ids

        # Verify dependency connects the newly generated nodes
        dep = imported_wf.dependencies[0]
        assert dep.source_node.name == "Query Database Analytics"
        assert dep.target_node.name == "Send Confirmation Email"

        # Verify integration advisory warnings generated for database_bi & email
        assert len(warnings) >= 1
        warning_text = " ".join(warnings)
        assert "Database BI" in warning_text or "Email" in warning_text


def test_workflow_duplication(app, db_session, test_user):
    """Verify duplicating an existing workflow creates a clone with new IDs and preserves DAG structure."""
    with app.app_context():
        agent = Agent(
            name="Pipeline Worker",
            agent_type="custom",
            system_instructions="Work on tasks.",
            user_id=test_user.id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add(agent)
        db.session.commit()

        orig_wf = Workflow(
            user_id=test_user.id,
            name="Original Pipeline",
            description="Master template pipeline",
            status=WORKFLOW_STATUS_ACTIVE,
        )
        db.session.add(orig_wf)
        db.session.commit()

        n1 = WorkflowNode(workflow_id=orig_wf.id, agent_id=agent.id, name="Step 1")
        n2 = WorkflowNode(workflow_id=orig_wf.id, agent_id=agent.id, name="Step 2")
        db.session.add_all([n1, n2])
        db.session.commit()

        dep = WorkflowDependency(
            workflow_id=orig_wf.id,
            source_node_id=n1.id,
            target_node_id=n2.id,
            dependency_type=DEPENDENCY_TYPE_ON_SUCCESS,
        )
        db.session.add(dep)
        db.session.commit()

        clone = duplicate_workflow(orig_wf, test_user.id)

        assert clone.id != orig_wf.id
        assert clone.public_id != orig_wf.public_id
        assert clone.name == "Copy of Original Pipeline"
        assert len(clone.nodes) == 2
        assert len(clone.dependencies) == 1

        clone_dep = clone.dependencies[0]
        assert clone_dep.source_node.name == "Step 1"
        assert clone_dep.target_node.name == "Step 2"
        assert clone_dep.source_node_id != n1.id


def test_workflow_api_export_import_endpoints(client, app, auth_headers, test_user):
    """Test HTTP endpoints GET /api/workflows/<id>/export, POST /api/workflows/import, and POST /api/workflows/<id>/duplicate."""
    with app.app_context():
        agent = Agent(
            name="Endpoint Test Agent",
            agent_type="custom",
            system_instructions="Handle test.",
            user_id=test_user.id,
            status=AGENT_STATUS_ACTIVE,
        )
        db.session.add(agent)
        db.session.commit()

        wf = Workflow(
            user_id=test_user.id,
            name="API Exportable Pipeline",
            description="Testing API export and import",
            status=WORKFLOW_STATUS_ACTIVE,
        )
        db.session.add(wf)
        db.session.commit()

        n1 = WorkflowNode(workflow_id=wf.id, agent_id=agent.id, name="Start Task")
        db.session.add(n1)
        db.session.commit()

        wf_pub_id = wf.public_id

    # 1. Test GET /api/workflows/<id>/export
    res_export = client.get(f"/api/workflows/{wf_pub_id}/export", headers=auth_headers)
    assert res_export.status_code == 200
    export_json = res_export.get_json()
    assert export_json["schema_version"] == "1.0"
    assert export_json["name"] == "API Exportable Pipeline"
    assert len(export_json["nodes"]) == 1

    # 2. Test POST /api/workflows/import
    import_body = {
        "schema_version": "1.0",
        "name": "Imported via HTTP",
        "description": "Created from export JSON",
        "nodes": [
            {
                "id": "node_1",
                "name": "Imported Task",
                "agent_type": "custom",
                "instructions": "Execute imported task.",
            }
        ],
        "dependencies": [],
    }
    res_import = client.post("/api/workflows/import", json=import_body, headers=auth_headers)
    assert res_import.status_code == 201
    import_resp = res_import.get_json()
    assert import_resp["workflow"]["name"] == "Imported via HTTP"
    assert "warnings" in import_resp

    # 3. Test POST /api/workflows/<id>/duplicate
    res_dup = client.post(f"/api/workflows/{wf_pub_id}/duplicate", headers=auth_headers)
    assert res_dup.status_code == 201
    dup_resp = res_dup.get_json()
    assert dup_resp["name"] == "Copy of API Exportable Pipeline"
