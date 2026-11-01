"""Arithmetic evaluator that walks an AST. It does not call eval()."""

from __future__ import annotations

import ast
import math
import operator

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "abs": abs,
    "round": round,
}
_NAMES = {"pi": math.pi, "e": math.e}


class UnsafeExpressionError(ValueError):
    """The expression used syntax the calculator does not allow."""


def safe_eval(expression: str) -> int | float:
    expr = expression.strip().replace("^", "**")
    if not expr:
        raise UnsafeExpressionError("Empty expression")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Invalid expression: {expression}") from exc
    return _eval(tree.body)


def _eval(node: ast.AST) -> int | float:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS or node.keywords:
            raise UnsafeExpressionError("Only listed math functions are allowed")
        args = [_eval(arg) for arg in node.args]
        try:
            result = _FUNCS[node.func.id](*args)
        except TypeError as exc:
            raise UnsafeExpressionError(str(exc)) from exc
        return result
    raise UnsafeExpressionError(f"Unsupported syntax: {type(node).__name__}")
