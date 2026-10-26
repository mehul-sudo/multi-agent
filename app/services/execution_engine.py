"""
Workflow Execution Engine.

Provider-agnostic execution engine for running multi-agent workflows.
Includes abstract interfaces for AgentExecutor, TaskExecutor, WorkflowExecutor, and ExecutionContext,
along with local mock and production LLMAgentExecutor implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.api.v1.streaming import emit_execution_log
except ImportError:
    def emit_execution_log(job_id, event_type, data):
        pass  # SSE streaming not available

from app.extensions import db
from app.llm.contracts import LLMMessage, LLMRequest, LLMResponse
from app.llm.errors import LLMError, LLMResponseFormatError
from app.llm.registry import provider_registry
from app.llm.resilience import LLMResilienceManager
from app.llm.structured_output import parse_and_validate_json
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.task_execution import (
    TASK_STATUS_BLOCKED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_READY,
    TASK_STATUS_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SKIPPED,
    TaskExecution,
)
from app.models.workflow import WORKFLOW_STATUS_ACTIVE, Workflow
from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_ALWAYS,
    DEPENDENCY_TYPE_ON_FAILURE,
    DEPENDENCY_TYPE_ON_SUCCESS,
)
from app.models.workflow_execution import (
    EXECUTION_STATUS_CANCELLED,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_PARTIALLY_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_QUEUED,
    EXECUTION_STATUS_RUNNING,
    WorkflowExecution,
)
from app.models.workflow_node import WorkflowNode
from app.services.condition_evaluator import evaluate_condition
from app.services.execution_plan_service import generate_execution_plan
from app.services.graph_validation_service import validate_workflow_graph
from app.services.llm_usage_service import check_agent_budget, record_llm_usage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Abstract Protocols & Context
# ---------------------------------------------------------------------------

class ExecutionContext:
    """State container for storing input data, global context, and task outputs across pipeline stages."""

    def __init__(self, initial_input: Dict[str, Any] | None = None):
        self.input_data: Dict[str, Any] = initial_input or {}
        self.context: Dict[str, Any] = {"input": self.input_data, "previous_results": {}}
        self.node_outputs: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.latest_output: Optional[Dict[str, Any]] = None

    def set_output(self, key: str, value: Any) -> None:
        """Store a task output by output key."""
        if key:
            self.node_outputs[key] = value
            self.context[key] = value
        self.latest_output = value

    def record_node_result(self, node: WorkflowNode, output: Any, artifacts: Optional[List[Any]] = None) -> None:
        """Record node result under all relevant keys, preserve history, and accumulate into context."""
        self.latest_output = output
        ag_type = getattr(node.agent, "agent_type", None) if node.agent else None
        ag_name = getattr(node.agent, "name", None) if node.agent else node.name

        # Extract and normalize artifact references
        art_list: List[Dict[str, Any]] = []
        if artifacts:
            for a in artifacts:
                if hasattr(a, "to_dict"):
                    art_list.append(a.to_dict())
                elif isinstance(a, dict):
                    art_list.append(a)
                elif hasattr(a, "name") and hasattr(a, "path"):
                    art_list.append({
                        "name": a.name,
                        "filename": a.name,
                        "path": a.path,
                        "url": getattr(a, "url", None),
                        "type": getattr(a, "type", "file"),
                    })

        if isinstance(output, dict):
            if output.get("all_artifacts") and isinstance(output["all_artifacts"], list):
                for a in output["all_artifacts"]:
                    if isinstance(a, dict) and a not in art_list:
                        art_list.append(a)
            elif output.get("artifact") and isinstance(output["artifact"], dict):
                if output["artifact"] not in art_list:
                    art_list.append(output["artifact"])

        # Determine human-readable summary
        summary_val = ""
        if isinstance(output, dict):
            summary_val = (
                output.get("summary")
                or output.get("result_summary")
                or output.get("reportTitle")
                or output.get("answer")
                or (f"Database query returned {output.get('rowCount', 0)} rows" if "rowCount" in output else "")
                or (f"Security scan identified {len(output.get('findings', []))} findings" if "findings" in output else "")
                or (f"HTTP {output.get('statusCode', '')} response received" if "statusCode" in output else "")
                or "Completed successfully."
            )

        # Append to chronological pipeline history
        self.history.append({
            "node_id": node.public_id,
            "node_name": node.name,
            "agent_type": ag_type or "custom",
            "agent_name": ag_name or node.name,
            "status": "completed",
            "output": output,
            "artifacts": art_list,
            "summary": summary_val,
        })

        if node.output_key:
            self.node_outputs[node.output_key] = output
            self.context[node.output_key] = output
        if node.public_id:
            self.node_outputs[node.public_id] = output
        if node.name:
            self.node_outputs[node.name] = output
            sanitized_name = node.name.lower().replace(" ", "_")
            self.node_outputs[sanitized_name] = output

            if "previous_results" not in self.context or not isinstance(self.context["previous_results"], dict):
                self.context["previous_results"] = {}
            self.context["previous_results"][node.name] = output
            self.context["previous_results"][sanitized_name] = output

        if getattr(node, "id", None):
            self.node_outputs[f"node_{node.id}"] = output
            self.node_outputs[f"step_{node.id}"] = output

        if getattr(node, "agent", None):
            ag = node.agent
            if getattr(ag, "agent_type", None):
                self.node_outputs[ag.agent_type] = output
                if "previous_results" in self.context and isinstance(self.context["previous_results"], dict):
                    self.context["previous_results"][ag.agent_type] = output
            if getattr(ag, "name", None):
                self.node_outputs[ag.name] = output

        self.context["latest_output"] = output

    def resolve_inputs(
        self,
        input_mapping: Dict[str, Any] | None,
        parent_nodes: Optional[List[WorkflowNode]] = None,
        node: Optional[WorkflowNode] = None,
    ) -> Dict[str, Any]:
        """Map variables from context based on node configuration and input_mapping, passing upstream ancestor results and applying scoped user runtime inputs."""
        import os
        resolved: Dict[str, Any] = {}

        # 1. Base Source of Truth: Node's saved configuration
        if node and node.configuration and isinstance(node.configuration, dict):
            for k, v in node.configuration.items():
                if v is not None and v != "":
                    if k in ("body", "message") and parent_nodes:
                        from app.agents.email_agent import EmailAgent
                        if EmailAgent._is_generic_body(str(v)):
                            continue
                    if k == "subject" and parent_nodes:
                        from app.agents.email_agent import EmailAgent
                        if EmailAgent._is_generic_subject(str(v)):
                            continue
                    resolved[k] = v

        # 2. Base Source of Truth: Node's static / variable input_mapping
        def _get_nested_val(data_source: Any, key_path: str) -> Any:
            if not key_path or not isinstance(data_source, dict):
                return None
            if key_path in data_source:
                return data_source[key_path]
            curr = data_source
            for part in key_path.split("."):
                if isinstance(curr, dict):
                    curr = curr.get(part)
                elif hasattr(curr, part):
                    curr = getattr(curr, part)
                else:
                    return None
                if curr is None:
                    return None
            return curr

        input_mapping = input_mapping or {}
        for param, mapping_spec in input_mapping.items():
            if isinstance(mapping_spec, str) and mapping_spec.startswith("$context."):
                path = mapping_spec[len("$context."):]
                val = _get_nested_val(self.context, path)
                if val is None:
                    val = _get_nested_val(self.node_outputs, path)
                if val is not None:
                    resolved[param] = val
            elif isinstance(mapping_spec, str) and mapping_spec.startswith("$input."):
                path = mapping_spec[len("$input."):]
                val = _get_nested_val(self.input_data, path)
                if val is not None:
                    resolved[param] = val
            elif mapping_spec is not None:
                if param in ("body", "message") and parent_nodes:
                    from app.agents.email_agent import EmailAgent
                    if EmailAgent._is_generic_body(str(mapping_spec)):
                        continue
                if param == "subject" and parent_nodes:
                    from app.agents.email_agent import EmailAgent
                    if EmailAgent._is_generic_subject(str(mapping_spec)):
                        continue
                resolved[param] = mapping_spec

        # 3. Node instructions fallback
        if node and node.instructions and "instructions" not in resolved:
            resolved["instructions"] = node.instructions

        # 4. Accumulate standard output fields from earlier stages in history
        for hist_item in self.history:
            h_out = hist_item.get("output")
            if isinstance(h_out, dict):
                for k in (
                    "data", "metrics", "summary", "analysis", "insights", "content",
                    "report_url", "findings", "key_findings", "rows", "numbers",
                    "statistics", "citations", "sources", "vulnerabilities", "security_score",
                    "findings_by_severity", "recommendations", "scannedTarget", "query",
                    "columns", "rowCount", "kpis", "answer", "key_takeaways", "artifact",
                    "all_artifacts", "downloads", "statusCode", "response_body", "headers"
                ):
                    if k in h_out and k not in resolved:
                        resolved[k] = h_out[k]

        # 5. Upstream parent node outputs (Structured per Section 4 of spec)
        if parent_nodes:
            upstream_results: Dict[str, Any] = {}
            source_results: List[Dict[str, Any]] = []
            for p in parent_nodes:
                p_out = (
                    self.node_outputs.get(p.public_id)
                    or self.node_outputs.get(p.name)
                    or (self.node_outputs.get(p.output_key) if p.output_key else None)
                )
                if p_out is not None:
                    p_ag_type = getattr(p.agent, "agent_type", None) if p.agent else None
                    if not p_ag_type:
                        # Infer agent type from task_type or name
                        nm = p.name.lower()
                        for cand in ("security_analysis", "database_bi", "document_research", "data_analysis", "http_webhook", "report_generation", "email"):
                            if cand in nm or cand.replace("_", " ") in nm or cand.split("_")[0] in nm:
                                p_ag_type = cand
                                break
                    if not p_ag_type and isinstance(p_out, dict):
                        if "statistics" in p_out or "aggregations" in p_out:
                            p_ag_type = "data_analysis"
                        elif "findings" in p_out or "vulnerabilities" in p_out or "security_score" in p_out:
                            p_ag_type = "security_analysis"
                        elif "statusCode" in p_out or "response_body" in p_out:
                            p_ag_type = "http_webhook"
                        elif "rowCount" in p_out or ("rows" in p_out and "columns" in p_out):
                            p_ag_type = "database_bi"
                        elif "citations" in p_out or "passages" in p_out:
                            p_ag_type = "document_research"
                        elif "reportTitle" in p_out or "all_artifacts" in p_out:
                            p_ag_type = "report_generation"
                    p_ag_type = p_ag_type or "custom"

                    # Find artifacts from history for this parent node
                    p_arts = []
                    for h in self.history:
                        if h.get("node_id") == p.public_id or h.get("node_name") == p.name:
                            p_arts = h.get("artifacts", [])
                            break

                    p_summary = ""
                    if isinstance(p_out, dict):
                        p_summary = p_out.get("summary") or p_out.get("result_summary") or p_out.get("reportTitle") or p_out.get("answer") or ""

                    p_status = "completed"
                    if isinstance(p_out, dict) and ((p_out.get("statusCode", 0) >= 400) or (p_out.get("success") is False)):
                        p_status = "failed"

                    parent_record = {
                        "status": p_status,
                        "agent_type": p_ag_type,
                        "node_id": p.public_id,
                        "node_name": p.name,
                        "output": p_out,
                        "artifacts": p_arts,
                        "summary": p_summary,
                    }
                    if isinstance(p_out, dict):
                        for k_out, v_out in p_out.items():
                            if k_out not in parent_record:
                                parent_record[k_out] = v_out

                    # Key by agent_type, public_id, name, and slug
                    upstream_results[p_ag_type] = parent_record
                    upstream_results[p.public_id] = parent_record
                    upstream_results[p.name] = parent_record
                    slug_name = p.name.lower().replace(" ", "_")
                    upstream_results[slug_name] = parent_record
                    source_results.append(parent_record)

                    # Copy standard fields into resolved if not already set
                    if isinstance(p_out, dict):
                        for k in (
                            "data", "metrics", "summary", "analysis", "insights", "content",
                            "report_url", "findings", "key_findings", "rows", "numbers",
                            "statistics", "citations", "sources", "vulnerabilities", "security_score",
                            "findings_by_severity", "recommendations", "scannedTarget", "query",
                            "columns", "rowCount", "kpis", "answer", "key_takeaways", "artifact",
                            "all_artifacts", "downloads", "statusCode", "response_body", "headers"
                        ):
                            if k in p_out and k not in resolved:
                                resolved[k] = p_out[k]

            if upstream_results:
                resolved["upstream_results"] = upstream_results
            if source_results:
                resolved["source_results"] = source_results

        # 6. Chronological pipeline results list containing all executed ancestor nodes
        if self.history:
            resolved["previous_results"] = list(self.history)
            resolved["pipeline_results"] = list(self.history)
        elif self.context.get("previous_results"):
            resolved["previous_results"] = self.context["previous_results"]

        if self.latest_output and "previous_output" not in resolved:
            resolved["previous_output"] = self.latest_output

        # 7. Credential & environment pass-through from execution input_data
        if isinstance(self.input_data, dict):
            for cred_key in ("resend_api_key", "smtp_user", "smtp_password", "email_provider", "email_from", "execution_mode", "user_id"):
                if cred_key in self.input_data and self.input_data[cred_key] is not None:
                    resolved[cred_key] = self.input_data[cred_key]

        # 8. Scoped overrides if input_data has a dict for this node or agent_type
        if node and isinstance(self.input_data, dict):
            agent_type = (node.agent.agent_type if node.agent else "").lower()
            candidate_keys = [node.public_id, node.name, node.name.lower().replace(" ", "_"), agent_type]
            for ck in candidate_keys:
                if ck and ck in self.input_data and isinstance(self.input_data[ck], dict):
                    for k, v in self.input_data[ck].items():
                        if v is not None and v != "":
                            resolved[k] = v

        # 9. Top-level input_data values populate unassigned keys (without stomping on node's saved config)
        if isinstance(self.input_data, dict):
            for k, v in self.input_data.items():
                if v is not None and v != "" and not isinstance(v, dict):
                    if k not in resolved:
                        resolved[k] = v

        # 10. Agent-Specific Semantic Downstream Wiring
        downstream_agent_type = (node.agent.agent_type if node.agent else "").lower() if node else ""

        # A. If downstream agent is REPORT_GENERATION:
        if downstream_agent_type in ("report_generation", "report"):
            # Ensure title is set intelligently if not already in configuration or inputs
            if not resolved.get("title") and not resolved.get("reportTitle"):
                parent_types = [p.agent.agent_type for p in (parent_nodes or []) if p.agent and getattr(p.agent, "agent_type", None)]
                if "security_analysis" in parent_types and "database_bi" in parent_types:
                    resolved["title"] = "Enterprise Security Posture & Database Intelligence Briefing"
                elif "security_analysis" in parent_types:
                    resolved["title"] = "Security Vulnerability & Threat Assessment Report"
                elif "database_bi" in parent_types:
                    resolved["title"] = "Database Business Intelligence & Performance Report"
                elif "data_analysis" in parent_types:
                    resolved["title"] = "Empirical Data Analysis & Statistical Telemetry Report"
                elif "document_research" in parent_types:
                    resolved["title"] = "Document Research & Evidence Synthesis Report"
                elif "http_webhook" in parent_types:
                    resolved["title"] = "External API Telemetry & Integration Report"
                elif len(parent_types) > 1:
                    resolved["title"] = "Integrated Multi-Agent Operational & Strategic Briefing"

        # B. If downstream agent is EMAIL:
        elif downstream_agent_type == "email":
            from app.agents.email_agent import EmailAgent

            # Check if any direct parent node is a Report Generation agent or produced an explicit report artifact
            if not resolved.get("attachments"):
                found_attachments = []
                source_report_name = None
                att_filename = None
                att_format = None

                # Search ONLY direct parent nodes (strict DAG dependency: no history fallback)
                nodes_to_search = list(parent_nodes or [])
                for p in nodes_to_search:
                    p_ag_type = getattr(p.agent, "agent_type", "") if p.agent else ""
                    # Attachments from upstream are ONLY harvested if the parent is a report_generation node
                    # (Mode B: Agent -> Report Generation -> Email).
                    # For Mode A (Direct Agent -> Email), no report artifact is attached!
                    if p_ag_type in ("report_generation", "report"):
                        p_out = self.node_outputs.get(p.public_id) or self.node_outputs.get(p.name) or {}
                        if isinstance(p_out, dict):
                            art = p_out.get("artifact")
                            if isinstance(art, dict) and art.get("path") and os.path.exists(art["path"]):
                                found_attachments.append(art["path"])
                                source_report_name = p_out.get("reportTitle") or p_out.get("title") or p.name
                                att_filename = art.get("filename") or os.path.basename(art["path"])
                                att_format = art.get("type") or p_out.get("format")
                                break
                            all_arts = p_out.get("all_artifacts") or []
                            for a in all_arts:
                                if isinstance(a, dict) and a.get("path") and os.path.exists(a["path"]):
                                    found_attachments.append(a["path"])
                                    source_report_name = p_out.get("reportTitle") or p_out.get("title") or p.name
                                    att_filename = a.get("filename") or os.path.basename(a["path"])
                                    att_format = a.get("type") or p_out.get("format")
                                    break
                            if found_attachments:
                                break

                if found_attachments:
                    resolved["attachments"] = found_attachments
                    if source_report_name:
                        resolved["source_report_name"] = source_report_name
                    if att_filename:
                        resolved["attachment_filename"] = att_filename
                    if att_format:
                        resolved["attachment_format"] = att_format
                    resolved["attachment_status"] = "attached"
                else:
                    resolved["attachments"] = []
                    resolved["attachment_status"] = "none"
                    resolved.pop("attachment_filename", None)
                    resolved.pop("attachment_format", None)
                    resolved.pop("source_report_name", None)

            # Check if current body is generic or empty
            curr_body = resolved.get("body") or resolved.get("message")
            if parent_nodes and EmailAgent._is_generic_body(curr_body):
                synth_records = []
                seen_node_ids = set()
                for p in parent_nodes:
                    p_out = self.node_outputs.get(p.public_id) or self.node_outputs.get(p.name) or {}
                    if isinstance(p_out, dict):
                        p_ag_type = getattr(p.agent, "agent_type", None) if p.agent else None
                        if not p_ag_type:
                            nm = p.name.lower()
                            for cand in ("security_analysis", "database_bi", "document_research", "data_analysis", "http_webhook", "report_generation", "email"):
                                if cand in nm or cand.replace("_", " ") in nm or cand.split("_")[0] in nm:
                                    p_ag_type = cand
                                    break
                        if not p_ag_type:
                            if "statistics" in p_out or "aggregations" in p_out:
                                p_ag_type = "data_analysis"
                            elif "findings" in p_out or "vulnerabilities" in p_out or "security_score" in p_out:
                                p_ag_type = "security_analysis"
                            elif "statusCode" in p_out or "response_body" in p_out:
                                p_ag_type = "http_webhook"
                            elif "rowCount" in p_out or ("rows" in p_out and "columns" in p_out):
                                p_ag_type = "database_bi"
                            elif "citations" in p_out or "passages" in p_out:
                                p_ag_type = "document_research"
                            elif "reportTitle" in p_out or "all_artifacts" in p_out:
                                p_ag_type = "report_generation"
                        p_ag_type = p_ag_type or "custom"

                        synth_records.append({
                            "agent_type": p_ag_type,
                            "node_id": p.public_id,
                            "node_name": p.name,
                            "output": p_out,
                        })
                        seen_node_ids.add(p.public_id)
                        seen_node_ids.add(p.name)

                # Also include predecessor ancestors from history for full multi-agent pipeline visibility
                for h in self.history:
                    h_out = h.get("output")
                    h_id = h.get("node_id")
                    h_name = h.get("node_name")
                    if isinstance(h_out, dict) and h_id not in seen_node_ids and h_name not in seen_node_ids:
                        h_ag_type = h.get("agent_type")
                        if not h_ag_type or h_ag_type == "custom":
                            if "statistics" in h_out or "aggregations" in h_out:
                                h_ag_type = "data_analysis"
                            elif "findings" in h_out or "vulnerabilities" in h_out or "security_score" in h_out:
                                h_ag_type = "security_analysis"
                            elif "statusCode" in h_out or "response_body" in h_out:
                                h_ag_type = "http_webhook"
                            elif "rowCount" in h_out or ("rows" in h_out and "columns" in h_out):
                                h_ag_type = "database_bi"
                            elif "citations" in h_out or "passages" in h_out:
                                h_ag_type = "document_research"
                            elif "reportTitle" in h_out or "all_artifacts" in h_out:
                                h_ag_type = "report_generation"
                        synth_records.append({
                            "agent_type": h_ag_type or "custom",
                            "node_id": h_id,
                            "node_name": h_name,
                            "output": h_out,
                        })
                        seen_node_ids.add(h_id)
                        seen_node_ids.add(h_name)

                if synth_records:
                    body_text, sug_subj = EmailAgent()._synthesize_upstream_findings(synth_records, resolved)
                    if body_text:
                        resolved["body"] = body_text
                    if sug_subj and (not resolved.get("subject") or EmailAgent._is_generic_subject(resolved["subject"])):
                        resolved["subject"] = sug_subj

            # Set smart subject if not provided or generic
            if not resolved.get("subject") or (parent_nodes and EmailAgent._is_generic_subject(resolved["subject"])):
                if resolved.get("source_report_name"):
                    resolved["subject"] = f"Executive Report: {resolved['source_report_name']}"
                elif resolved.get("title"):
                    resolved["subject"] = f"Executive Briefing: {resolved['title']}"
                else:
                    resolved["subject"] = f"Workflow Execution Update: {node.name if node else 'Pipeline'}"

            # Fallback smart body if still unassigned
            if not resolved.get("body") and not resolved.get("message"):
                body_parts = ["Hello,\n\nThe autonomous multi-agent workflow has executed successfully.\n"]
                if resolved.get("source_report_name"):
                    body_parts.append(f"Attached is the generated report: **{resolved['source_report_name']}**.")
                    if resolved.get("attachment_filename"):
                        body_parts.append(f"File: `{resolved['attachment_filename']}`\n")

                for p in (parent_nodes or []):
                    p_out = self.node_outputs.get(p.public_id) or self.node_outputs.get(p.name) or {}
                    if isinstance(p_out, dict):
                        p_summary = p_out.get("summary") or p_out.get("result_summary")
                        if p_summary:
                            body_parts.append(f"### {p.name} Summary:\n{p_summary}\n")

                body_parts.append("Best regards,\nOrchestrAI Enterprise Dispatcher")
                resolved["body"] = "\n".join(body_parts)

        # C. If downstream agent is DATA_ANALYSIS:
        elif downstream_agent_type in ("data_analysis", "analysis"):
            if not resolved.get("rows") and not resolved.get("data") and not resolved.get("file_id"):
                for p in (parent_nodes or []):
                    p_out = self.node_outputs.get(p.public_id) or self.node_outputs.get(p.name) or {}
                    if isinstance(p_out, dict):
                        if p_out.get("rows") and isinstance(p_out["rows"], list):
                            resolved["rows"] = p_out["rows"]
                            resolved["columns"] = p_out.get("columns", [])
                            break
                        elif p_out.get("data") and isinstance(p_out["data"], list):
                            resolved["rows"] = p_out["data"]
                            break

        return resolved


class ExecutionResult:
    """Standardized result of an agent or task execution, supporting human-in-the-loop approvals."""

    def __init__(
        self,
        success: bool,
        output: Dict[str, Any] | None = None,
        error: Optional[str] = None,
        requires_approval: bool = False,
        approval_details: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.output = output or {}
        self.error = error
        self.requires_approval = requires_approval
        self.approval_details = approval_details or {}
        self.artifacts = artifacts or []
        self.metadata = metadata or {}

    def __iter__(self):
        """Allow backward-compatible unpacking as (success, output, error)."""
        yield self.success
        yield self.output
        yield self.error

    def __getitem__(self, index):
        return (self.success, self.output, self.error)[index]

    def __repr__(self) -> str:
        return f"<ExecutionResult success={self.success} requires_approval={self.requires_approval}>"


class AgentExecutor(ABC):
    """Abstract interface for executing an Agent task."""

    @abstractmethod
    def execute(
        self, agent: Optional[Agent], instructions: str, inputs: Dict[str, Any], config: Dict[str, Any]
    ) -> ExecutionResult:
        """Run an agent task.

        Returns:
            ExecutionResult: Standardized execution result with approval awareness.
        """
        pass


class MockLocalAgentExecutor(AgentExecutor):
    """Deterministic local mock executor for multi-agent tasks."""

    def execute(
        self,
        agent: Optional[Agent],
        instructions: str,
        inputs: Dict[str, Any],
        config: Dict[str, Any],
    ) -> ExecutionResult:
        """Simulate agent execution safely."""
        if config.get("simulate_failure", False):
            return ExecutionResult(False, {}, config.get("failure_reason", "Simulated task execution failure."))

        agent_name = agent.name if agent else "System"
        agent_type = agent.agent_type if agent else "system_action"

        result_payload = {
            "status": "success",
            "agent_name": agent_name,
            "agent_type": agent_type,
            "processed_inputs": inputs,
            "result_summary": f"Executed [{instructions or 'default action'}] successfully.",
            "simulation_only": True,
        }

        if agent_type == "email":
            result_payload["action"] = "email_drafted"
            result_payload["recipient"] = inputs.get("to", "user@example.com")
            result_payload["status"] = "drafted"
        elif agent_type == "document_research":
            result_payload["action"] = "document_summarized"
            result_payload["summary"] = "Mock document summary generated."
        elif agent_type == "report_generation":
            result_payload["action"] = "report_created"
            result_payload["report_url"] = "https://example.com/reports/mock_report.pdf"

        if "result" in config and isinstance(config["result"], dict):
            result_payload.update(config["result"])

        return ExecutionResult(True, result_payload, None)



# ---------------------------------------------------------------------------
# Process-level circuit-breaker singleton
# ---------------------------------------------------------------------------
# A single LLMResilienceManager instance is shared across all LLMAgentExecutor
# usages within one process.  This ensures that circuit-breaker failure counts
# accumulate correctly and that the OPEN/HALF_OPEN states are maintained across
# multiple workflow executions.
#
# Limitation (documented): separate Celery worker *processes* each maintain
# their own independent copy of this singleton.  Circuit-breaker state is NOT
# shared across worker processes.  This is the expected and correct behaviour
# for a process-level singleton in a distributed worker environment.  If
# cross-process state persistence is required, an external store (Redis) would
# be needed.
_SHARED_RESILIENCE_MANAGER: LLMResilienceManager = LLMResilienceManager()


class LLMAgentExecutor(AgentExecutor):
    """Production LLM-backed Agent Executor supporting multi-provider routing,
    resilience (retries/circuit breaker/fallback), usage tracking, and structured output.
    """

    def __init__(self, resilience_manager: Optional[LLMResilienceManager] = None):
        # Default to the process-level singleton so circuit-breaker state
        # persists across requests.  Pass an explicit manager to override
        # (e.g. to inject a fresh instance in isolated unit tests).
        self.resilience_manager = resilience_manager if resilience_manager is not None else _SHARED_RESILIENCE_MANAGER

    def execute(
        self,
        agent: Optional[Agent],
        instructions: str,
        inputs: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        # Fallback to specialized agent inference if no agent is explicitly attached
        if not agent:
            inferred_type = None
            text_to_check = f"{instructions} {config.get('task_name', '')} {config.get('agent_name', '')}".lower()
            if any(k in text_to_check for k in ["email", "mail", "inbox"]):
                inferred_type = "email"
            elif any(k in text_to_check for k in ["data", "analytic", "metric", "trend"]):
                inferred_type = "data_analysis"
            elif any(k in text_to_check for k in ["report", "dossier", "briefing"]):
                inferred_type = "report_generation"
            elif any(k in text_to_check for k in ["security", "vulnerability", "audit"]):
                inferred_type = "security_analysis"
            elif any(k in text_to_check for k in ["database", "sql", "query"]):
                inferred_type = "database_bi"
            elif any(k in text_to_check for k in ["research", "doc"]):
                inferred_type = "document_research"
            elif any(k in text_to_check for k in ["webhook", "http"]):
                inferred_type = "http_webhook"

            if inferred_type:
                from app.agents import get_agent_instance, AgentContext
                spec_agent = get_agent_instance(inferred_type)
                if spec_agent:
                    import uuid
                    task_id = str(config.get("task_execution_id") or uuid.uuid4())
                    user_id = config.get("user_id", 1)
                    ctx = AgentContext(
                        task_id=task_id,
                        user_id=user_id,
                        input_data=inputs or {},
                        instructions=instructions,
                        previous_results=[],
                        metadata=config or {},
                    )
                    res = spec_agent.execute(ctx)
                    return ExecutionResult(
                        success=res.success,
                        output=res.output or {},
                        error=res.error if not res.success else None,
                        requires_approval=bool(res.requires_approval),
                        approval_details=res.approval_details or {},
                        artifacts=res.artifacts,
                        metadata=res.metadata,
                    )

            mock = MockLocalAgentExecutor()
            return mock.execute(agent, instructions, inputs, config)

        if agent.status != AGENT_STATUS_ACTIVE:
            return False, {}, f"Agent '{agent.name}' is {agent.status} and cannot execute tasks."

        # Check agent token and cost budget constraints
        budget_error = check_agent_budget(agent)
        if budget_error:
            record_llm_usage(
                user_id=agent.user_id,
                provider=getattr(agent, "provider", "mock") or "mock",
                model=getattr(agent, "model", "mock-v1") or "mock-v1",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=0,
                agent_id=agent.id,
                workflow_id=config.get("workflow_id"),
                workflow_execution_id=config.get("workflow_execution_id"),
                task_execution_id=config.get("task_execution_id"),
                success=False,
                error_category="LLMQuotaExceededError",
            )
            return False, {}, budget_error

        # Dispatch to specialized registered BaseAgent if available (e.g. data_analysis, email, database_bi, etc.)
        agent_type = getattr(agent, "agent_type", "custom") or config.get("agent_type", "custom")
        if agent_type and agent_type not in ("custom", "coordinator"):
            from app.agents import get_agent_instance, AgentContext
            spec_agent = get_agent_instance(agent_type)
            if spec_agent:
                import uuid
                task_id = str(config.get("task_execution_id") or uuid.uuid4())
                prev_res = inputs.get("previous_results") or inputs.get("upstream_results") or []
                if isinstance(prev_res, dict):
                    prev_res_list = [v for v in prev_res.values() if isinstance(v, dict)]
                elif isinstance(prev_res, list):
                    prev_res_list = prev_res
                else:
                    prev_res_list = []

                ctx = AgentContext(
                    task_id=task_id,
                    user_id=agent.user_id,
                    input_data=inputs or {},
                    instructions=instructions or agent.system_instructions,
                    previous_results=prev_res_list,
                    metadata=config or {},
                )
                res = spec_agent.execute(ctx)
                requires_appr = bool(res.requires_approval) or (
                    bool(getattr(agent, "requires_human_approval", False)) and not config.get("approval_granted")
                )
                appr_details = res.approval_details or {}
                if requires_appr and not appr_details:
                    appr_details = {
                        "requested_action": f"Execute action for {agent.name} ({agent_type})",
                        "explanation": f"Agent '{agent.name}' requires explicit human verification before execution.",
                        "risk_level": "medium",
                    }
                return ExecutionResult(
                    success=res.success and not requires_appr,
                    output=res.output or {},
                    error=res.error if not res.success else None,
                    requires_approval=requires_appr,
                    approval_details=appr_details,
                    artifacts=res.artifacts,
                    metadata=res.metadata,
                )

        configured_prov = (os.getenv("LLM_PROVIDER") or "").strip().lower()
        use_mock = (os.getenv("USE_MOCK_LLM", "false") or "").strip().lower() in ("true", "1")
        raw_provider = config.get("provider") or getattr(agent, "provider", None)

        if (not raw_provider or raw_provider == "mock") and not use_mock and configured_prov:
            provider_name = configured_prov
        else:
            provider_name = raw_provider or configured_prov or "mock"

        raw_model = config.get("model") or getattr(agent, "model", None)
        if (not raw_model or raw_model.startswith("mock")) and not use_mock:
            if provider_name == "gemini":
                model_name = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
            elif provider_name == "openai":
                model_name = os.getenv("OPENAI_MODEL") or "gpt-4o"
            elif provider_name == "anthropic":
                model_name = os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022"
            else:
                model_name = raw_model or "default-model"
        else:
            model_name = raw_model or (os.getenv("GEMINI_MODEL") if provider_name == "gemini" else "mock-v1")

        fallback_name = config.get("fallback_provider") or getattr(agent, "fallback_provider", None)


        workflow_id = config.get("workflow_id")
        workflow_execution_id = config.get("workflow_execution_id")
        task_execution_id = config.get("task_execution_id")

        try:
            primary_provider = provider_registry.get_provider(provider_name)
            fallback_provider = provider_registry.get_provider(fallback_name) if fallback_name else None
        except LLMError as err:
            return False, {}, str(err)

        system_instr = agent.system_instructions or instructions
        user_prompt = f"Instructions: {instructions}\nInputs: {json.dumps(inputs)}" if inputs else (instructions or "Execute task.")
        messages = [LLMMessage(role="user", content=user_prompt)]

        response_format = config.get("response_format", "text")
        json_schema = config.get("json_schema")

        request_metadata = dict(agent.configuration or {})
        request_metadata.update(config or {})
        if "metadata" in config and isinstance(config["metadata"], dict):
            request_metadata.update(config["metadata"])

        llm_request = LLMRequest(
            provider=provider_name,
            model=model_name,
            system_instructions=system_instr,
            messages=messages,
            temperature=getattr(agent, "temperature", 0.7),
            max_tokens=getattr(agent, "max_tokens", 1000),
            response_format=response_format,
            json_schema=json_schema,
            metadata=request_metadata,
            user_id=agent.user_id,
            agent_id=agent.public_id,
        )

        try:
            response = self.resilience_manager.execute_with_resilience(
                primary_provider=primary_provider,
                fallback_provider=fallback_provider,
                request=llm_request,
            )
        except LLMError as exc:
            record_llm_usage(
                user_id=agent.user_id,
                provider=provider_name,
                model=model_name,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=0,
                agent_id=agent.id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                task_execution_id=task_execution_id,
                success=False,
                error_category=exc.__class__.__name__,
            )
            return False, {}, exc.message
        except Exception as exc:
            return False, {}, f"Execution error: {str(exc)}"

        output_payload: Dict[str, Any] = {}
        if response_format == "json" or json_schema:
            try:
                output_payload = parse_and_validate_json(response.text, json_schema=json_schema)
            except LLMResponseFormatError as err:
                record_llm_usage(
                    user_id=agent.user_id,
                    provider=response.provider,
                    model=response.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    duration_ms=response.request_duration_ms,
                    agent_id=agent.id,
                    workflow_id=workflow_id,
                    workflow_execution_id=workflow_execution_id,
                    task_execution_id=task_execution_id,
                    success=False,
                    error_category="LLMResponseFormatError",
                )
                return False, {}, str(err)
        else:
            if response.json_data:
                output_payload = response.json_data
            else:
                output_payload = {
                    "result": response.text,
                    "provider": response.provider,
                    "model": response.model,
                }

        record_llm_usage(
            user_id=agent.user_id,
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            duration_ms=response.request_duration_ms,
            agent_id=agent.id,
            workflow_id=workflow_id,
            workflow_execution_id=workflow_execution_id,
            task_execution_id=task_execution_id,
            success=True,
            fallback_used=response.metadata.get("fallback_used", False) if hasattr(response, "metadata") else False,
        )

        requires_appr = bool(getattr(agent, "requires_human_approval", False)) and not config.get("approval_granted")
        return ExecutionResult(
            success=not requires_appr,
            output=output_payload,
            error=None,
            requires_approval=requires_appr,
            approval_details={
                "requested_action": f"Approve LLM action ({agent.name})",
                "explanation": f"Agent '{agent.name}' requires human verification before applying outputs.",
                "risk_level": "low",
            } if requires_appr else {},
            metadata={"provider_used": response.provider, "model_used": response.model},
        )



class WorkflowExecutionEngine:
    """Core Execution Engine managing workflow state transitions and DAG task dispatch."""

    def __init__(self, agent_executor: AgentExecutor | None = None):
        self.agent_executor = agent_executor or LLMAgentExecutor()

    def run_execution(self, execution_id: int) -> WorkflowExecution:
        """Run a queued workflow execution synchronously."""
        execution = db.session.get(WorkflowExecution, execution_id)
        if not execution or execution.status != EXECUTION_STATUS_QUEUED:
            return execution

        workflow = execution.workflow

        execution.status = EXECUTION_STATUS_RUNNING
        execution.started_at = _utcnow()
        db.session.commit()
        
        emit_execution_log(execution.public_id, "execution_start", {"execution_id": execution.public_id})

        context = ExecutionContext(execution.input_data)
        nodes = {n.id: n for n in workflow.nodes}
        pub_nodes = {n.public_id: n for n in workflow.nodes}

        # Generate / record execution plan for this execution
        try:
            generate_execution_plan(workflow, execution_id=execution.id)
        except Exception:
            pass

        incoming_deps: Dict[int, List[Tuple[int, str, bool, Optional[str]]]] = {n.id: [] for n in workflow.nodes}
        for dep in workflow.dependencies:
            incoming_deps[dep.target_node_id].append((
                dep.source_node_id,
                dep.dependency_type,
                getattr(dep, "is_optional", False),
                getattr(dep, "condition", None),
            ))

        task_exec_map: Dict[int, TaskExecution] = {}
        for te in execution.task_executions:
            task_exec_map[te.workflow_node_id] = te

        for n_id, node in nodes.items():
            if n_id not in task_exec_map:
                te = TaskExecution(
                    workflow_execution_id=execution.id,
                    workflow_node_id=node.id,
                    agent_id=node.agent_id,
                    status=TASK_STATUS_PENDING,
                    attempt_number=0,
                )
                db.session.add(te)
                task_exec_map[n_id] = te
        db.session.commit()

        return self._run_dag_loop(
            execution=execution,
            workflow=workflow,
            nodes=nodes,
            pub_nodes=pub_nodes,
            incoming_deps=incoming_deps,
            task_exec_map=task_exec_map,
            context=context,
        )

    def _run_dag_loop(
        self,
        execution: WorkflowExecution,
        workflow: Workflow,
        nodes: Dict[int, WorkflowNode],
        pub_nodes: Dict[str, WorkflowNode],
        incoming_deps: Dict[int, List[Tuple[int, str, bool, Optional[str]]]],
        task_exec_map: Dict[int, TaskExecution],
        context: ExecutionContext,
    ) -> WorkflowExecution:
        """Execute workflow nodes in true dependency-aware parallel waves."""
        import concurrent.futures
        from flask import current_app

        val_result = validate_workflow_graph(workflow)
        topological_pub_ids = val_result.get("topological_order", [])
        topological_nodes = [pub_nodes[pid] for pid in topological_pub_ids if pid in pub_nodes]

        overall_failed = False
        overall_completed = sum(1 for te in task_exec_map.values() if te.status == TASK_STATUS_COMPLETED)

        app = None
        try:
            app = current_app._get_current_object()
        except Exception:
            pass

        while True:
            db.session.refresh(execution)
            if execution.status == EXECUTION_STATUS_CANCELLED:
                break

            ready_nodes: List[WorkflowNode] = []

            for node in topological_nodes:
                te = task_exec_map[node.id]
                # If already completed or skipped, skip
                if te.status in (TASK_STATUS_COMPLETED, TASK_STATUS_SKIPPED):
                    continue

                if te.status == TASK_STATUS_FAILED:
                    overall_failed = True
                    continue

                # Check if this task is paused awaiting approval
                if te.status == TASK_STATUS_BLOCKED:
                    from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
                    appr = ApprovalRequest.query.filter_by(
                        task_execution_id=te.id,
                        status=APPROVAL_STATUS_PENDING,
                    ).first()
                    if appr:
                        # Waiting for human decision
                        continue

                deps = incoming_deps[node.id]
                eval_res = self._evaluate_dependencies(deps, task_exec_map, context, nodes)
                if len(eval_res) == 4:
                    should_run, should_skip, should_block, block_reasons = eval_res
                else:
                    should_run, should_skip, should_block = eval_res[:3]
                    block_reasons = []

                if should_block:
                    if te.status != TASK_STATUS_BLOCKED:
                        te.status = TASK_STATUS_BLOCKED
                        te.completed_at = _utcnow()
                        block_msg = "; ".join(block_reasons) if block_reasons else "Blocked: upstream dependency failed or was not satisfied."
                        te.error_data = {"error": block_msg}
                        db.session.commit()
                        emit_execution_log(execution.public_id, "task_error", {
                            "task_name": node.name,
                            "error": block_msg
                        })
                    continue

                if should_skip:
                    if te.status != TASK_STATUS_SKIPPED:
                        te.status = TASK_STATUS_SKIPPED
                        te.completed_at = _utcnow()
                        db.session.commit()
                        emit_execution_log(execution.public_id, "task_skipped", {"task_name": node.name})
                    continue

                if should_run and te.status not in (TASK_STATUS_RUNNING, TASK_STATUS_COMPLETED):
                    ready_nodes.append(node)

            if not ready_nodes:
                # No more nodes ready in this wave
                break

            # Execute ready nodes: if single node or testing environment, execute sequentially in main thread
            from flask import current_app
            try:
                app_obj = current_app._get_current_object()
            except Exception:
                app_obj = None

            is_testing = bool(app_obj and app_obj.config.get("TESTING"))

            if len(ready_nodes) == 1 or is_testing:
                for node in ready_nodes:
                    te = task_exec_map[node.id]
                    deps = incoming_deps[node.id]
                    parent_nodes = [nodes[item[0]] for item in deps if item[0] in nodes]
                    emit_execution_log(execution.public_id, "task_start", {
                        "task_name": node.name,
                        "agent_type": node.agent.agent_type if node.agent else None
                    })
                    success = self._execute_task_node(node, te, context, parent_nodes=parent_nodes)
                    if te.status == TASK_STATUS_COMPLETED:
                        overall_completed += 1
                        art_list = []
                        if isinstance(te.output_data, dict):
                            if "all_artifacts" in te.output_data and isinstance(te.output_data["all_artifacts"], list):
                                art_list = te.output_data["all_artifacts"]
                            elif "artifact" in te.output_data and isinstance(te.output_data["artifact"], dict):
                                art_list = [te.output_data["artifact"]]
                        context.record_node_result(node, te.output_data, artifacts=art_list)
                        execution.context_data = dict(context.node_outputs)
                        execution.output_data = dict(context.node_outputs)
                        db.session.commit()
                        emit_execution_log(execution.public_id, "task_complete", {
                            "task_name": node.name,
                            "success": True,
                            "duration": te.duration_ms
                        })
                    elif te.status == TASK_STATUS_FAILED:
                        overall_failed = True
                        emit_execution_log(execution.public_id, "task_error", {
                            "task_name": node.name,
                            "error": te.error_data.get("error") if te.error_data else "Unknown error"
                        })
            else:

                tasks_to_run = []
                for n in ready_nodes:
                    t = task_exec_map[n.id]
                    t.status = TASK_STATUS_RUNNING
                    t.started_at = _utcnow()
                    emit_execution_log(execution.public_id, "task_start", {
                        "task_name": n.name,
                        "agent_type": n.agent.agent_type if n.agent else None
                    })
                    d = incoming_deps[n.id]
                    p = [nodes[item[0]] for item in d if item[0] in nodes]
                    resolved_inputs = context.resolve_inputs(n.input_mapping, parent_nodes=p, node=n)

                    exec_config = dict(n.configuration or {})
                    exec_config["workflow_execution_id"] = t.workflow_execution_id
                    exec_config["task_execution_id"] = t.id
                    exec_config["workflow_id"] = t.workflow_execution.workflow_id if t.workflow_execution else None
                    exec_config["task_name"] = n.name
                    exec_config["agent_name"] = n.agent.name if n.agent else n.name
                    exec_config["user_id"] = t.workflow_execution.user_id if t.workflow_execution else 1

                    agent_obj = n.agent
                    instructions = n.instructions or ""
                    tasks_to_run.append((n, agent_obj, instructions, resolved_inputs, exec_config))

                db.session.commit()

                def _run_worker(args):
                    node_item, agent_obj, instrs, res_inputs, cfg = args
                    start_t = time.time()
                    try:
                        if app_obj:
                            with app_obj.app_context():
                                exec_res = self.agent_executor.execute(
                                    agent=agent_obj,
                                    instructions=instrs,
                                    inputs=res_inputs,
                                    config=cfg,
                                )
                        else:
                            exec_res = self.agent_executor.execute(
                                agent=agent_obj,
                                instructions=instrs,
                                inputs=res_inputs,
                                config=cfg,
                            )
                    except Exception as exc:
                        exec_res = ExecutionResult(False, {}, str(exc))
                    duration = int((time.time() - start_t) * 1000)
                    return node_item, res_inputs, exec_res, duration

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(ready_nodes), 5)) as pool:
                    futures = [pool.submit(_run_worker, task_args) for task_args in tasks_to_run]
                    for fut in concurrent.futures.as_completed(futures):
                        n, resolved_inputs, exec_res, duration = fut.result()
                        orig_te = task_exec_map[n.id]
                        te = db.session.get(TaskExecution, orig_te.id) or orig_te
                        te.duration_ms = duration
                        te.completed_at = _utcnow()
                        te.input_data = resolved_inputs

                        requires_appr = getattr(exec_res, "requires_approval", False)
                        if requires_appr:
                            from app.services.approval_service import create_approval_request

                            appr_details = getattr(exec_res, "approval_details", {}) or {}
                            output_data = exec_res.output if hasattr(exec_res, "output") else exec_res[1]

                            te.status = TASK_STATUS_BLOCKED
                            te.output_data = output_data or {}
                            te.error_data = {}

                            create_approval_request(
                                workflow_execution=te.workflow_execution,
                                task_execution=te,
                                requested_action=appr_details.get("requested_action", f"Approve execution of {n.name}"),
                                explanation=appr_details.get(
                                    "explanation", f"Task '{n.name}' requires human verification before side-effect execution."
                                ),
                                risk_level=appr_details.get("risk_level", "medium"),
                                input_summary=resolved_inputs,
                                proposed_output=output_data,
                                requested_by_agent_id=n.agent.id if n.agent else None,
                                assigned_approver_user_id=te.workflow_execution.user_id if te.workflow_execution else None,
                            )
                            if te.workflow_execution:
                                te.workflow_execution.status = EXECUTION_STATUS_PAUSED
                        else:
                            success = exec_res.success if hasattr(exec_res, "success") else exec_res[0]
                            output_data = exec_res.output if hasattr(exec_res, "output") else exec_res[1]
                            error_msg = exec_res.error if hasattr(exec_res, "error") else exec_res[2]

                            if success:
                                te.status = TASK_STATUS_COMPLETED
                                te.output_data = output_data or {}
                                art_list = getattr(exec_res, "artifacts", []) or []
                                if not art_list and isinstance(te.output_data, dict):
                                    if "all_artifacts" in te.output_data and isinstance(te.output_data["all_artifacts"], list):
                                        art_list = te.output_data["all_artifacts"]
                                    elif "artifact" in te.output_data and isinstance(te.output_data["artifact"], dict):
                                        art_list = [te.output_data["artifact"]]
                                context.record_node_result(n, te.output_data, artifacts=art_list)
                                execution.context_data = dict(context.node_outputs)
                                execution.output_data = dict(context.node_outputs)
                                emit_execution_log(execution.public_id, "task_complete", {
                                    "task_name": n.name,
                                    "success": True,
                                    "duration": te.duration_ms
                                })
                            else:
                                te.status = TASK_STATUS_FAILED
                                te.output_data = output_data or {}
                                te.error_data = {"error": error_msg or "Execution failed"}
                                overall_failed = True
                                if te.output_data:
                                    context.record_node_result(n, te.output_data)
                                    execution.context_data = dict(context.node_outputs)
                                    execution.output_data = dict(context.node_outputs)
                                emit_execution_log(execution.public_id, "task_error", {
                                    "task_name": n.name,
                                    "error": error_msg or "Execution failed"
                                })

                        task_exec_map[n.id] = te
                        db.session.commit()

            db.session.refresh(execution)

        # Check if any tasks are paused awaiting human approval
        from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
        pending_approvals = ApprovalRequest.query.filter_by(
            workflow_execution_id=execution.id,
            status=APPROVAL_STATUS_PENDING,
        ).all()

        if pending_approvals:
            execution.status = EXECUTION_STATUS_PAUSED
            execution.context_data = dict(context.node_outputs)
            execution.output_data = dict(context.node_outputs)
            db.session.commit()
            emit_execution_log(execution.public_id, "execution_paused", {
                "pending_approvals_count": len(pending_approvals)
            })
            return execution

        if execution.status not in (EXECUTION_STATUS_CANCELLED, EXECUTION_STATUS_PAUSED):
            execution.completed_at = _utcnow()
            execution.context_data = context.node_outputs

            all_completed = all(te.status in (TASK_STATUS_COMPLETED, TASK_STATUS_SKIPPED) for te in task_exec_map.values())
            any_failed = any(te.status in (TASK_STATUS_FAILED, TASK_STATUS_BLOCKED) for te in task_exec_map.values())

            if all_completed and not overall_failed:
                execution.status = EXECUTION_STATUS_COMPLETED
                execution.output_data = context.node_outputs
            elif overall_completed > 0 and (overall_failed or any_failed):
                execution.status = EXECUTION_STATUS_PARTIALLY_COMPLETED
                execution.failure_reason = "Workflow completed partially: one or more tasks failed or were blocked/rejected."
                execution.output_data = context.node_outputs
            else:
                execution.status = EXECUTION_STATUS_FAILED
                execution.failure_reason = "One or more tasks failed during execution."

            db.session.commit()
            emit_execution_log(execution.public_id, "execution_complete", {"status": execution.status})

        return execution

    def _evaluate_dependencies(
        self,
        deps: List[Tuple[int, str, bool, Optional[str]]],
        task_exec_map: Dict[int, TaskExecution],
        context: ExecutionContext,
        nodes_dict: Optional[Dict[int, WorkflowNode]] = None,
    ) -> Tuple[bool, bool, bool, List[str]]:
        """Evaluate if a task is (should_run, should_skip, should_block, block_reasons)."""
        if not deps:
            return True, False, False, []

        eval_ctx = {
            "node_outputs": context.node_outputs,
            "inputs": context.input_data,
            "input": context.input_data,
            "context": context.context,
        }

        has_pending = False
        mandatory_satisfied = True
        mandatory_count = 0
        block_reasons: List[str] = []

        for item in deps:
            src_id = item[0]
            dep_type = item[1]
            is_optional = item[2] if len(item) > 2 else False
            condition = item[3] if len(item) > 3 else None

            parent_node = nodes_dict.get(src_id) if nodes_dict else None
            p_name = parent_node.name if parent_node else f"Node {src_id}"

            parent_te = task_exec_map.get(src_id)
            if not parent_te or parent_te.status in (
                TASK_STATUS_PENDING,
                TASK_STATUS_RUNNING,
                TASK_STATUS_RETRYING,
            ):
                has_pending = True
                continue

            if parent_te.status == TASK_STATUS_BLOCKED:
                from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
                appr = ApprovalRequest.query.filter_by(
                    task_execution_id=parent_te.id,
                    status=APPROVAL_STATUS_PENDING,
                ).first()
                if appr:
                    has_pending = True
                    continue
                else:
                    if not is_optional:
                        mandatory_satisfied = False
                        p_err = (parent_te.error_data or {}).get("error") if parent_te else None
                        reason = f"Blocked: Upstream node '{p_name}' is blocked" + (f": {p_err}" if p_err else "")
                        block_reasons.append(reason)
                    continue

            # If a condition is attached, evaluate condition against execution context
            if condition:
                cond_passed = evaluate_condition(condition, eval_ctx)
                if not cond_passed:
                    if not is_optional:
                        mandatory_satisfied = False
                        block_reasons.append(f"Blocked: Condition '{condition}' evaluated to False for upstream node '{p_name}'")
                    continue

            edge_satisfied = False
            if dep_type == DEPENDENCY_TYPE_ON_SUCCESS:
                edge_satisfied = parent_te.status == TASK_STATUS_COMPLETED
            elif dep_type == DEPENDENCY_TYPE_ON_FAILURE:
                edge_satisfied = parent_te.status == TASK_STATUS_FAILED
            elif dep_type == DEPENDENCY_TYPE_ALWAYS:
                edge_satisfied = parent_te.status in (
                    TASK_STATUS_COMPLETED,
                    TASK_STATUS_FAILED,
                    TASK_STATUS_SKIPPED,
                )

            if not is_optional:
                mandatory_count += 1
                if not edge_satisfied:
                    mandatory_satisfied = False
                    p_err = (parent_te.error_data or {}).get("error") if parent_te else None
                    if parent_te.status == TASK_STATUS_FAILED:
                        reason = f"Blocked: Upstream node '{p_name}' failed" + (f": {p_err}" if p_err else "")
                    else:
                        reason = f"Blocked: Upstream dependency on '{p_name}' not satisfied (status: {parent_te.status})"
                    block_reasons.append(reason)

        if has_pending:
            return False, False, False, []

        if mandatory_satisfied:
            return True, False, False, []

        return False, False, True, block_reasons

    def _execute_task_node(
        self,
        node: WorkflowNode,
        te: TaskExecution,
        context: ExecutionContext,
        parent_nodes: Optional[List[WorkflowNode]] = None,
    ) -> bool:
        """Execute a node with retries, approval pause checks, and status updates."""
        te.status = TASK_STATUS_RUNNING
        te.started_at = _utcnow()
        db.session.commit()

        resolved_inputs = context.resolve_inputs(node.input_mapping, parent_nodes=parent_nodes, node=node)
        te.input_data = resolved_inputs

        # Explicit failure if required upstream dependencies did not produce output data
        if parent_nodes:
            missing_parents = []
            for p in parent_nodes:
                p_out = (
                    context.node_outputs.get(p.public_id)
                    or context.node_outputs.get(p.name)
                    or (context.node_outputs.get(p.output_key) if p.output_key else None)
                )
                if not p_out:
                    missing_parents.append(p.name)
            if missing_parents:
                te.status = TASK_STATUS_FAILED
                te.completed_at = _utcnow()
                err_text = f"Missing upstream result: required dependency '{missing_parents[0]}' produced no output data."
                te.error_data = {"error": err_text}
                db.session.commit()
                emit_execution_log(te.workflow_execution.public_id if te.workflow_execution else "", "task_error", {
                    "task_name": node.name,
                    "error": err_text
                })
                return False

        agent = node.agent
        max_attempts = max(1, node.retry_limit + 1)
        attempt = 0
        success = False
        error_msg = None
        output_data = {}

        start_time = time.time()

        while attempt < max_attempts:
            attempt += 1
            te.attempt_number = attempt
            if attempt > 1:
                te.status = TASK_STATUS_RETRYING
                db.session.commit()

            exec_config = dict(node.configuration or {})
            exec_config["workflow_execution_id"] = te.workflow_execution_id
            exec_config["task_execution_id"] = te.id
            exec_config["workflow_id"] = te.workflow_execution.workflow_id if te.workflow_execution else None
            exec_config["task_name"] = node.name
            exec_config["agent_name"] = node.agent.name if node.agent else node.name
            exec_config["user_id"] = te.workflow_execution.user_id if te.workflow_execution else 1

            exec_res = self.agent_executor.execute(
                agent=agent,
                instructions=node.instructions or "",
                inputs=resolved_inputs,
                config=exec_config,
            )

            # Check if this task requires human approval!
            requires_appr = getattr(exec_res, "requires_approval", False)
            if requires_appr:
                from app.services.approval_service import create_approval_request

                appr_details = getattr(exec_res, "approval_details", {}) or {}
                output_data = exec_res.output if hasattr(exec_res, "output") else exec_res[1]

                te.status = TASK_STATUS_BLOCKED
                te.output_data = output_data or {}
                te.error_data = {}

                # Create ApprovalRequest linked to WorkflowExecution & TaskExecution
                create_approval_request(
                    workflow_execution=te.workflow_execution,
                    task_execution=te,
                    requested_action=appr_details.get("requested_action", f"Approve execution of {node.name}"),
                    explanation=appr_details.get(
                        "explanation", f"Task '{node.name}' requires human verification before side-effect execution."
                    ),
                    risk_level=appr_details.get("risk_level", "medium"),
                    input_summary=resolved_inputs,
                    proposed_output=output_data,
                    requested_by_agent_id=agent.id if agent else None,
                    assigned_approver_user_id=te.workflow_execution.user_id if te.workflow_execution else None,
                )

                if te.workflow_execution:
                    te.workflow_execution.status = EXECUTION_STATUS_PAUSED
                db.session.commit()
                return False

            success = exec_res.success if hasattr(exec_res, "success") else exec_res[0]
            output_data = exec_res.output if hasattr(exec_res, "output") else exec_res[1]
            error_msg = exec_res.error if hasattr(exec_res, "error") else exec_res[2]

            if success:
                break

        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)

        te.duration_ms = duration_ms
        te.completed_at = _utcnow()

        if success:
            te.status = TASK_STATUS_COMPLETED
            te.output_data = output_data
            te.error_data = {}
        else:
            te.status = TASK_STATUS_FAILED
            te.output_data = output_data or {}
            te.error_data = {"error": error_msg or "Execution failed", "attempts": attempt}
            if te.output_data:
                context.record_node_result(node, te.output_data)

        db.session.commit()
        return success

    def resume_execution_after_approval(
        self, execution_id: int, task_execution_id: int, approval: Any
    ) -> WorkflowExecution:
        """Resume a paused workflow execution after an approval request was approved."""
        execution = db.session.get(WorkflowExecution, execution_id)
        if not execution:
            raise ValueError(f"WorkflowExecution {execution_id} not found.")

        te = db.session.get(TaskExecution, task_execution_id)
        if not te:
            raise ValueError(f"TaskExecution {task_execution_id} not found.")

        # Idempotency check: if already completed or sent, don't execute again
        if te.status == TASK_STATUS_COMPLETED or (te.output_data and te.output_data.get("status") == "sent"):
            return execution

        node = te.workflow_node
        workflow = execution.workflow

        # Reconstruct execution context from prior completed nodes
        context = ExecutionContext(execution.input_data)
        for prev_te in execution.task_executions:
            if prev_te.id != te.id and prev_te.status == TASK_STATUS_COMPLETED and prev_te.workflow_node:
                if prev_te.output_data:
                    context.record_node_result(prev_te.workflow_node, prev_te.output_data)
                    if prev_te.workflow_node.output_key:
                        context.set_output(prev_te.workflow_node.output_key, prev_te.output_data)

        nodes = {n.id: n for n in workflow.nodes}
        pub_nodes = {n.public_id: n for n in workflow.nodes}
        incoming_deps = {n.id: [] for n in workflow.nodes}
        for dep in workflow.dependencies:
            incoming_deps[dep.target_node_id].append((
                dep.source_node_id,
                dep.dependency_type,
                getattr(dep, "is_optional", False),
                getattr(dep, "condition", None),
            ))

        parent_nodes = [nodes[item[0]] for item in incoming_deps[node.id] if item[0] in nodes]

        # Prepare inputs with verified approval
        resolved_inputs = context.resolve_inputs(node.input_mapping, parent_nodes=parent_nodes, node=node)
        resolved_inputs["approval_granted"] = True
        resolved_inputs["_backend_approval_verified"] = True
        if node.agent and node.agent.agent_type == "email":
            resolved_inputs["mode"] = "send"
            if te.output_data and isinstance(te.output_data, dict):
                saved_body = te.output_data.get("body")
                from app.agents.email_agent import EmailAgent
                if saved_body and not EmailAgent._is_generic_body(saved_body):
                    resolved_inputs["body"] = saved_body
                saved_subj = te.output_data.get("subject")
                if saved_subj and not EmailAgent._is_generic_subject(saved_subj):
                    resolved_inputs["subject"] = saved_subj
        elif node.agent and node.agent.agent_type == "http_webhook":
            resolved_inputs["approval_granted"] = True

        exec_config = dict(node.configuration or {})
        exec_config["workflow_execution_id"] = execution.id
        exec_config["task_execution_id"] = te.id
        exec_config["workflow_id"] = workflow.id
        exec_config["approval_id"] = approval.id if hasattr(approval, "id") else None
        exec_config["_backend_approval_verified"] = True
        exec_config["approval_granted"] = True
        exec_config["task_name"] = node.name
        exec_config["agent_name"] = node.agent.name if node.agent else node.name
        exec_config["user_id"] = execution.user_id or 1

        te.status = TASK_STATUS_RUNNING
        execution.status = EXECUTION_STATUS_RUNNING
        db.session.commit()

        start_time = time.time()
        exec_res = self.agent_executor.execute(
            agent=node.agent,
            instructions=node.instructions or "",
            inputs=resolved_inputs,
            config=exec_config,
        )

        success = exec_res.success if hasattr(exec_res, "success") else exec_res[0]
        output_data = exec_res.output if hasattr(exec_res, "output") else exec_res[1]
        error_msg = exec_res.error if hasattr(exec_res, "error") else exec_res[2]

        duration_ms = int((time.time() - start_time) * 1000)
        te.duration_ms = duration_ms
        te.completed_at = _utcnow()

        if success:
            te.status = TASK_STATUS_COMPLETED
            te.output_data = output_data
            te.error_data = {}
            context.record_node_result(node, output_data)
            execution.context_data = dict(context.node_outputs)
            execution.output_data = dict(context.node_outputs)
            emit_execution_log(execution.public_id, "task_complete", {
                "task_name": node.name,
                "success": True,
                "duration": duration_ms,
            })
        else:
            te.status = TASK_STATUS_FAILED
            te.error_data = {"error": error_msg or "Execution failed after approval"}
            emit_execution_log(execution.public_id, "task_error", {
                "task_name": node.name,
                "error": error_msg or "Execution failed after approval",
            })

        db.session.commit()

        # Now resume remaining nodes in the workflow DAG
        task_exec_map = {t.workflow_node_id: t for t in execution.task_executions}
        return self._run_dag_loop(
            execution=execution,
            workflow=workflow,
            nodes=nodes,
            pub_nodes=pub_nodes,
            incoming_deps=incoming_deps,
            task_exec_map=task_exec_map,
            context=context,
        )

    def resume_execution_after_rejection(
        self, execution_id: int, task_execution_id: int, rejection_reason: str = "Rejected by user"
    ) -> WorkflowExecution:
        """Resume a paused workflow execution after an approval request was rejected.
        
        The rejected task is marked as failed, which causes dependent nodes to be blocked
        with the rejection reason while independent parallel branches continue.
        """
        execution = db.session.get(WorkflowExecution, execution_id)
        if not execution:
            raise ValueError(f"WorkflowExecution {execution_id} not found.")

        te = db.session.get(TaskExecution, task_execution_id)
        if not te:
            raise ValueError(f"TaskExecution {task_execution_id} not found.")

        # Ensure the rejected task is marked failed
        te.status = TASK_STATUS_FAILED
        te.error_data = {"error": rejection_reason, "rejected": True}
        te.completed_at = _utcnow()
        execution.status = EXECUTION_STATUS_RUNNING
        db.session.commit()

        workflow = execution.workflow
        context = ExecutionContext(execution.input_data)
        for prev_te in execution.task_executions:
            if prev_te.id != te.id and prev_te.status == TASK_STATUS_COMPLETED and prev_te.workflow_node:
                if prev_te.output_data:
                    context.record_node_result(prev_te.workflow_node, prev_te.output_data)
                    if prev_te.workflow_node.output_key:
                        context.set_output(prev_te.workflow_node.output_key, prev_te.output_data)

        nodes = {n.id: n for n in workflow.nodes}
        pub_nodes = {n.public_id: n for n in workflow.nodes}
        incoming_deps = {n.id: [] for n in workflow.nodes}
        for dep in workflow.dependencies:
            incoming_deps[dep.target_node_id].append((
                dep.source_node_id,
                dep.dependency_type,
                getattr(dep, "is_optional", False),
                getattr(dep, "condition", None),
            ))

        task_exec_map = {t.workflow_node_id: t for t in execution.task_executions}
        return self._run_dag_loop(
            execution=execution,
            workflow=workflow,
            nodes=nodes,
            pub_nodes=pub_nodes,
            incoming_deps=incoming_deps,
            task_exec_map=task_exec_map,
            context=context,
        )


