"""
Workflow Graph Validation Service.

Validates the directed acyclic graph (DAG) structure of a workflow before activation/execution.
Checks for cycles, self-dependencies, duplicate edges, unreachable nodes, missing agent references,
invalid timeout/retry limits, and invalid output keys.
"""

from collections import deque
from typing import Any, Dict, List, Set, Tuple

from app.models.agent import AGENT_STATUS_ACTIVE, Agent
from app.models.workflow import Workflow
from app.models.workflow_dependency import SUPPORTED_DEPENDENCY_TYPES, WorkflowDependency
from app.models.workflow_node import WorkflowNode
from app.services.condition_evaluator import validate_condition_syntax


def validate_workflow_graph(workflow: Workflow) -> Dict[str, Any]:
    """Validate a Workflow object's nodes and dependencies.

    Args:
        workflow: The Workflow model instance (with loaded nodes and dependencies).

    Returns:
        Structured dict containing:
          - valid: bool
          - errors: list[dict]
          - warnings: list[dict]
          - topological_order: list[str] (node public_ids)
          - graph_statistics: dict
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    nodes = list(workflow.nodes)
    dependencies = list(workflow.dependencies)

    node_map: Dict[int, WorkflowNode] = {n.id: n for n in nodes}
    public_id_map: Dict[int, str] = {n.id: n.public_id for n in nodes}

    # Graph statistics
    total_nodes = len(nodes)
    total_dependencies = len(dependencies)

    if total_nodes == 0:
        errors.append({
            "code": "EMPTY_WORKFLOW",
            "message": "Workflow contains no nodes.",
            "severity": "ERROR",
        })
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "topological_order": [],
            "graph_statistics": {
                "total_nodes": 0,
                "total_dependencies": 0,
                "max_depth": 0,
            },
        }

    # 1. Node & Agent configuration validation
    referenced_agent_ids = {n.agent_id for n in nodes if n.agent_id is not None}
    active_agent_ids: Set[int] = set()
    if referenced_agent_ids:
        active_agents = Agent.query.filter(
            Agent.id.in_(referenced_agent_ids),
            Agent.status == AGENT_STATUS_ACTIVE,
        ).all()
        active_agent_ids = {a.id for a in active_agents}

    output_keys_seen: Set[str] = set()

    for node in nodes:
        node_pub_id = node.public_id

        # Validate agent assignment
        if node.agent_id is not None:
            if node.agent_id not in active_agent_ids:
                errors.append({
                    "code": "INVALID_OR_INACTIVE_AGENT",
                    "message": f"Node '{node.name}' references an invalid, disabled, or archived agent.",
                    "node_id": node_pub_id,
                    "severity": "ERROR",
                })
        elif node.task_type == "agent_task":
            warnings.append({
                "code": "UNASSIGNED_AGENT",
                "message": f"Agent task node '{node.name}' has no agent assigned.",
                "node_id": node_pub_id,
                "severity": "WARNING",
            })

        # Validate timeout
        if node.timeout_seconds <= 0 or node.timeout_seconds > 86400:
            errors.append({
                "code": "INVALID_TIMEOUT",
                "message": f"Node '{node.name}' timeout must be between 1 and 86400 seconds.",
                "node_id": node_pub_id,
                "severity": "ERROR",
            })

        # Validate retry_limit
        if node.retry_limit < 0 or node.retry_limit > 20:
            errors.append({
                "code": "INVALID_RETRY_LIMIT",
                "message": f"Node '{node.name}' retry limit must be between 0 and 20.",
                "node_id": node_pub_id,
                "severity": "ERROR",
            })

        # Validate output_key
        if node.output_key:
            stripped_key = node.output_key.strip()
            if not stripped_key or " " in stripped_key:
                errors.append({
                    "code": "INVALID_OUTPUT_KEY",
                    "message": f"Node '{node.name}' output_key must not contain spaces or be blank.",
                    "node_id": node_pub_id,
                    "severity": "ERROR",
                })
            elif stripped_key in output_keys_seen:
                warnings.append({
                    "code": "DUPLICATE_OUTPUT_KEY",
                    "message": f"Output key '{stripped_key}' is defined by multiple nodes.",
                    "node_id": node_pub_id,
                    "severity": "WARNING",
                })
            output_keys_seen.add(stripped_key)

    # 2. Dependency Edge Validation
    adj_list: Dict[int, List[int]] = {n.id: [] for n in nodes}
    in_degree: Dict[int, int] = {n.id: 0 for n in nodes}
    seen_edges: Set[Tuple[int, int]] = set()

    for dep in dependencies:
        dep_pub_id = dep.public_id
        src = dep.source_node_id
        tgt = dep.target_node_id

        # Check node existence in workflow
        if src not in node_map or tgt not in node_map:
            errors.append({
                "code": "INVALID_DEPENDENCY_NODE",
                "message": f"Dependency {dep_pub_id} references a node that does not belong to this workflow.",
                "dependency_id": dep_pub_id,
                "severity": "ERROR",
            })
            continue

        # Check self loop
        if src == tgt:
            errors.append({
                "code": "SELF_DEPENDENCY",
                "message": f"Node '{node_map[src].name}' cannot depend on itself.",
                "dependency_id": dep_pub_id,
                "node_id": public_id_map[src],
                "severity": "ERROR",
            })
            continue

        # Check duplicate edge
        edge = (src, tgt)
        if edge in seen_edges:
            errors.append({
                "code": "DUPLICATE_DEPENDENCY",
                "message": f"Duplicate dependency edge from '{node_map[src].name}' to '{node_map[tgt].name}'.",
                "dependency_id": dep_pub_id,
                "severity": "ERROR",
            })
            continue
        seen_edges.add(edge)

        # Check dependency type
        if dep.dependency_type not in SUPPORTED_DEPENDENCY_TYPES:
            errors.append({
                "code": "INVALID_DEPENDENCY_TYPE",
                "message": f"Unsupported dependency type '{dep.dependency_type}'.",
                "dependency_id": dep_pub_id,
                "severity": "ERROR",
            })
            continue

        # Check condition syntax if provided
        condition_str = getattr(dep, "condition", None)
        if condition_str and not validate_condition_syntax(condition_str):
            errors.append({
                "code": "INVALID_CONDITION_SYNTAX",
                "message": f"Invalid condition syntax in dependency edge '{condition_str}'.",
                "dependency_id": dep_pub_id,
                "severity": "ERROR",
            })
            continue

        adj_list[src].append(tgt)
        in_degree[tgt] += 1

    # 3. Detect Unreachable / Isolated Nodes (isolated in multi-node workflows)
    if total_nodes > 1:
        for node_id in node_map:
            if in_degree[node_id] == 0 and len(adj_list[node_id]) == 0:
                warnings.append({
                    "code": "ISOLATED_NODE",
                    "message": f"Node '{node_map[node_id].name}' has no incoming or outgoing dependencies.",
                    "node_id": public_id_map[node_id],
                    "severity": "WARNING",
                })

    # 4. Topological Sort & Cycle Detection using Kahn's Algorithm
    zero_in_degree_queue = deque([n_id for n_id, deg in in_degree.items() if deg == 0])

    # To respect task priorities during execution ordering, sort zero_in_degree queue by priority desc
    topological_internal: List[int] = []

    # Process nodes
    while zero_in_degree_queue:
        # Sort queue elements by priority descending
        sorted_candidates = sorted(
            zero_in_degree_queue,
            key=lambda nid: node_map[nid].priority,
            reverse=True,
        )
        current = sorted_candidates.pop(0)
        zero_in_degree_queue.remove(current)

        topological_internal.append(current)

        for neighbor in adj_list[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                zero_in_degree_queue.append(neighbor)

    # Check for Cycle
    if len(topological_internal) < total_nodes:
        cycle_node_ids = [n_id for n_id, deg in in_degree.items() if deg > 0]
        cycle_node_names = [node_map[nid].name for nid in cycle_node_ids]
        errors.append({
            "code": "WORKFLOW_CYCLE_DETECTED",
            "message": f"Workflow contains a cyclic dependency loop involving nodes: {', '.join(cycle_node_names)}.",
            "severity": "ERROR",
        })
        topological_order = []
    else:
        topological_order = [public_id_map[nid] for nid in topological_internal]

    valid = len(errors) == 0

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "topological_order": topological_order,
        "graph_statistics": {
            "total_nodes": total_nodes,
            "total_dependencies": total_dependencies,
            "max_depth": len(topological_order),
        },
    }
