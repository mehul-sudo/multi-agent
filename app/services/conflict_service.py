"""
ConflictService.

Identifies contradictory outputs between agents, compares structured claims,
records resolution strategy, and generates ConflictRecord entries.

Resolution strategies supported:
  - "majority_vote"        : Pick the output whose primitive claims are agreed on
                              by the majority of agents.
  - "highest_confidence"   : Pick the output whose embedded 'confidence' value is
                              highest; fall back to majority_vote when absent.
  - "adjudicator_agent"    : Attempt majority_vote first; if no majority can be
                              determined, fall back to highest_confidence.
                              This is the default strategy.

Confidence is calculated dynamically as the fraction of comparable primitive
keys on which a strict majority of agents agree.  It is never hardcoded.

Evidence references are always populated with the lists of agreeing and
disagreeing keys found during comparison.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.extensions import db
from app.models.review_conflict import ConflictRecord

logger = logging.getLogger(__name__)

STRATEGY_ADJUDICATOR_AGENT = "adjudicator_agent"
STRATEGY_MAJORITY_VOTE = "majority_vote"
STRATEGY_HIGHEST_CONFIDENCE = "highest_confidence"
SUPPORTED_STRATEGIES = {
    STRATEGY_ADJUDICATOR_AGENT,
    STRATEGY_MAJORITY_VOTE,
    STRATEGY_HIGHEST_CONFIDENCE,
}

# Primitive types that can be compared meaningfully for agreement/disagreement.
_PRIMITIVE_TYPES = (str, int, float, bool, type(None))


class ConflictResolutionError(RuntimeError):
    """Raised when conflict resolution cannot produce a valid decision.

    This may occur when:
    * Fewer than two agents provided valid outputs.
    * No comparable (primitive) keys exist across outputs.
    * The requested strategy cannot select a winner (e.g. perfect tie).
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_claims(output: Any) -> Dict[str, Any]:
    """Return the top-level primitive-valued key/value pairs from *output*.

    Only primitive values (str, int, float, bool, None) are included because
    nested structures cannot be compared reliably without domain-specific
    semantics.  Non-primitive values are silently excluded.

    Returns an empty dict when *output* is not a dict or has no primitive values.
    """
    if not isinstance(output, dict):
        return {}
    return {k: v for k, v in output.items() if isinstance(v, _PRIMITIVE_TYPES)}


def _analyse_claims(
    valid_outputs: Dict[int, Dict[str, Any]],
) -> Tuple[Set[str], Set[str], float]:
    """Analyse claims across all valid agent outputs.

    Returns:
        agreeing_keys   - Keys on which a strict majority of agents agree on the
                          same value.
        disagreeing_keys - Keys present in at least two outputs where at least
                           one agent disagrees with the majority.
        confidence      - Float in [0.0, 1.0].  Fraction of comparable keys on
                          which there is a strict majority consensus.
    """
    agent_ids = list(valid_outputs.keys())

    # Gather all primitive claims per agent
    per_agent_claims: Dict[int, Dict[str, Any]] = {
        aid: _extract_claims(out) for aid, out in valid_outputs.items()
    }

    # Build the union of all keys that appear in at least two agents' claims
    all_keys: Dict[str, int] = {}  # key -> how many agents have this key
    for claims in per_agent_claims.values():
        for k in claims:
            all_keys[k] = all_keys.get(k, 0) + 1
    comparable_keys = {k for k, cnt in all_keys.items() if cnt >= 2}

    if not comparable_keys:
        return set(), set(), 0.0

    agreeing_keys: Set[str] = set()
    disagreeing_keys: Set[str] = set()

    for key in comparable_keys:
        # Collect values from agents that actually have this key
        values = [
            per_agent_claims[aid][key]
            for aid in agent_ids
            if key in per_agent_claims[aid]
        ]
        if not values:
            continue

        # Check strict majority: more than half agree on the same value
        value_counts: Dict[Any, int] = {}
        for v in values:
            try:
                value_counts[v] = value_counts.get(v, 0) + 1
            except TypeError:
                value_counts[repr(v)] = value_counts.get(repr(v), 0) + 1

        majority_threshold = len(values) / 2
        majority_value, majority_count = max(value_counts.items(), key=lambda x: x[1])

        if majority_count > majority_threshold:
            agreeing_keys.add(key)
        else:
            disagreeing_keys.add(key)

    n_comparable = len(comparable_keys)
    confidence = len(agreeing_keys) / n_comparable if n_comparable > 0 else 0.0
    return agreeing_keys, disagreeing_keys, confidence


def _majority_vote_winner(
    valid_outputs: Dict[int, Dict[str, Any]],
    agreeing_keys: Set[str],
) -> Optional[int]:
    """Return the agent_id whose output agrees with the majority on the most keys.

    When two agents are tied on agreement count, the agent with the lower
    integer id wins (deterministic tiebreaker).

    Returns None only when ``valid_outputs`` is empty.
    """
    if not valid_outputs:
        return None

    per_agent_claims: Dict[int, Dict[str, Any]] = {
        aid: _extract_claims(out) for aid, out in valid_outputs.items()
    }

    # Build majority value for each agreeing key
    majority_values: Dict[str, Any] = {}
    for key in agreeing_keys:
        value_counts: Dict[Any, int] = {}
        for claims in per_agent_claims.values():
            if key in claims:
                v = claims[key]
                value_counts[v] = value_counts.get(v, 0) + 1
        if value_counts:
            majority_values[key] = max(value_counts, key=lambda x: value_counts[x])

    # Score each agent by how many agreeing keys they match
    scores: Dict[int, int] = {}
    for aid, claims in per_agent_claims.items():
        score = sum(
            1
            for k, v in majority_values.items()
            if claims.get(k) == v
        )
        scores[aid] = score

    # Sort by (score desc, agent_id asc) for deterministic tiebreaking
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return ranked[0][0] if ranked else None


def _highest_confidence_winner(
    valid_outputs: Dict[int, Dict[str, Any]],
) -> Optional[int]:
    """Return the agent_id whose output has the highest embedded 'confidence' value.

    Falls back to the agent with the lowest id when no output has a numeric
    'confidence' key (deterministic fallback).
    """
    if not valid_outputs:
        return None

    best_agent: Optional[int] = None
    best_conf: float = -1.0

    for aid, out in valid_outputs.items():
        conf = None
        if isinstance(out, dict):
            raw_conf = out.get("confidence")
            if isinstance(raw_conf, (int, float)):
                conf = float(raw_conf)

        if conf is not None and conf > best_conf:
            best_conf = conf
            best_agent = aid

    # Fallback: lowest agent id (deterministic)
    if best_agent is None:
        best_agent = min(valid_outputs.keys())

    return best_agent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_and_resolve_conflict(
    orchestration_id: int,
    task_id: Optional[int],
    agent_outputs: Dict[int, Any],  # agent_id -> output (expected dict)
    resolution_strategy: str = STRATEGY_ADJUDICATOR_AGENT,
) -> ConflictRecord:
    """Detect conflicts between multiple agent outputs and record the resolution.

    Algorithm
    ---------
    1. Filter out agents with missing or non-dict outputs.
    2. Require at least two valid outputs (raise ConflictResolutionError otherwise).
    3. Extract primitive-valued claims from each output.
    4. Compute agreeing/disagreeing keys and dynamic confidence.
    5. Select a winner according to *resolution_strategy*.
    6. Persist a ConflictRecord with populated evidence_references.

    Parameters
    ----------
    orchestration_id : int
        The ID of the orchestration session owning this conflict record.
    task_id : Optional[int]
        The task to which this conflict belongs; may be None for plan-level
        conflicts.
    agent_outputs : Dict[int, Any]
        Mapping of agent_id -> raw output.  Non-dict values are treated as
        malformed and excluded from comparison.
    resolution_strategy : str
        One of "adjudicator_agent" (default), "majority_vote",
        "highest_confidence".

    Returns
    -------
    ConflictRecord
        The persisted conflict record with final_decision populated.

    Raises
    ------
    ConflictResolutionError
        When fewer than 2 valid outputs are available, or when no resolution
        can be determined.
    ValueError
        When an unsupported resolution_strategy is supplied.
    """
    if resolution_strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(
            f"Unsupported resolution strategy '{resolution_strategy}'. "
            f"Choose from: {sorted(SUPPORTED_STRATEGIES)}"
        )

    # --- Step 1: Filter valid outputs ---
    valid_outputs: Dict[int, Any] = {}
    malformed_agents: List[int] = []
    for aid, out in agent_outputs.items():
        if out is None or not isinstance(out, dict):
            malformed_agents.append(aid)
            logger.warning(
                "Agent %d produced a non-dict or None output; excluded from conflict resolution.",
                aid,
            )
        else:
            valid_outputs[aid] = out

    if len(valid_outputs) < 2:
        raise ConflictResolutionError(
            f"Conflict resolution requires at least 2 valid agent outputs. "
            f"Received {len(valid_outputs)} valid output(s). "
            f"Malformed agents: {malformed_agents}."
        )

    # --- Step 2: Analyse claims ---
    agreeing_keys, disagreeing_keys, confidence = _analyse_claims(valid_outputs)

    logger.info(
        "Conflict analysis for orchestration=%d task=%s: "
        "%d valid agents, %d agreeing keys, %d disagreeing keys, confidence=%.3f",
        orchestration_id,
        task_id,
        len(valid_outputs),
        len(agreeing_keys),
        len(disagreeing_keys),
        confidence,
    )

    # --- Step 3: Select winner ---
    winner_agent_id: Optional[int] = None

    if resolution_strategy == STRATEGY_MAJORITY_VOTE:
        winner_agent_id = _majority_vote_winner(valid_outputs, agreeing_keys)

    elif resolution_strategy == STRATEGY_HIGHEST_CONFIDENCE:
        winner_agent_id = _highest_confidence_winner(valid_outputs)

    else:  # STRATEGY_ADJUDICATOR_AGENT (default)
        # Try majority vote first
        winner_agent_id = _majority_vote_winner(valid_outputs, agreeing_keys)
        # If no agreeing keys exist (complete disagreement), fall back to
        # highest_confidence rather than returning the lowest-id agent silently.
        if winner_agent_id is None or not agreeing_keys:
            logger.debug(
                "No majority consensus found; falling back to highest_confidence strategy."
            )
            winner_agent_id = _highest_confidence_winner(valid_outputs)

    if winner_agent_id is None:
        raise ConflictResolutionError(
            "Conflict resolution failed: could not determine a winner with strategy "
            f"'{resolution_strategy}'. Agents: {list(valid_outputs.keys())}."
        )

    final_decision = valid_outputs[winner_agent_id]

    # --- Step 4: Build evidence references ---
    evidence_references: Dict[str, Any] = {
        "winner_agent_id": winner_agent_id,
        "agreeing_keys": sorted(agreeing_keys),
        "disagreeing_keys": sorted(disagreeing_keys),
        "valid_agent_ids": sorted(valid_outputs.keys()),
        "malformed_agent_ids": sorted(malformed_agents),
        "strategy_applied": resolution_strategy,
    }

    # --- Step 5: Persist and return ---
    record = ConflictRecord(
        orchestration_id=orchestration_id,
        task_id=task_id,
        conflicting_outputs={str(aid): val for aid, val in agent_outputs.items()},
        participating_agent_ids=sorted(valid_outputs.keys()),
        evidence_references=evidence_references,
        resolution_strategy=resolution_strategy,
        final_decision=final_decision,
        decision_confidence=round(confidence, 4),
    )
    db.session.add(record)
    db.session.commit()
    return record


def detect_task_conflicts(tasks_spec: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Inspect planned task specifications for duplicate keys or structural conflicts."""
    conflicts = []
    seen_keys = set()

    for spec in tasks_spec:
        key = spec.get("task_key")
        if key:
            if key in seen_keys:
                conflicts.append({
                    "type": "duplicate_task_key",
                    "severity": "high",
                    "description": f"Duplicate task key '{key}' detected in plan.",
                    "affectedTasks": [key],
                    "resolutionRequired": True,
                })
            seen_keys.add(key)

    return {
        "hasConflict": len(conflicts) > 0,
        "conflicts": conflicts,
    }

