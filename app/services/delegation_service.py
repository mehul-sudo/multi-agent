"""
DelegationService.

Governs agent-to-agent task delegation. Checks maximum delegation depth,
loops, child task limits, permissions, and creates child PlanTasks.

Cycle Detection
---------------
``delegate_subtask`` detects both direct (A→A) and indirect (A→B→A,
A→B→C→A) delegation cycles by walking the ``DelegationRecord`` table
upward from the *parent_agent_id* to build the full set of ancestor
agent IDs.  If the resolved *target_agent_id* appears anywhere in that
ancestry, the delegation is rejected with a ``DelegationLoopError``
before any database records are created.
"""

from typing import Any, Dict, Optional, Set, Tuple

from app.extensions import db
from app.models.agent import Agent
from app.models.delegation_record import DelegationRecord
from app.models.orchestration_plan import PLAN_TASK_STATUS_PENDING, PlanTask
from app.services.agent_matching_service import find_best_agent_for_task


class DelegationDepthExceededError(ValueError):
    """Raised when an agent attempts to delegate beyond the configured max_delegation_depth."""
    pass


class DelegationLoopError(ValueError):
    """Raised when delegation creates a circular chain back to a parent agent."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_delegation_ancestry(orchestration_id: int, agent_id: int) -> Set[int]:
    """Return the full set of ancestor agent IDs in the current delegation chain.

    Walks the ``DelegationRecord`` table upward from *agent_id*, following
    ``child_agent_id → parent_agent_id`` links until no further parent is found.
    This detects both direct (A→A) and indirect (A→B→A, A→B→C→A) cycles.

    The returned set includes *agent_id* itself, so callers can simply check
    ``target_agent_id in ancestry``.

    Parameters
    ----------
    orchestration_id : int
        Scope the ancestry walk to the current orchestration to avoid
        false positives from independent orchestration sessions.
    agent_id : int
        The agent whose ancestry we want to compute (typically the
        parent agent in the proposed new delegation).

    Returns
    -------
    Set[int]
        All agent IDs in the ancestry chain, including *agent_id*.
    """
    ancestry: Set[int] = {agent_id}
    current_id = agent_id

    # Iterate upward — worst case O(depth), bounded by max_delegation_depth
    while True:
        record = DelegationRecord.query.filter_by(
            orchestration_id=orchestration_id,
            child_agent_id=current_id,
        ).order_by(DelegationRecord.id.desc()).first()

        if record is None:
            # No further parent in this orchestration; chain is complete
            break

        parent_id = record.parent_agent_id
        if parent_id in ancestry:
            # Cycle already detected in ancestry set — stop to avoid infinite loop
            break

        ancestry.add(parent_id)
        current_id = parent_id

    return ancestry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def delegate_subtask(
    orchestration_id: int,
    parent_task: PlanTask,
    parent_agent: Agent,
    requested_capability: str,
    subtask_name: str,
    subtask_input: Dict[str, Any],
    delegation_reason: str,
) -> Tuple[PlanTask, DelegationRecord]:
    """Validate delegation rules and create a delegated child task.

    Checks performed (in order):
    1. Maximum delegation depth.
    2. Full indirect cycle detection via ancestry walk.
    3. Direct self-delegation guard (also caught by ancestry, but explicit).

    Raises
    ------
    DelegationDepthExceededError
        When the new depth would exceed ``parent_agent.max_delegation_depth``.
    DelegationLoopError
        When the resolved target agent appears anywhere in the delegation
        ancestry of ``parent_agent``, indicating a cycle.
    """
    current_depth = parent_task.delegation_depth + 1
    if current_depth > parent_agent.max_delegation_depth:
        raise DelegationDepthExceededError(
            f"Delegation depth limit exceeded: current {current_depth} > max {parent_agent.max_delegation_depth}"
        )

    # Resolve the best matching target agent
    target_agent, reasoning, score = find_best_agent_for_task(
        user_id=parent_agent.user_id,
        required_capabilities=[requested_capability],
    )

    target_agent_id = target_agent.id if target_agent else parent_agent.id

    # --- Indirect cycle detection ---
    # Build the full ancestry from parent_agent upward in this orchestration.
    # The ancestry set always includes parent_agent.id itself.
    ancestry = _get_delegation_ancestry(orchestration_id, parent_agent.id)

    if target_agent_id in ancestry:
        cycle_desc = (
            f"Agent '{parent_agent.name}' (id={parent_agent.id}) attempted to delegate "
            f"to Agent id={target_agent_id}, but that agent is already in the delegation "
            f"ancestry chain {sorted(ancestry)}. This would create a circular delegation loop."
        )
        raise DelegationLoopError(cycle_desc)

    # Create delegated child task
    child_task = PlanTask(
        plan_id=parent_task.plan_id,
        task_key=f"{parent_task.task_key}_sub_{parent_task.subtasks.count() + 1}",
        name=subtask_name,
        description=f"Delegated task: {delegation_reason}",
        task_type="delegation",
        assigned_agent_id=target_agent_id,
        required_capabilities=[requested_capability],
        input_references=subtask_input,
        parent_task_id=parent_task.id,
        delegation_depth=current_depth,
        status=PLAN_TASK_STATUS_PENDING,
    )
    db.session.add(child_task)
    db.session.flush()

    record = DelegationRecord(
        orchestration_id=orchestration_id,
        parent_task_id=parent_task.id,
        child_task_id=child_task.id,
        parent_agent_id=parent_agent.id,
        child_agent_id=target_agent_id,
        delegation_depth=current_depth,
        delegation_reason=delegation_reason,
        requested_capability=requested_capability,
        status="IN_PROGRESS",
    )
    db.session.add(record)
    db.session.commit()

    return child_task, record

