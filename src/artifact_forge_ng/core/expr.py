"""A tiny, safe arithmetic expression evaluator for parametric formulas.

Feature specs may carry *formulas* instead of literal numbers — e.g. a hole
count of ``"floor(PI*OD/cell)"`` or a revolve profile of ``"30 + 8*sin(z)"``.
This is the "nodes" idea in miniature: an ``expr`` feature seeds named
variables, and any later numeric field can be an expression referencing them.

Evaluation goes through Python's ``ast`` with a strict whitelist of node types,
functions, and constants — there is no ``eval`` of arbitrary code, no attribute
access, no names beyond the supplied context and the math table below.
"""

from __future__ import annotations

import ast
import math
from typing import Any

#: Constants available in every formula.
_CONSTS: dict[str, float] = {
    "PI": math.pi, "TAU": math.tau, "E": math.e, "PHI": (1 + 5 ** 0.5) / 2,
}


def _sign(x: float) -> float:
    return (x > 0) - (x < 0)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


#: Whitelisted functions. Trig is in radians (use ``rad``/``deg`` to convert).
_FUNCS: dict[str, Any] = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "atan2": math.atan2, "hypot": math.hypot,
    "sqrt": math.sqrt, "exp": math.exp, "log": math.log, "log10": math.log10,
    "floor": math.floor, "ceil": math.ceil, "round": round, "abs": abs,
    "min": min, "max": max, "pow": pow, "fmod": math.fmod,
    "rad": math.radians, "deg": math.degrees,
    "sign": _sign, "clamp": _clamp,
}

#: AST node types the evaluator accepts. Anything else raises.
_ALLOWED = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
    ast.Constant, ast.IfExp, ast.Compare, ast.BoolOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.And, ast.Or,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)


def _eval(node: ast.AST, ctx: dict[str, float]) -> Any:
    if not isinstance(node, _ALLOWED):
        raise ValueError(f"disallowed expression element: {type(node).__name__}")
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"only numeric literals allowed, got {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id in ctx:
            return ctx[node.id]
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise ValueError(f"unknown name {node.id!r} in formula")
    if isinstance(node, ast.UnaryOp):
        x = _eval(node.operand, ctx)
        return +x if isinstance(node.op, ast.UAdd) else -x
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left, ctx), _eval(node.right, ctx)
        op = node.op
        if isinstance(op, ast.Add): return a + b
        if isinstance(op, ast.Sub): return a - b
        if isinstance(op, ast.Mult): return a * b
        if isinstance(op, ast.Div): return a / b
        if isinstance(op, ast.FloorDiv): return a // b
        if isinstance(op, ast.Mod): return a % b
        if isinstance(op, ast.Pow): return a ** b
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, ctx) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, ctx)
            ok = (isinstance(op, ast.Lt) and left < right
                  or isinstance(op, ast.LtE) and left <= right
                  or isinstance(op, ast.Gt) and left > right
                  or isinstance(op, ast.GtE) and left >= right
                  or isinstance(op, ast.Eq) and left == right
                  or isinstance(op, ast.NotEq) and left != right)
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body, ctx) if _eval(node.test, ctx) else _eval(node.orelse, ctx)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ValueError("only whitelisted functions may be called")
        args = [_eval(a, ctx) for a in node.args]
        return _FUNCS[node.func.id](*args)
    raise ValueError(f"disallowed expression element: {type(node).__name__}")


def evaluate(expr: str, ctx: dict[str, float] | None = None) -> float:
    """Evaluate an arithmetic formula string to a float against ``ctx``."""
    tree = ast.parse(expr, mode="eval")
    return float(_eval(tree, ctx or {}))


def resolve(value: Any, ctx: dict[str, float] | None = None) -> Any:
    """Resolve a value that may be a formula string, number, or list thereof."""
    if isinstance(value, str):
        return evaluate(value, ctx)
    if isinstance(value, (list, tuple)):
        return [resolve(v, ctx) for v in value]
    return value
