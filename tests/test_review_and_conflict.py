"""
Tests for Quality Control Reviews and Conflict Resolution.
"""

from app.services.conflict_service import detect_and_resolve_conflict
from app.services.quality_service import evaluate_task_output


def test_quality_service_evaluation(app):
    """Test task output schema evaluation."""
    with app.app_context():
        outcome = evaluate_task_output(
            orchestration_id=1,
            task_id=1,
            output_data={"summary": "Detailed summary"},
            expected_output_schema={"required": ["summary"]},
        )
        assert outcome.outcome == "Approved"
        assert outcome.confidence_score == 1.0


def test_conflict_resolution_service(app):
    """Test detecting and resolving agent output conflicts."""
    with app.app_context():
        outputs = {
            1: {"prediction": "increase"},
            2: {"prediction": "decrease"},
        }
        record = detect_and_resolve_conflict(orchestration_id=1, task_id=1, agent_outputs=outputs)
        assert record.id is not None
        assert record.resolution_strategy == "adjudicator_agent"
