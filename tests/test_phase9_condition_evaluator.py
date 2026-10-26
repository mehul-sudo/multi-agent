"""
Phase 9 Tests — Safe AST Condition Evaluator.
"""

import pytest
from app.services.condition_evaluator import (
    ConditionEvaluationError,
    evaluate_condition,
    validate_condition_syntax,
)


def test_validate_condition_syntax_valid():
    assert validate_condition_syntax("inputs['count'] > 5") is True
    assert validate_condition_syntax("node_outputs['fetch']['status'] == 'completed'") is True
    assert validate_condition_syntax("context.flag == True and 10 + 2 == 12") is True
    assert validate_condition_syntax("") is True
    assert validate_condition_syntax(None) is True


def test_validate_condition_syntax_forbidden():
    # Function calls forbidden
    assert validate_condition_syntax("__import__('os').system('ls')") is False
    assert validate_condition_syntax("eval('1+1')") is False
    # Dunder attributes forbidden
    assert validate_condition_syntax("inputs.__class__") is False


def test_evaluate_condition_basic():
    ctx = {
        "inputs": {"count": 10, "flag": True},
        "node_outputs": {"fetch": {"status": "completed", "total": 100}},
    }
    assert evaluate_condition("inputs['count'] > 5", ctx) is True
    assert evaluate_condition("inputs['count'] < 5", ctx) is False
    assert evaluate_condition("node_outputs['fetch']['status'] == 'completed'", ctx) is True
    assert evaluate_condition("node_outputs['fetch']['total'] >= 100", ctx) is True
    assert evaluate_condition("inputs['flag'] == True and node_outputs['fetch']['total'] > 50", ctx) is True


def test_evaluate_condition_missing_keys_safe():
    ctx = {"inputs": {}}
    # Missing keys evaluate safely to False instead of throwing exceptions
    assert evaluate_condition("inputs['missing_key'] == 'value'", ctx) is False
    assert evaluate_condition("node_outputs['unknown']['field'] > 0", ctx) is False


def test_evaluate_condition_math_and_logic():
    ctx = {"x": 10, "y": 20}
    assert evaluate_condition("x + y == 30", ctx) is True
    assert evaluate_condition("x * 2 == y", ctx) is True
    assert evaluate_condition("x in [5, 10, 15]", ctx) is True
    assert evaluate_condition("y not in [5, 10, 15]", ctx) is True
