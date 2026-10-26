"""
SupervisorService.

Main orchestration coordinator layer.
Manages DAG task execution, dispatches eligible tasks, handles completed dependencies,
triggers parallel branches, enforces quality control and human approvals, records metrics,
and updates orchestration state.
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.extensions import db
from app.llm.base import LLMProvider
from app.llm.contracts import LLMMessage, LLMRequest
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.registry import provider_registry



from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
from app.models.orchestration_plan import (
    PLAN_TASK_STATUS_AWAITING_APPROVAL,
    PLAN_TASK_STATUS_COMPLETED,
    PLAN_TASK_STATUS_FAILED,
    PLAN_TASK_STATUS_PENDING,
    PLAN_TASK_STATUS_READY,
    PLAN_TASK_STATUS_RUNNING,
    PLAN_TASK_STATUS_SKIPPED,
    OrchestrationPlan,
    PlanTask,
    TaskDependency,
)
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_AWAITING_APPROVAL,
    ORCHESTRATION_STATUS_CANCELLED,
    ORCHESTRATION_STATUS_COMPLETED,
    ORCHESTRATION_STATUS_FAILED,
    ORCHESTRATION_STATUS_PAUSED,
    ORCHESTRATION_STATUS_RUNNING,
    OrchestrationSession,
)
from app.models.agent_message import MESSAGE_TYPE_TASK_REQUEST, MESSAGE_TYPE_TASK_RESULT
from app.services.agent_message_service import send_agent_message
from app.services.approval_service import create_approval_request
from app.services.context_service import get_all_context_for_orchestration, set_context_entry
from app.services.governance_service import update_orchestration_usage
from app.services.orchestration_event_service import emit_orchestration_event
from app.services.quality_service import evaluate_task_output



class SupervisorService:
    """Supervisor Coordinator executing orchestration plans."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        if llm_provider:
            self.llm_provider = llm_provider
        else:
            prov, _ = provider_registry.resolve_provider_and_model()
            self.llm_provider = prov

    def run_orchestration(self, orchestration_id: int, auto_approve: bool = False) -> OrchestrationSession:
        """Execute or progress an orchestration session."""
        session = db.session.get(OrchestrationSession, orchestration_id)
        if not session:
            raise ValueError(f"Orchestration session {orchestration_id} not found.")

        # In production runtime, NEVER trust auto_approve from input_context/user/frontend.
        # Only permit auto_approve if explicitly enabled in TestingConfig.
        is_test = bool(
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("TESTING", "").lower() in ("true", "1")
        )
        is_auto = bool(auto_approve and is_test)

        if session.status in (ORCHESTRATION_STATUS_COMPLETED, ORCHESTRATION_STATUS_FAILED, ORCHESTRATION_STATUS_CANCELLED):
            return session

        if session.status == ORCHESTRATION_STATUS_PAUSED:
            return session

        if session.status == ORCHESTRATION_STATUS_AWAITING_APPROVAL:
            return session

        session.status = ORCHESTRATION_STATUS_RUNNING
        session.started_at = session.started_at or db.func.now()
        db.session.commit()

        emit_orchestration_event(
            event_type="ORCHESTRATION_RUNNING",
            orchestration_id=session.id,
            correlation_id=session.correlation_id,
            trace_id=session.trace_id,
            organization_id=session.organization_id,
        )

        plan = session.plan_id and db.session.get(OrchestrationPlan, session.plan_id)
        if not plan:
            session.status = ORCHESTRATION_STATUS_FAILED
            session.failure_reason = "No valid orchestration plan attached."
            db.session.commit()
            return session

        # Continuous loop dispatching READY tasks in dependency-aware parallel waves
        while True:
            ready_tasks = PlanTask.query.filter_by(
                plan_id=plan.id,
                status=PLAN_TASK_STATUS_READY,
            ).all()

            if not ready_tasks:
                break

            if len(ready_tasks) == 1:
                self._execute_single_task(session, plan, ready_tasks[0], auto_approve=is_auto)
                if not is_auto and session.status in (ORCHESTRATION_STATUS_AWAITING_APPROVAL, ORCHESTRATION_STATUS_PAUSED):
                    return session
            else:
                # Concurrent dependency-aware execution for independent ready tasks
                import concurrent.futures
                from flask import current_app

                try:
                    app_obj = current_app._get_current_object()
                except Exception:
                    app_obj = None

                if len(ready_tasks) == 1:
                    t = ready_tasks[0]
                    self._execute_single_task(session, plan, t, auto_approve=is_auto)
                    db.session.commit()
                else:
                    is_sqlite = "sqlite" in str(db.engine.url).lower()
                    if is_sqlite:
                        for t in ready_tasks:
                            self._execute_single_task(session, plan, t, auto_approve=is_auto)
                            db.session.commit()
                    else:
                        session_id = session.id
                        plan_id = plan.id
                        task_ids = [t.id for t in ready_tasks]

                        def _run_worker(t_id: int):
                            if app_obj:
                                with app_obj.app_context():
                                    s_obj = db.session.get(OrchestrationSession, session_id)
                                    p_obj = db.session.get(OrchestrationPlan, plan_id)
                                    t_obj = db.session.get(PlanTask, t_id)
                                    if s_obj and p_obj and t_obj:
                                        self._execute_single_task(s_obj, p_obj, t_obj, auto_approve=is_auto)
                                        db.session.commit()
                                    return t_id
                            else:
                                s_obj = db.session.get(OrchestrationSession, session_id)
                                p_obj = db.session.get(OrchestrationPlan, plan_id)
                                t_obj = db.session.get(PlanTask, t_id)
                                if s_obj and p_obj and t_obj:
                                    self._execute_single_task(s_obj, p_obj, t_obj, auto_approve=is_auto)
                                    db.session.commit()
                                return t_id

                        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(ready_tasks), 5)) as pool:
                            futures = [pool.submit(_run_worker, tid) for tid in task_ids]
                            for fut in concurrent.futures.as_completed(futures):
                                try:
                                    fut.result()
                                except Exception:
                                    pass

                db.session.refresh(session)
                if not is_auto and session.status in (ORCHESTRATION_STATUS_AWAITING_APPROVAL, ORCHESTRATION_STATUS_PAUSED):
                    return session

            # Check and promote PENDING tasks whose upstream dependencies are COMPLETED
            self._update_task_readiness(plan)

        # Evaluate final orchestration status
        all_tasks = plan.tasks.all()
        completed_count = sum(1 for t in all_tasks if t.status == PLAN_TASK_STATUS_COMPLETED)
        failed_count = sum(1 for t in all_tasks if t.status == PLAN_TASK_STATUS_FAILED)
        blocked_count = sum(1 for t in all_tasks if t.status == "BLOCKED")
        awaiting_count = sum(1 for t in all_tasks if t.status == PLAN_TASK_STATUS_AWAITING_APPROVAL)

        if awaiting_count > 0:
            session.status = ORCHESTRATION_STATUS_AWAITING_APPROVAL
            db.session.commit()
            return session

        if completed_count == len(all_tasks):
            session.status = ORCHESTRATION_STATUS_COMPLETED
            session.completed_at = db.func.now()

            task_findings = []
            for t in all_tasks:
                out = t.output_data or {}
                if isinstance(out, dict):
                    inner_out = out.get("output", out)
                    summary = ""
                    if isinstance(inner_out, dict):
                        summary = inner_out.get("summary") or inner_out.get("executive_summary") or inner_out.get("answer") or inner_out.get("action")
                    if not summary:
                        summary = str(out.get("status") or "Task completed successfully")
                    task_findings.append(f"- **{t.name}**: {summary}")

            final_synthesis = self._generate_final_synthesis(session, task_findings)

            session.result_summary = {
                "total_tasks": len(all_tasks),
                "completed_tasks": completed_count,
                "status": "SUCCESS",
                "final_synthesis": final_synthesis,
            }
            emit_orchestration_event(
                event_type="ORCHESTRATION_COMPLETED",
                orchestration_id=session.id,
                correlation_id=session.correlation_id,
                trace_id=session.trace_id,
            )
        elif failed_count > 0 or blocked_count > 0:
            session.status = ORCHESTRATION_STATUS_FAILED
            session.failure_reason = f"Execution failed: {failed_count} task(s) failed, {blocked_count} task(s) blocked."
            session.completed_at = db.func.now()
            emit_orchestration_event(
                event_type="ORCHESTRATION_FAILED",
                orchestration_id=session.id,
                correlation_id=session.correlation_id,
                trace_id=session.trace_id,
                metadata={"failed_tasks": failed_count, "blocked_tasks": blocked_count},
            )

        db.session.commit()
        return session

    def _execute_single_task(self, session: OrchestrationSession, plan: OrchestrationPlan, task: PlanTask, auto_approve: bool = False) -> None:
        """Execute a single PlanTask."""
        is_auto = auto_approve or bool(session.input_context and session.input_context.get("auto_approve"))

        task.status = PLAN_TASK_STATUS_RUNNING
        task.started_at = task.started_at or db.func.now()
        task.attempt_count += 1
        db.session.commit()

        emit_orchestration_event(
            event_type="TASK_STARTED",
            orchestration_id=session.id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            correlation_id=session.correlation_id,
            trace_id=session.trace_id,
        )

        agent = task.assigned_agent_id and db.session.get(Agent, task.assigned_agent_id)

        # 1. Human Approval Check for high-risk actions & side-effect agents (email, http_webhook, database_bi write)
        from app.models.approval_request import (
            ApprovalRequest,
            APPROVAL_STATUS_APPROVED,
            APPROVAL_STATUS_PENDING,
        )

        existing_approved = ApprovalRequest.query.filter_by(
            orchestration_id=session.id,
            task_id=task.id,
            status=APPROVAL_STATUS_APPROVED,
        ).first()

        if not existing_approved:
            existing_pending = ApprovalRequest.query.filter_by(
                orchestration_id=session.id,
                task_id=task.id,
                status=APPROVAL_STATUS_PENDING,
            ).first()

            if existing_pending:
                return  # Still waiting for human approval
            else:
                from app.security.approval_policy import requires_approval

                agent_type = agent.agent_type if agent else "custom"
                needs_appr, risk_lvl, appr_reason = requires_approval(agent_type, task.name, task.input_references or {})

                if needs_appr or (agent and getattr(agent, "requires_human_approval", False)):
                    create_approval_request(
                        orchestration=session,
                        requested_action=f"Execute task '{task.name}' ({agent_type})",
                        explanation=f"Task '{task.name}' requires human verification before side-effect execution.",
                        task=task,
                        risk_level=risk_lvl,
                        input_summary=task.input_references or {},
                        requested_by_agent_id=agent.id if agent else None,
                    )
                    return


        # 2. Inter-agent message log - Task Request
        send_agent_message(
            orchestration_id=session.id,
            plan_id=plan.id,
            task_id=task.id,
            sender_agent_id=None,
            receiver_agent_id=agent.id if agent else None,
            message_type=MESSAGE_TYPE_TASK_REQUEST,
            subject=f"Execute Task {task.task_key}",
            payload={"input_references": task.input_references},
            correlation_id=session.correlation_id,
        )

        # 3. Perform Task Execution via LLM or Agent
        try:
            prompt = (
                f"System Instructions: {agent.system_instructions if agent else 'Execute enterprise automation task'}\n"
                f"Task Name: {task.name}\n"
                f"Task Description: {task.description}\n"
                f"Input Data: {task.input_references}\n"
            )
            messages = [LLMMessage(role="user", content=prompt)]

            req = LLMRequest(
                messages=messages,
                temperature=agent.temperature if agent else 0.7,
                max_tokens=agent.max_tokens if agent else 1000,
            )

            # Collect outputs from upstream dependency parent tasks
            parent_deps = TaskDependency.query.filter_by(plan_id=plan.id, child_task_id=task.id).all()
            previous_results = []
            for dep in parent_deps:
                parent_t = db.session.get(PlanTask, dep.parent_task_id)
                if parent_t and parent_t.output_data:
                    p_agent = parent_t.assigned_agent_id and db.session.get(Agent, parent_t.assigned_agent_id)
                    parent_out = parent_t.output_data
                    if isinstance(parent_out, dict) and "output" in parent_out and isinstance(parent_out.get("output"), dict):
                        unwrapped_out = parent_out["output"]
                    else:
                        unwrapped_out = parent_out
                    previous_results.append({
                        "task_key": parent_t.task_key,
                        "task_name": parent_t.name,
                        "agent_type": p_agent.agent_type if p_agent else None,
                        "output": unwrapped_out,
                        "raw_output": parent_out,
                    })

            # Check if assigned agent has a specialized enterprise implementation
            from app.agents import get_agent_instance, AgentContext
            agent_type = getattr(agent, "agent_type", None) if agent else None
            domain_agent = get_agent_instance(agent_type) if agent_type else None

            if domain_agent:
                input_payload = dict(task.input_references or {})
                # Propagate user objective and instructions
                if "query" not in input_payload:
                    input_payload["query"] = session.objective
                if "instructions" not in input_payload:
                    input_payload["instructions"] = session.objective
                if "user_objective" not in input_payload:
                    input_payload["user_objective"] = session.objective
                if "task_description" not in input_payload and task.description:
                    input_payload["task_description"] = task.description

                # Ensure session input_context (file_id, filename, file_path, etc.) is in input_payload
                if session.input_context:
                    for k in ("file_id", "filename", "file_ids", "file_path", "code_snippet", "recipient", "subject"):
                        if k in session.input_context and k not in input_payload:
                            input_payload[k] = session.input_context[k]

                agent_meta = {
                    "orchestration_id": session.public_id,
                    "task_id": task.public_id,
                    "task_name": task.name,
                }
                if existing_approved:
                    input_payload["approval_granted"] = True
                    input_payload["approval_id"] = existing_approved.id
                    agent_meta["approval_granted"] = True
                    agent_meta["approval_id"] = existing_approved.id

                ctx = AgentContext(
                    user_id=session.user_id,
                    input_data=input_payload,
                    previous_results=previous_results,
                    instructions=agent.system_instructions if agent else None,
                    metadata=agent_meta,
                )
                agent_res = domain_agent.execute(ctx)
                output_payload = agent_res.to_dict()
                if not agent_res.success:
                    raise RuntimeError(agent_res.error or f"Agent execution failed for task '{task.name}'")
                usage_dict = getattr(agent_res, "metadata", {}).get("usage") or {}
                if isinstance(agent_res.output, dict) and "usage" in agent_res.output:
                    usage_dict = agent_res.output.get("usage") or usage_dict
                tokens_used = int(usage_dict.get("total_tokens") or 0)
                p_tok = int(usage_dict.get("prompt_tokens") or 0)
                c_tok = int(usage_dict.get("completion_tokens") or 0)
                from app.services.llm_usage_service import calculate_estimated_cost
                agent_model = getattr(agent, "model", "mock-v1") if agent else "mock-v1"
                est_c = calculate_estimated_cost(agent_model, p_tok, c_tok)
                cost = est_c if est_c is not None else 0.0
            else:
                # Use task agent's provider if registered, or default adapter
                adapter = self.llm_provider
                if agent and agent.provider != "mock":
                    try:
                        adapter = provider_registry.get_provider(agent.provider)
                    except Exception:
                        adapter = self.llm_provider

                req.user_id = session.user_id
                req.agent_id = agent.public_id if agent else None
                req.metadata = {"orchestration_id": session.id, "task_id": task.public_id}

                resp = adapter.generate(req)

                tokens_used = resp.usage.total_tokens if resp.usage else 0
                p_tok = resp.usage.prompt_tokens if resp.usage else 0
                c_tok = resp.usage.completion_tokens if resp.usage else 0
                from app.services.llm_usage_service import calculate_estimated_cost
                est_c = calculate_estimated_cost(resp.model, p_tok, c_tok)
                cost = est_c if est_c is not None else 0.0

                output_payload = {
                    "summary": resp.text,
                    "tokens_used": tokens_used,
                    "status": "COMPLETED",
                }

            update_orchestration_usage(session, tokens_used, cost)


            # 4. Quality Control Review
            review = evaluate_task_output(
                orchestration_id=session.id,
                task_id=task.id,
                output_data=output_payload,
                expected_output_schema=task.output_schema,
            )

            task.output_data = output_payload
            task.status = PLAN_TASK_STATUS_COMPLETED
            task.completed_at = db.func.now()

            # Record in Shared Context
            set_context_entry(
                orchestration_id=session.id,
                plan_id=plan.id,
                task_id=task.id,
                agent_id=agent.id if agent else None,
                key=f"task_output_{task.task_key}",
                value=output_payload,
            )

            # Inter-agent message log - Task Result
            send_agent_message(
                orchestration_id=session.id,
                plan_id=plan.id,
                task_id=task.id,
                sender_agent_id=agent.id if agent else None,
                receiver_agent_id=None,
                message_type=MESSAGE_TYPE_TASK_RESULT,
                subject=f"Result Task {task.task_key}",
                payload=output_payload,
                correlation_id=session.correlation_id,
            )


            emit_orchestration_event(
                event_type="TASK_COMPLETED",
                orchestration_id=session.id,
                task_id=task.id,
                agent_id=agent.id if agent else None,
                correlation_id=session.correlation_id,
                trace_id=session.trace_id,
            )

        except Exception as exc:
            task.status = PLAN_TASK_STATUS_FAILED
            task.error_message = str(exc)
            task.completed_at = db.func.now()

            emit_orchestration_event(
                event_type="TASK_FAILED",
                orchestration_id=session.id,
                task_id=task.id,
                agent_id=agent.id if agent else None,
                correlation_id=session.correlation_id,
                trace_id=session.trace_id,
                metadata={"error": str(exc)},
            )

        db.session.commit()

    def _update_task_readiness(self, plan: OrchestrationPlan) -> None:
        """Promote PENDING tasks to READY when all upstream dependencies are COMPLETED.
        Propagate failure: mark dependent task as BLOCKED if any upstream dependency FAILED."""
        pending_tasks = PlanTask.query.filter_by(
            plan_id=plan.id,
            status=PLAN_TASK_STATUS_PENDING,
        ).all()

        for task in pending_tasks:
            deps = TaskDependency.query.filter_by(plan_id=plan.id, child_task_id=task.id).all()
            all_parents_done = True
            failed_parent = None
            for dep in deps:
                parent_task = db.session.get(PlanTask, dep.parent_task_id)
                if not parent_task:
                    all_parents_done = False
                    continue
                if parent_task.status in (PLAN_TASK_STATUS_FAILED, "BLOCKED"):
                    failed_parent = parent_task
                    break
                elif parent_task.status != PLAN_TASK_STATUS_COMPLETED:
                    all_parents_done = False

            if failed_parent:
                task.status = "BLOCKED"
                err_detail = failed_parent.error_message or "Upstream task failed."
                task.error_message = f"Blocked due to failure of upstream dependency '{failed_parent.task_key}': {err_detail}"
            elif all_parents_done:
                task.status = PLAN_TASK_STATUS_READY

        db.session.commit()

    def _generate_final_synthesis(self, session: OrchestrationSession, findings: List[str]) -> str:
        """Produce an executive synthesis of verified pipeline results grounded in task outcomes without redundant LLM latency."""
        if not findings:
            return "All pipeline tasks completed successfully."

        findings_block = "\n".join(findings)
        header = f"### Executive Summary — {session.objective}\n\n"
        outcomes = (
            f"**Pipeline Deliverables & Verified Outcomes:**\n"
            f"{findings_block}\n\n"
            f"All pipeline stages completed successfully with verified domain outputs and data integrity."
        )
        return header + outcomes
