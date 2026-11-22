"""Read and write Fusion user parameters.

Fusion keeps lengths internally in cm, so every value crossing this boundary
is converted through the design's UnitsManager and the rest of the add-in only
ever sees millimetres.
"""

from typing import Callable, Dict, List, Optional

import adsk.core
import adsk.fusion

from ..core.paramcsv import ParamRow


def evaluator(design: adsk.fusion.Design) -> Callable[[str], float]:
    """Return a function that evaluates a Fusion expression to mm.

    evaluateExpression does not raise on a bad expression - it returns -1 and
    sets the API's last error - so validate first and raise ourselves.
    """
    um = design.unitsManager

    def evaluate(expression: str) -> float:
        if not um.isValidExpression(expression, "mm"):
            raise ValueError(f"cannot evaluate '{expression}' (missing parameter?)")
        internal = um.evaluateExpression(expression, "mm")
        return um.convert(internal, um.internalUnits, "mm")
    return evaluate


def get_mm(design: adsk.fusion.Design, name: str) -> Optional[float]:
    p = design.userParameters.itemByName(name)
    if not p:
        return None
    um = design.unitsManager
    return um.convert(p.value, um.internalUnits, "mm")


def set_mm(design: adsk.fusion.Design, name: str, value_mm: float,
           comment: Optional[str] = None, favorite_if_new: bool = False) -> adsk.fusion.UserParameter:
    """Write a hard value (in mm) to a user parameter, creating it if needed.

    The Favorite flag is only set when the parameter is created; an existing
    parameter keeps whatever the user chose in Change Parameters.
    """
    expression = f"{value_mm:.4f} mm"
    p = design.userParameters.itemByName(name)
    if p:
        if not _same_expression(p.expression, expression):
            p.expression = expression
    else:
        p = design.userParameters.add(name, adsk.core.ValueInput.createByString(expression),
                                      "mm", comment or "")
        if favorite_if_new:
            p.isFavorite = True
    if comment is not None:
        _set_comment(p, comment)
    return p


def _set_comment(p, comment: str) -> None:
    # Comment is settable on user parameters in practice, but the reference
    # does not promise it; never let a cosmetic write fail the command.
    try:
        if p.comment != comment:
            p.comment = comment
    except Exception:  # noqa: BLE001
        pass


def _same_expression(a: str, b: str) -> bool:
    return a.replace(" ", "") == b.replace(" ", "")


def import_rows(design: adsk.fusion.Design, rows: List[ParamRow],
                overwrite_values: bool = False) -> Dict[str, int]:
    """Create/refresh user parameters from a Fusion parameter CSV.

    Two passes so expressions may reference parameters defined later in the
    file: first every parameter exists with its literal value, then the
    expressions are applied.  A missing parameter is created exactly as the
    file describes it.  For an existing one, literal values are left alone
    unless ``overwrite_values`` is set, expressions are brought in line, and
    the Favorite flag is never touched.
    """
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    created = set()
    for r in rows:
        p = design.userParameters.itemByName(r.name)
        literal = f"{r.value:g} {r.unit}"
        if not p:
            p = design.userParameters.add(r.name, adsk.core.ValueInput.createByString(literal),
                                          r.unit, r.comment)
            if r.favorite:
                p.isFavorite = True
            created.add(r.name)
            stats["created"] += 1
        elif overwrite_values and not r.expression and not _same_expression(p.expression, literal):
            p.expression = literal
            stats["updated"] += 1
        else:
            stats["unchanged"] += 1
    for r in rows:
        p = design.userParameters.itemByName(r.name)
        if r.expression and not _same_expression(p.expression, r.expression):
            p.expression = r.expression
            stats["updated"] += 1
            stats["unchanged"] = max(0, stats["unchanged"] - 1)
        if r.comment and r.name in created:
            _set_comment(p, r.comment)
    return stats


def remove_if_unused(design: adsk.fusion.Design, name: str) -> bool:
    """Delete a user parameter nothing depends on (used to retire legacy names)."""
    p = design.userParameters.itemByName(name)
    if not p:
        return False
    try:
        if p.dependentParameters.count:
            return False
        return bool(p.deleteMe())
    except Exception:  # noqa: BLE001 - never let cleanup break a write
        return False
