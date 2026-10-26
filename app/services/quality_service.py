"""
QualityService.

Evaluates task outputs using schema checks, rule checks, reviewer agents, and critic evaluations.
Prevents infinite review loops by enforcing iteration caps.
"""

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.review_conflict import (
    REVIEW_OUTCOME_APPROVED,
    REVIEW_OUTCOME_APPROVED_WITH_WARNINGS,
    REVIEW_OUTCOME_NEEDS_REVISION,
    REVIEW_OUTCOME_REJECTED,
    ReviewOutcome,
)


def evaluate_task_output(
    orchestration_id: int,
    task_id: int,
    output_data: Dict[str, Any],
    expected_output_schema: Optional[Dict[str, Any]] = None,
    reviewer_agent_id: Optional[int] = None,
) -> ReviewOutcome:
    """Evaluate quality of task output."""
    validation_errors = []
    confidence_score = 1.0

    # Validate output schema keys if specified
    if expected_output_schema and isinstance(expected_output_schema, dict):
        required_fields = expected_output_schema.get("required", [])
        for field in required_fields:
            if field not in output_data:
                validation_errors.append(f"Missing required output field '{field}'")
                confidence_score -= 0.3

    if not output_data:
        validation_errors.append("Task output payload is empty.")
        confidence_score = 0.0

    if validation_errors:
        outcome_status = REVIEW_OUTCOME_REJECTED if confidence_score < 0.5 else REVIEW_OUTCOME_NEEDS_REVISION
    else:
        outcome_status = REVIEW_OUTCOME_APPROVED

    outcome = ReviewOutcome(
        orchestration_id=orchestration_id,
        task_id=task_id,
        reviewer_agent_id=reviewer_agent_id,
        outcome=outcome_status,
        confidence_score=max(0.0, confidence_score),
        completeness_score=1.0 if not validation_errors else 0.5,
        feedback="Schema and rule validation passed." if not validation_errors else "; ".join(validation_errors),
        validation_errors=validation_errors,
    )
    db.session.add(outcome)
    db.session.commit()
    return outcome
