"""A tiny, safe evaluator for Fusion-style parameter expressions.

Inside Fusion the add-in hands expressions to ``design.unitsManager`` and
this module is not used.  Outside Fusion (tests, the ``snap_report`` CLI) we
need to evaluate things like ``m3_socket_head_OD + 2 * counterbore_radial_clearance``
against a dict of parameter values, so this does just arithmetic, names, and
an optional trailing unit (``mm``) - nothing else.
"""

import ast
import operator
from typing import Dict

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_UNIT_SCALE = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}


class ExpressionError(ValueError):
    pass


def evaluate(expression: str, params: Dict[str, float]) -> float:
    """Evaluate ``expression`` (result in mm) with every name taken from ``params``."""
    src = expression.strip()
    scale = 1.0
    for unit, factor in _UNIT_SCALE.items():
        if src.endswith(" " + unit):
            src, scale = src[:-len(unit) - 1], factor
            break
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"cannot parse {expression!r}: {exc.msg}") from None
    return _eval(tree.body, params, expression) * scale


def _eval(node, params, expression):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        try:
            return float(params[node.id])
        except KeyError:
            raise ExpressionError(f"unknown parameter {node.id!r} in {expression!r}") from None
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left, params, expression),
                                   _eval(node.right, params, expression))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand, params, expression))
    raise ExpressionError(f"unsupported syntax in {expression!r}")
