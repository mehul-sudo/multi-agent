"""
Execution Plan Service.

Compiles workflow DAGs into staged parallel execution plans with priority inheritance
and dependency rule definitions.
"""

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.workflow import Workflow
from app.models.workflow_execution_plan import WorkflowExecutionPlan
from app.utils.errors import ResourceNotFoundError


def generate_execution_plan(workflow: Workflow, execution_id: Optional[int] = None) -> WorkflowExecutionPlan:
    """Generate and persist a staged execution plan for a workflow definition."""
    nodes = {node.public_id: node for node in workflow.nodes}
    if not nodes:
        plan = WorkflowExecutionPlan(
            workflow_id=workflow.id,
            execution_id=execution_id,
            stages=[],
            node_priorities={},
            dependency_rules={},
            status="completed",
        )
        db.session.add(plan)
        db.session.commit()
        return plan

    # Build adjacency lists and in-degree counts
    in_degree = {n_id: 0 for n_id in nodes}
    upstream_adj = defaultdict(list)
    downstream_adj = defaultdict(list)
    dependency_rules = {}

    for dep in workflow.dependencies:
        src = dep.source_node.public_id if dep.source_node else None
        tgt = dep.target_node.public_id if dep.target_node else None

        if src and tgt and src in nodes and tgt in nodes:
            in_degree[tgt] += 1
            downstream_adj[src].append(tgt)
            upstream_adj[tgt].append(src)
            edge_key = f"{src}->{tgt}"
            dependency_rules[edge_key] = {
                "is_optional": getattr(dep, "is_optional", False),
                "condition": getattr(dep, "condition", None),
                "dependency_type": dep.dependency_type,
            }

    # Partition nodes into parallel stages using BFS level-by-level
    stages: List[List[str]] = []
    current_stage = [n_id for n_id, deg in in_degree.items() if deg == 0]

    processed_count = 0
    remaining_in_degree = dict(in_degree)

    while current_stage:
        # Sort stage nodes deterministically by priority (descending) then name
        current_stage.sort(
            key=lambda nid: (nodes[nid].priority if nodes.get(nid) else 0, nid),
            reverse=True,
        )
        stages.append(current_stage)
        processed_count += len(current_stage)

        next_stage = []
        for src in current_stage:
            for tgt in downstream_adj[src]:
                remaining_in_degree[tgt] -= 1
                if remaining_in_degree[tgt] == 0:
                    next_stage.append(tgt)

        current_stage = next_stage

    # Check for unreached nodes (e.g. cycle residue or unreachable)
    if processed_count < len(nodes):
        unreached = [nid for nid in nodes if nid not in [n for stage in stages for n in stage]]
        if unreached:
            stages.append(unreached)

    # Compute node priorities with priority inheritance
    node_priorities: Dict[str, int] = {}
    wf_priority = getattr(workflow, "priority", 1) or 1

    for stage in stages:
        for nid in stage:
            node_base_priority = nodes[nid].priority if nid in nodes else 0
            # Parent inherited max priority
            parent_max = 0
            if upstream_adj[nid]:
                parent_max = max(node_priorities.get(p, 0) for p in upstream_adj[nid])
            node_priorities[nid] = wf_priority + node_base_priority + parent_max

    plan = WorkflowExecutionPlan(
        workflow_id=workflow.id,
        execution_id=execution_id,
        stages=stages,
        node_priorities=node_priorities,
        dependency_rules=dependency_rules,
        status="generated",
    )

    db.session.add(plan)
    db.session.commit()
    return plan


def get_execution_plan_for_workflow(workflow_public_id: str, user_id: int) -> Optional[WorkflowExecutionPlan]:
    """Retrieve the latest execution plan for a workflow owned by user."""
    wf = Workflow.query.filter_by(public_id=workflow_public_id, user_id=user_id).first()
    if not wf:
        raise ResourceNotFoundError(f"Workflow '{workflow_public_id}' not found or access denied.")

    return WorkflowExecutionPlan.query.filter_by(workflow_id=wf.id).order_by(WorkflowExecutionPlan.created_at.desc()).first()
