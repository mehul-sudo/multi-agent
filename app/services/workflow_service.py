"""
Workflow Service.

Handles business logic for creation, modification, validation, activation,
archival, and dependency management of Workflows.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.extensions import db
from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.workflow import (
    WORKFLOW_STATUS_ACTIVE,
    WORKFLOW_STATUS_ARCHIVED,
    WORKFLOW_STATUS_DISABLED,
    WORKFLOW_STATUS_DRAFT,
    Workflow,
)
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_node import WorkflowNode
from app.services.audit_service import log_audit_event
from app.services.graph_validation_service import validate_workflow_graph
from app.utils.pagination import paginate_query


def create_workflow(user_id: int, data: dict) -> Workflow:
    """Create a new draft Workflow."""
    workflow = Workflow(
        user_id=user_id,
        name=data["name"],
        description=data.get("description"),
        priority=data.get("priority", 1),
        status=WORKFLOW_STATUS_DRAFT,
        version=1,
        input_schema=data.get("input_schema", {}),
        output_schema=data.get("output_schema", {}),
        metadata_json=data.get("metadata", {}),
    )
    db.session.add(workflow)
    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_CREATED",
        resource_type="workflow",
        resource_id=workflow.public_id,
        user_id=user_id,
        event_data={"name": workflow.name},
    )

    return workflow


def get_workflow_by_public_id(public_id: str, user_id: int | None = None) -> Workflow | None:
    """Retrieve a workflow by public_id, optionally scoped by user ownership."""
    query = Workflow.query.filter_by(public_id=public_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def list_workflows(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> dict:
    """List workflows owned by a user with filtering and pagination."""
    query = Workflow.query.filter_by(user_id=user_id)

    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Workflow.status != WORKFLOW_STATUS_ARCHIVED)

    query = query.order_by(Workflow.created_at.desc())
    return paginate_query(query, page=page, page_size=page_size)


def update_workflow(workflow: Workflow, user_id: int, updates: dict) -> Workflow:
    """Update metadata for a workflow."""
    updated_any = False
    for field in ("name", "description", "priority", "input_schema", "output_schema"):
        if field in updates and updates[field] is not None:
            setattr(workflow, field, updates[field])
            updated_any = True

    if "metadata" in updates and updates["metadata"] is not None:
        workflow.metadata_json = updates["metadata"]
        updated_any = True

    if updated_any:
        workflow.version += 1
        db.session.commit()

        log_audit_event(
            event_type="WORKFLOW_UPDATED",
            resource_type="workflow",
            resource_id=workflow.public_id,
            user_id=user_id,
            event_data={"version": workflow.version},
        )

    return workflow


def archive_workflow(workflow: Workflow, user_id: int) -> Workflow:
    """Archive a workflow without deleting execution history."""
    if workflow.status != WORKFLOW_STATUS_ARCHIVED:
        workflow.status = WORKFLOW_STATUS_ARCHIVED
        db.session.commit()

        log_audit_event(
            event_type="WORKFLOW_ARCHIVED",
            resource_type="workflow",
            resource_id=workflow.public_id,
            user_id=user_id,
            event_data={"name": workflow.name},
        )

    return workflow


def delete_workflow_safely(workflow: Workflow, user_id: int, force: bool = False) -> bool:
    """Archive or delete workflow depending on whether executions exist or force is requested."""
    from app.models.approval_request import ApprovalRequest
    from app.models.async_job import AsyncWorkflowJob
    from app.models.llm_usage import LLMUsageLog
    from app.models.task_execution import TaskExecution
    from app.models.workflow_execution import WorkflowExecution
    from app.models.workflow_execution_plan import WorkflowExecutionPlan
    from app.models.workflow_policy import WorkflowPolicy
    from app.models.workflow_schedule import WorkflowSchedule

    if workflow.executions.count() > 0 and not force:
        archive_workflow(workflow, user_id)
        return False  # Archived to preserve history

    # Clean up all related child entities if force=True or workflow has no executions
    exec_ids = [e.id for e in workflow.executions]
    node_ids = [n.id for n in workflow.nodes]

    if exec_ids:
        ApprovalRequest.query.filter(ApprovalRequest.workflow_execution_id.in_(exec_ids)).delete(synchronize_session=False)
        TaskExecution.query.filter(TaskExecution.workflow_execution_id.in_(exec_ids)).delete(synchronize_session=False)
        LLMUsageLog.query.filter(LLMUsageLog.workflow_execution_id.in_(exec_ids)).delete(synchronize_session=False)
        WorkflowExecutionPlan.query.filter(WorkflowExecutionPlan.execution_id.in_(exec_ids)).delete(synchronize_session=False)
        WorkflowExecution.query.filter(WorkflowExecution.id.in_(exec_ids)).delete(synchronize_session=False)

    if node_ids:
        TaskExecution.query.filter(TaskExecution.workflow_node_id.in_(node_ids)).delete(synchronize_session=False)

    LLMUsageLog.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    WorkflowExecutionPlan.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    WorkflowDependency.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    WorkflowSchedule.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    WorkflowPolicy.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    AsyncWorkflowJob.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)
    WorkflowNode.query.filter_by(workflow_id=workflow.id).delete(synchronize_session=False)

    log_audit_event(
        event_type="WORKFLOW_DELETED",
        resource_type="workflow",
        resource_id=workflow.public_id,
        user_id=user_id,
        event_data={"name": workflow.name, "forced": force},
    )
    db.session.delete(workflow)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Node Management
# ---------------------------------------------------------------------------

def _resolve_agent_for_node(raw_aid: Any, node_name: str = "", instructions: str = "", user_id: int = 1) -> Optional[Agent]:
    """Resolve an Agent entity by public_id, internal id, agent_type, name, or keywords belonging to user_id."""
    agent = None
    if raw_aid:
        aid_str = str(raw_aid).strip()
        # 1. Match by public_id or integer id strictly belonging to user
        agent = Agent.query.filter(
            db.or_(Agent.public_id == aid_str, Agent.id == aid_str),
            Agent.user_id == user_id,
            Agent.status == AGENT_STATUS_ACTIVE,
        ).first()

        # 2. Match by agent_type (e.g. 'email', 'data_analysis') belonging to user
        if not agent:
            agent = Agent.query.filter(
                db.func.lower(Agent.agent_type) == aid_str.lower(),
                Agent.user_id == user_id,
                Agent.status == AGENT_STATUS_ACTIVE,
            ).first()

        # 3. Match by agent name belonging to user
        if not agent:
            agent = Agent.query.filter(
                db.func.lower(Agent.name) == aid_str.lower(),
                Agent.user_id == user_id,
                Agent.status == AGENT_STATUS_ACTIVE,
            ).first()

    # 4. Keyword inference from node name or instructions if agent still not resolved
    if not agent:
        haystack = f"{node_name} {instructions} {raw_aid or ''}".lower()
        type_keywords = [
            ("email", ["email", "mail", "inbox", "notify_email"]),
            ("data_analysis", ["data", "analytic", "metric", "trend", "statistics", "dataset"]),
            ("report_generation", ["report", "dossier", "briefing", "summary"]),
            ("security_analysis", ["security", "vulnerability", "audit", "scan"]),
            ("database_bi", ["database", "sql", "query", "bi"]),
            ("document_research", ["research", "document", "doc", "synthesize"]),
            ("http_webhook", ["webhook", "http", "api_call", "post_webhook"]),
        ]
        for ag_type, kw_list in type_keywords:
            if any(kw in haystack for kw in kw_list):
                agent = Agent.query.filter(
                    Agent.agent_type == ag_type,
                    Agent.user_id == user_id,
                    Agent.status == AGENT_STATUS_ACTIVE,
                ).first()
                if agent:
                    break

    return agent


def add_node_to_workflow(workflow: Workflow, user_id: int, data: dict) -> Tuple[Optional[WorkflowNode], Optional[str]]:
    """Add a node to a draft workflow.

    Returns:
        (WorkflowNode, None) on success or (None, error_message) on failure.
    """
    node_name = data.get("name", "")
    instructions = data.get("instructions", "")
    raw_aid = data.get("agent_id")
    agent = _resolve_agent_for_node(
        raw_aid=raw_aid,
        node_name=node_name,
        instructions=instructions,
        user_id=user_id,
    )
    if raw_aid and not agent:
        return None, "Referenced agent does not exist or access denied."

    agent_internal_id = agent.id if agent else None

    raw_out_key = data.get("output_key")
    if not raw_out_key or not str(raw_out_key).strip():
        import re, time
        name_slug = re.sub(r"[^a-zA-Z0-9_]", "_", node_name.strip().lower())
        raw_out_key = f"{name_slug}_{int(time.time() * 1000) % 100000}"

    node = WorkflowNode(
        workflow_id=workflow.id,
        agent_id=agent_internal_id,
        name=node_name,
        task_type=data.get("task_type", "agent_task"),
        instructions=instructions,
        input_mapping=data.get("input_mapping", {}),
        output_key=raw_out_key,
        configuration=data.get("configuration", {}),
        timeout_seconds=data.get("timeout_seconds", 300),
        retry_limit=data.get("retry_limit", 3),
        priority=data.get("priority", 0),
        position=data.get("position", {}),
    )

    workflow.version += 1
    db.session.add(node)
    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_NODE_ADDED",
        resource_type="workflow",
        resource_id=workflow.public_id,
        user_id=user_id,
        event_data={"node_name": node.name, "node_public_id": node.public_id},
    )

    return node, None


def update_workflow_node(
    workflow: Workflow, node: WorkflowNode, user_id: int, updates: dict
) -> Tuple[WorkflowNode, Optional[str]]:
    """Update fields of a workflow node."""
    if "agent_id" in updates and updates["agent_id"] is not None:
        agent = _resolve_agent_for_node(
            raw_aid=updates["agent_id"],
            node_name=updates.get("name", node.name),
            instructions=updates.get("instructions", node.instructions or ""),
            user_id=user_id,
        )
        if not agent:
            return node, "Referenced agent does not exist or access denied."
        node.agent_id = agent.id

    for field in (
        "name",
        "task_type",
        "instructions",
        "input_mapping",
        "output_key",
        "configuration",
        "timeout_seconds",
        "retry_limit",
        "priority",
        "position",
    ):
        if field in updates and updates[field] is not None:
            setattr(node, field, updates[field])

    workflow.version += 1
    db.session.commit()
    return node, None


def delete_workflow_node(workflow: Workflow, node: WorkflowNode, user_id: int) -> bool:
    """Remove a node and its attached dependencies from a workflow."""
    from app.models.task_execution import TaskExecution

    node_name = node.name
    node_pub_id = node.public_id

    # Delete task executions referencing this node to avoid SQLite foreign key constraint failures
    TaskExecution.query.filter_by(workflow_node_id=node.id).delete(synchronize_session=False)

    # Delete attached dependencies (also cascade deleted by FK constraint, but clean explicitly)
    WorkflowDependency.query.filter(
        (WorkflowDependency.source_node_id == node.id)
        | (WorkflowDependency.target_node_id == node.id)
    ).delete(synchronize_session=False)

    db.session.delete(node)
    workflow.version += 1
    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_NODE_DELETED",
        resource_type="workflow",
        resource_id=workflow.public_id,
        user_id=user_id,
        event_data={"node_name": node_name, "node_public_id": node_pub_id},
    )

    return True


# ---------------------------------------------------------------------------
# Dependency Management
# ---------------------------------------------------------------------------

def add_dependency_to_workflow(
    workflow: Workflow, user_id: int, data: dict
) -> Tuple[Optional[WorkflowDependency], Optional[str]]:
    """Add a dependency edge between two nodes in the workflow.

    Checks:
      - Both nodes exist and belong to this workflow
      - No self loop (source != target)
      - No duplicate edge
    """
    src_pub = data["source_node_id"]
    tgt_pub = data["target_node_id"]
    dep_type = data.get("dependency_type", "on_success")

    if src_pub == tgt_pub:
        return None, "Self-dependencies (node depending on itself) are strictly forbidden."

    src_node = WorkflowNode.query.filter_by(public_id=src_pub, workflow_id=workflow.id).first()
    tgt_node = WorkflowNode.query.filter_by(public_id=tgt_pub, workflow_id=workflow.id).first()

    if not src_node or not tgt_node:
        return None, "Source or target node does not exist in this workflow."

    # Check duplicate edge
    existing = WorkflowDependency.query.filter_by(
        workflow_id=workflow.id,
        source_node_id=src_node.id,
        target_node_id=tgt_node.id,
    ).first()
    if existing:
        return None, "A dependency edge already exists between these two nodes."

    dep = WorkflowDependency(
        workflow_id=workflow.id,
        source_node_id=src_node.id,
        target_node_id=tgt_node.id,
        dependency_type=dep_type,
        is_optional=data.get("is_optional", False),
        condition=data.get("condition"),
    )

    workflow.version += 1
    db.session.add(dep)
    db.session.commit()

    return dep, None


def delete_dependency_from_workflow(
    workflow: Workflow, dependency: WorkflowDependency, user_id: int
) -> bool:
    """Remove a dependency edge from a workflow."""
    db.session.delete(dependency)
    workflow.version += 1
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Validation & Activation
# ---------------------------------------------------------------------------

def validate_workflow(workflow: Workflow) -> dict:
    """Run DAG and graph validation on a workflow."""
    return validate_workflow_graph(workflow)


def activate_workflow(workflow: Workflow, user_id: int) -> Tuple[bool, dict]:
    """Validate and activate a workflow. If workflow has no nodes, auto-attach a starter node matching the workflow's intent.

    Returns:
        (True, validation_results) if valid & activated,
        (False, validation_results) if validation fails.
    """
    # If workflow is empty, auto-attach a starter agent node matching workflow intent
    if not workflow.nodes or len(workflow.nodes) == 0:
        from app.models.agent import Agent, AGENT_STATUS_ACTIVE
        wf_text = f"{workflow.name} {workflow.description or ''}".lower()
        user_agents = (
            Agent.query.filter_by(user_id=user_id, status=AGENT_STATUS_ACTIVE)
            .order_by(Agent.id.asc())
            .all()
        )
        matched_agent = None
        for a in user_agents:
            a_name = (a.name or "").lower()
            a_type = (a.agent_type or "").lower()
            if (
                ("email" in wf_text and (a_type == "email" or "email" in a_name))
                or ("report" in wf_text and (a_type == "report_generation" or "report" in a_name))
                or ("data" in wf_text and (a_type == "data_analysis" or "data" in a_name))
                or ("security" in wf_text and (a_type == "security_analysis" or "security" in a_name))
                or (("sql" in wf_text or "db" in wf_text) and (a_type == "database_bi" or "database" in a_name))
                or ("research" in wf_text and (a_type == "document_research" or "research" in a_name))
                or (("webhook" in wf_text or "http" in wf_text) and (a_type == "http_webhook" or "webhook" in a_name))
            ):
                matched_agent = a
                break

        if not matched_agent and user_agents:
            matched_agent = user_agents[0]

        if matched_agent:
            node_name = f"{matched_agent.name} Task"
            instructions = workflow.description or f"Execute automation task using {matched_agent.name}."
            add_node_to_workflow(
                workflow,
                user_id,
                {
                    "name": node_name,
                    "agent_id": matched_agent.public_id,
                    "instructions": instructions,
                    "output_key": "step_result",
                    "position": {"x": 200, "y": 150},
                },
            )

    val_result = validate_workflow_graph(workflow)
    if not val_result["valid"]:
        return False, val_result

    workflow.status = WORKFLOW_STATUS_ACTIVE
    workflow.version += 1
    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_ACTIVATED",
        resource_type="workflow",
        resource_id=workflow.public_id,
        user_id=user_id,
        event_data={"version": workflow.version},
    )

    return True, val_result


# ---------------------------------------------------------------------------
# Workflow Export / Import / Duplication (Schema 1.0)
# ---------------------------------------------------------------------------

def _sanitize_sensitive_data(obj: Any) -> Any:
    """Recursively strip secrets, credentials, tokens, and private identifiers."""
    SENSITIVE_KEYS = {
        "api_key", "apikey", "secret", "client_secret", "password",
        "token", "access_token", "refresh_token", "auth", "authorization",
        "credentials", "bearer", "private_key", "user_id", "organization_id",
        "account_id", "email_password", "smtp_password",
    }
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            k_lower = str(k).lower().replace("-", "_")
            if any(s in k_lower for s in SENSITIVE_KEYS):
                continue
            sanitized[k] = _sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(obj, list):
        return [_sanitize_sensitive_data(item) for item in obj]
    return obj


def export_workflow(workflow: Workflow) -> Dict[str, Any]:
    """Export a workflow to a sanitized, portable JSON format conforming to schema_version 1.0."""
    node_id_map = {}
    nodes_export = []
    for idx, node in enumerate(workflow.nodes, start=1):
        rel_id = f"node_{idx}"
        node_id_map[node.public_id] = rel_id
        node_id_map[str(node.id)] = rel_id

        ag_type = node.agent.agent_type if node.agent else "custom"
        ag_name = node.agent.name if node.agent else node.name

        nodes_export.append({
            "id": rel_id,
            "name": node.name,
            "agent_type": ag_type,
            "agent_name": ag_name,
            "instructions": node.instructions,
            "input_mapping": _sanitize_sensitive_data(node.input_mapping or {}),
            "output_key": node.output_key,
            "configuration": _sanitize_sensitive_data(node.configuration or {}),
            "position": node.position or {"x": 180 * idx, "y": 150},
            "priority": node.priority,
            "timeout_seconds": node.timeout_seconds,
            "retry_limit": node.retry_limit,
        })

    deps_export = []
    for dep in workflow.dependencies:
        src_pub = dep.source_node.public_id if dep.source_node else str(dep.source_node_id)
        tgt_pub = dep.target_node.public_id if dep.target_node else str(dep.target_node_id)
        src_rel = node_id_map.get(src_pub) or node_id_map.get(str(dep.source_node_id), src_pub)
        tgt_rel = node_id_map.get(tgt_pub) or node_id_map.get(str(dep.target_node_id), tgt_pub)

        deps_export.append({
            "source_node_id": src_rel,
            "target_node_id": tgt_rel,
            "dependency_type": dep.dependency_type,
            "is_optional": getattr(dep, "is_optional", False),
            "condition": getattr(dep, "condition", None),
        })

    return {
        "schema_version": "1.0",
        "name": workflow.name,
        "description": workflow.description,
        "priority": getattr(workflow, "priority", 1),
        "input_schema": _sanitize_sensitive_data(workflow.input_schema or {}),
        "output_schema": _sanitize_sensitive_data(workflow.output_schema or {}),
        "metadata": _sanitize_sensitive_data(workflow.metadata_json or {}),
        "nodes": nodes_export,
        "dependencies": deps_export,
    }


def import_workflow(user_id: int, data: Dict[str, Any]) -> Tuple[Optional[Workflow], List[str], Optional[str]]:
    """Import a portable workflow JSON into the user's account with cross-account isolation.

    Returns:
        (workflow, warnings, error_message)
    """
    if not isinstance(data, dict):
        return None, [], "Import data must be a JSON object."

    schema_version = data.get("schema_version")
    if schema_version != "1.0":
        return None, [], f"Unsupported schema version: '{schema_version}'. Expected '1.0'."

    from app.models.agent import Agent, AGENT_STATUS_ACTIVE
    user_agents = Agent.query.filter_by(user_id=user_id, status=AGENT_STATUS_ACTIVE).all()
    agent_by_type = {a.agent_type: a for a in user_agents}
    agent_by_name = {a.name.lower(): a for a in user_agents}

    wf_name = data.get("name") or "Imported Workflow"
    wf_desc = data.get("description")
    wf_priority = data.get("priority", 1)

    wf = Workflow(
        user_id=user_id,
        name=wf_name,
        description=wf_desc,
        priority=wf_priority,
        status=WORKFLOW_STATUS_DRAFT,
        version=1,
        input_schema=data.get("input_schema", {}),
        output_schema=data.get("output_schema", {}),
        metadata_json=data.get("metadata", {}),
    )
    db.session.add(wf)
    db.session.commit()

    rel_to_new_node = {}
    warnings: List[str] = []
    seen_agent_types = set()

    nodes_data = data.get("nodes", [])
    for idx, n_spec in enumerate(nodes_data, start=1):
        rel_id = n_spec.get("id") or f"node_{idx}"
        ag_type = n_spec.get("agent_type") or "custom"
        ag_name = n_spec.get("agent_name") or ""
        seen_agent_types.add(ag_type)

        target_agent = agent_by_type.get(ag_type) or agent_by_name.get(ag_name.lower())
        if not target_agent and user_agents:
            target_agent = user_agents[0]

        node = WorkflowNode(
            workflow_id=wf.id,
            agent_id=target_agent.id if target_agent else None,
            name=n_spec.get("name") or f"Step {idx}",
            task_type=n_spec.get("task_type", "agent_task"),
            instructions=n_spec.get("instructions") or "Execute task.",
            input_mapping=_sanitize_sensitive_data(n_spec.get("input_mapping", {})),
            output_key=n_spec.get("output_key"),
            configuration=_sanitize_sensitive_data(n_spec.get("configuration", {})),
            position=n_spec.get("position") or {"x": 180 * idx, "y": 150},
            priority=n_spec.get("priority", 1),
            timeout_seconds=n_spec.get("timeout_seconds", 300),
            retry_limit=n_spec.get("retry_limit", 3),
        )
        db.session.add(node)
        db.session.commit()
        rel_to_new_node[rel_id] = node
        rel_to_new_node[node.name] = node

    for dep_spec in data.get("dependencies", []):
        src_key = dep_spec.get("source_node_id")
        tgt_key = dep_spec.get("target_node_id")
        src_node = rel_to_new_node.get(src_key)
        tgt_node = rel_to_new_node.get(tgt_key)

        if src_node and tgt_node:
            dep = WorkflowDependency(
                workflow_id=wf.id,
                source_node_id=src_node.id,
                target_node_id=tgt_node.id,
                dependency_type=dep_spec.get("dependency_type", "on_success"),
                is_optional=dep_spec.get("is_optional", False),
                condition=dep_spec.get("condition"),
            )
            db.session.add(dep)

    db.session.commit()

    # Check for integration advisories
    if "email" in seen_agent_types:
        import os
        resend_key = os.getenv("RESEND_API_KEY", "")
        if not resend_key or resend_key.startswith("re_test") or "re_" not in resend_key:
            warnings.append("Workflow includes Email node: Ensure RESEND_API_KEY or verified sender domain is configured in your account settings.")

    if "database_bi" in seen_agent_types:
        warnings.append("Workflow includes Database BI node: Verify database connection permissions before executing.")

    # Validate and attempt auto-activation
    val = validate_workflow_graph(wf)
    if val["valid"]:
        wf.status = WORKFLOW_STATUS_ACTIVE
        db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_IMPORTED",
        resource_type="workflow",
        resource_id=wf.public_id,
        user_id=user_id,
        event_data={"name": wf.name, "nodes_count": len(wf.nodes)},
    )

    return wf, warnings, None


def duplicate_workflow(workflow: Workflow, user_id: int) -> Workflow:
    """Duplicate/clone an existing workflow for the user with all its nodes and dependencies."""
    clone = Workflow(
        user_id=user_id,
        name=f"Copy of {workflow.name}",
        description=workflow.description,
        priority=getattr(workflow, "priority", 1),
        status=WORKFLOW_STATUS_ACTIVE if workflow.status == WORKFLOW_STATUS_ACTIVE else WORKFLOW_STATUS_DRAFT,
        version=1,
        input_schema=dict(workflow.input_schema or {}),
        output_schema=dict(workflow.output_schema or {}),
        metadata_json=dict(workflow.metadata_json or {}),
    )
    db.session.add(clone)
    db.session.commit()

    old_to_new_node = {}
    for node in workflow.nodes:
        new_node = WorkflowNode(
            workflow_id=clone.id,
            agent_id=node.agent_id,
            name=node.name,
            task_type=node.task_type,
            instructions=node.instructions,
            input_mapping=dict(node.input_mapping or {}),
            output_key=node.output_key,
            configuration=dict(node.configuration or {}),
            position=dict(node.position or {}),
            priority=node.priority,
            timeout_seconds=node.timeout_seconds,
            retry_limit=node.retry_limit,
        )
        db.session.add(new_node)
        db.session.commit()
        old_to_new_node[node.id] = new_node

    for dep in workflow.dependencies:
        src = old_to_new_node.get(dep.source_node_id)
        tgt = old_to_new_node.get(dep.target_node_id)
        if src and tgt:
            new_dep = WorkflowDependency(
                workflow_id=clone.id,
                source_node_id=src.id,
                target_node_id=tgt.id,
                dependency_type=dep.dependency_type,
                is_optional=dep.is_optional,
                condition=dep.condition,
            )
            db.session.add(new_dep)

    db.session.commit()

    log_audit_event(
        event_type="WORKFLOW_DUPLICATED",
        resource_type="workflow",
        resource_id=clone.public_id,
        user_id=user_id,
        event_data={"original_id": workflow.public_id, "name": clone.name},
    )

    return clone
