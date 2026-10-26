"""
Safe Condition Evaluator Service.

Provides secure AST-based expression evaluation for conditional workflow dependencies.
Never uses raw eval() or exec().
"""

import ast
from typing import Any, Dict, Optional, Set


class ConditionEvaluationError(Exception):
    """Raised when evaluation fails or expression contains forbidden constructs."""
    pass


ALLOWED_AST_NODES: Set[type] = {
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Subscript,
    ast.Attribute,
    ast.List,
    ast.Dict,
    ast.Tuple,
    ast.Slice,
}


def _validate_ast_node(node: ast.AST) -> None:
    """Recursively validate that AST only contains allowed nodes and safe attributes."""
    if type(node) not in ALLOWED_AST_NODES:
        raise ConditionEvaluationError(
            f"Forbidden construct '{type(node).__name__}' in condition expression."
        )

    if isinstance(node, ast.Attribute):
        if node.attr.startswith("__"):
            raise ConditionEvaluationError(f"Forbidden dunder attribute access '{node.attr}'.")
    elif isinstance(node, ast.Name):
        if node.id.startswith("__"):
            raise ConditionEvaluationError(f"Forbidden identifier '{node.id}'.")

    for child in ast.iter_child_nodes(node):
        _validate_ast_node(child)


def validate_condition_syntax(condition_str: str) -> bool:
    """Validate whether condition string is syntactically valid and safe AST."""
    if not condition_str or not condition_str.strip():
        return True
    try:
        parsed = ast.parse(condition_str.strip(), mode="eval")
        _validate_ast_node(parsed)
        return True
    except (SyntaxError, ConditionEvaluationError):
        return False


class SafeASTEvaluator:
    """Evaluates validated AST expressions against context dictionary."""

    def __init__(self, context: Dict[str, Any]):
        self.context = context or {}

    def eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.eval_node(node.body)

        elif isinstance(node, ast.Constant):
            return node.value

        elif isinstance(node, ast.Name):
            if node.id == "True":
                return True
            elif node.id == "False":
                return False
            elif node.id == "None":
                return None
            if node.id in self.context:
                return self.context[node.id]
            # Fallback for common alias
            return None

        elif isinstance(node, ast.UnaryOp):
            val = self.eval_node(node.operand)
            if isinstance(node.op, ast.Not):
                return not val
            elif isinstance(node.op, ast.USub):
                return -val
            elif isinstance(node.op, ast.UAdd):
                return +val

        elif isinstance(node, ast.BinOp):
            left = self.eval_node(node.left)
            right = self.eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right if right != 0 else 0
            elif isinstance(node.op, ast.Mod):
                return left % right if right != 0 else 0

        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for val_node in node.values:
                    if not self.eval_node(val_node):
                        return False
                return True
            elif isinstance(node.op, ast.Or):
                for val_node in node.values:
                    if self.eval_node(val_node):
                        return True
                return False

        elif isinstance(node, ast.Compare):
            left = self.eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.eval_node(comparator)
                if isinstance(op, ast.Eq) and not (left == right):
                    return False
                elif isinstance(op, ast.NotEq) and not (left != right):
                    return False
                elif isinstance(op, ast.Lt) and not (left < right):
                    return False
                elif isinstance(op, ast.LtE) and not (left <= right):
                    return False
                elif isinstance(op, ast.Gt) and not (left > right):
                    return False
                elif isinstance(op, ast.GtE) and not (left >= right):
                    return False
                elif isinstance(op, ast.In) and not (left in right if right is not None else False):
                    return False
                elif isinstance(op, ast.NotIn) and not (left not in right if right is not None else True):
                    return False
                elif isinstance(op, ast.Is) and not (left is right):
                    return False
                elif isinstance(op, ast.IsNot) and not (left is not right):
                    return False
                left = right
            return True

        elif isinstance(node, ast.Subscript):
            val = self.eval_node(node.value)
            key = self.eval_node(node.slice)
            if isinstance(val, (dict, list, tuple)) and key is not None:
                try:
                    return val[key]
                except (KeyError, IndexError, TypeError):
                    return None
            return None

        elif isinstance(node, ast.Attribute):
            val = self.eval_node(node.value)
            if isinstance(val, dict):
                return val.get(node.attr)
            elif hasattr(val, node.attr):
                return getattr(val, node.attr)
            return None

        elif isinstance(node, ast.List):
            return [self.eval_node(elt) for elt in node.elts]

        elif isinstance(node, ast.Dict):
            return {
                self.eval_node(k): self.eval_node(v)
                for k, v in zip(node.keys, node.values)
                if k is not None
            }

        elif isinstance(node, ast.Tuple):
            return tuple(self.eval_node(elt) for elt in node.elts)

        raise ConditionEvaluationError(f"Unsupported AST node: {type(node).__name__}")


def evaluate_condition(condition_str: Optional[str], context: Dict[str, Any]) -> bool:
    """Evaluate a conditional expression safely against context.
    
    If condition_str is None or empty, returns True.
    """
    if not condition_str or not condition_str.strip():
        return True

    clean_str = condition_str.strip()
    try:
        parsed = ast.parse(clean_str, mode="eval")
        _validate_ast_node(parsed)
        evaluator = SafeASTEvaluator(context)
        res = evaluator.eval_node(parsed)
        return bool(res)
    except Exception as exc:
        # Failed conditions evaluate to False safely rather than crashing execution
        return False
