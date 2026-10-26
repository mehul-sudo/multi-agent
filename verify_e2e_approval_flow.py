import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath("."))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.agent import Agent, AGENT_STATUS_ACTIVE
from app.models.workflow import Workflow, WORKFLOW_STATUS_ACTIVE
from app.models.workflow_node import WorkflowNode
from app.models.workflow_execution import (
    WorkflowExecution,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_COMPLETED,
)
from app.models.task_execution import (
    TaskExecution,
    TASK_STATUS_BLOCKED,
    TASK_STATUS_COMPLETED,
)
from app.models.approval_request import (
    ApprovalRequest,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_APPROVED,
)
from app.services.execution_engine import WorkflowExecutionEngine
from app.services.approval_service import resolve_approval_request


def run_e2e_approval_test():
    print("=" * 60)
    print("STARTING E2E HUMAN-IN-THE-LOOP APPROVAL TEST")
    print("=" * 60)

    app = create_app("testing")
    with app.app_context():
        db.create_all()

        from app.security.password import hash_password

        # 1. Setup User
        user = User.query.filter_by(username="test_e2e_user").first()
        if not user:
            user = User(
                username="test_e2e_user",
                email="test_e2e@example.com",
                password_hash=hash_password("SecurePassword123!"),
                role="admin",
            )
            db.session.add(user)
            db.session.commit()

        # Approver user
        approver = User.query.filter_by(username="test_e2e_approver").first()
        if not approver:
            approver = User(
                username="test_e2e_approver",
                email="test_e2e_approver@example.com",
                password_hash=hash_password("SecurePassword123!"),
                role="admin",
            )
            db.session.add(approver)
            db.session.commit()

        # 2. Setup Email Agent with requires_human_approval = True
        agent = Agent.query.filter_by(name="E2E Email Sender").first()
        if not agent:
            agent = Agent(
                name="E2E Email Sender",
                agent_type="email",
                user_id=user.id,
                description="Agent that sends emails with approval",
                status=AGENT_STATUS_ACTIVE,
                requires_human_approval=True,
                provider="mock",
                model="mock-v1",
                system_instructions="Send an email to {to} with subject {subject}",
            )
            db.session.add(agent)
            db.session.commit()
        else:
            agent.requires_human_approval = True
            db.session.commit()

        # 3. Setup Workflow with Node
        wf = Workflow(
            name="E2E Human Approval Workflow",
            description="Testing human-in-the-loop email workflow",
            user_id=user.id,
            status=WORKFLOW_STATUS_ACTIVE,
            version=1,
        )
        db.session.add(wf)
        db.session.commit()

        node = WorkflowNode(
            workflow_id=wf.id,
            agent_id=agent.id,
            name="Send Executive Email",
            instructions="Send email to ceo@company.com with quarterly updates",
            input_mapping={
                "instructions": "Send email to ceo@company.com with quarterly updates",
                "to": "ceo@company.com",
                "subject": "Q3 Executive Update",
                "body": "Here is the summary of Q3 performance.",
                "mode": "send",
            },
        )
        db.session.add(node)
        db.session.commit()

        # 4. Trigger Execution
        print("\n[Step 1] Triggering workflow execution...")
        from app.models.workflow_execution import EXECUTION_STATUS_QUEUED
        execution = WorkflowExecution(
            workflow_id=wf.id,
            user_id=user.id,
            status=EXECUTION_STATUS_QUEUED,
            input_data={},
            triggered_by="manual",
        )
        db.session.add(execution)
        db.session.commit()

        engine = WorkflowExecutionEngine()
        execution = engine.run_execution(execution.id)
        print(f"Execution started: {execution.public_id}, Current Status: {execution.status}")

        # 5. Verify Execution Paused and Task Blocked
        print("\n[Step 2] Verifying execution paused and task blocked for approval...")
        db.session.refresh(execution)
        print(f"Execution Status: {execution.status}")
        assert execution.status == EXECUTION_STATUS_PAUSED, f"Expected paused, got {execution.status}"

        te = TaskExecution.query.filter_by(workflow_execution_id=execution.id).first()
        assert te is not None, "TaskExecution not found"
        print(f"TaskExecution Status: {te.status}")
        assert te.status == TASK_STATUS_BLOCKED, f"Expected blocked, got {te.status}"

        # 6. Verify ApprovalRequest Created
        print("\n[Step 3] Verifying pending ApprovalRequest...")
        appr_req = ApprovalRequest.query.filter_by(
            workflow_execution_id=execution.id,
            task_execution_id=te.id,
            status=APPROVAL_STATUS_PENDING,
        ).first()
        assert appr_req is not None, "ApprovalRequest not created"
        print(f"Found ApprovalRequest: ID={appr_req.public_id}")
        print(f"Action: {appr_req.requested_action}")
        print(f"Risk Level: {appr_req.risk_level}")
        print(f"Assigned Approver ID: {appr_req.assigned_approver_user_id}")

        # 7. Approve the Request as designated approver
        print("\n[Step 4] Approving request via resolve_approval_request...")
        resolved = resolve_approval_request(
            approval_id=appr_req.id,
            user_id=approver.id,
            approve=True,
            comments="Approved by Security Executive",
        )
        assert resolved.status == APPROVAL_STATUS_APPROVED
        print(f"ApprovalRequest Status: {resolved.status}")

        # 8. Verify Workflow Execution Resumed and Completed
        print("\n[Step 5] Verifying workflow execution resumed to completion...")
        db.session.refresh(execution)
        db.session.refresh(te)

        print(f"Final TaskExecution Status: {te.status}")
        print(f"Final TaskExecution Output Data: {te.output_data}")
        assert te.status == TASK_STATUS_COMPLETED, f"Expected task completed, got {te.status}"
        assert te.output_data.get("status") == "sent" or te.output_data.get("status") == "simulated", f"Unexpected output status: {te.output_data}"
        assert "simulation_only" in te.output_data, "simulation_only flag missing in output data"
        print(f"Simulation flag: {te.output_data.get('simulation_only')}")
        print(f"Provider: {te.output_data.get('provider')}")

        print(f"Final WorkflowExecution Status: {execution.status}")
        assert execution.status == EXECUTION_STATUS_COMPLETED, f"Expected workflow completed, got {execution.status}"

        # 9. Verify Idempotency (prevent duplicate approval action)
        print("\n[Step 6] Verifying idempotency / double-approval rejection...")
        try:
            resolve_approval_request(
                approval_id=appr_req.id,
                user_id=approver.id,
                approve=True,
            )
            print("ERROR: Should have raised ValueError for already resolved request!")
            sys.exit(1)
        except ValueError as e:
            print(f"Correctly rejected duplicate resolution: {e}")

        # 10. Verify Rejection Flow
        print("\n[Step 7] Verifying Rejection Flow...")
        from app.models.approval_request import APPROVAL_STATUS_REJECTED
        from app.models.task_execution import TASK_STATUS_FAILED
        from app.models.workflow_execution import EXECUTION_STATUS_FAILED

        execution2 = WorkflowExecution(
            workflow_id=wf.id,
            user_id=user.id,
            status=EXECUTION_STATUS_QUEUED,
            input_data={},
            triggered_by="manual",
        )
        db.session.add(execution2)
        db.session.commit()

        execution2 = engine.run_execution(execution2.id)
        assert execution2.status == EXECUTION_STATUS_PAUSED

        te2 = TaskExecution.query.filter_by(workflow_execution_id=execution2.id).first()
        assert te2.status == TASK_STATUS_BLOCKED

        appr_req2 = ApprovalRequest.query.filter_by(
            workflow_execution_id=execution2.id,
            task_execution_id=te2.id,
            status=APPROVAL_STATUS_PENDING,
        ).first()
        assert appr_req2 is not None

        resolved2 = resolve_approval_request(
            approval_id=appr_req2.id,
            user_id=approver.id,
            approve=False,
            comments="Rejected by security policy",
        )
        assert resolved2.status == APPROVAL_STATUS_REJECTED

        db.session.refresh(execution2)
        db.session.refresh(te2)
        print(f"Post-rejection Task Status: {te2.status}")
        print(f"Post-rejection Execution Status: {execution2.status}")
        assert te2.status == TASK_STATUS_FAILED
        assert execution2.status == EXECUTION_STATUS_FAILED
        print("Rejection flow cleanly marked task and execution as failed!")

        print("\n" + "=" * 60)
        print("ALL E2E HUMAN-IN-THE-LOOP TESTS (APPROVAL + REJECTION) PASSED!")
        print("=" * 60)


if __name__ == "__main__":
    run_e2e_approval_test()
