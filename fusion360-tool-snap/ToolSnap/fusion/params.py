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
    """Return a function that evaluates a Fusion expression to mm."""
    um = design.unitsManager

    def evaluate(expression: str) -> float:
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
           comment: Optional[str] = None, favorite: Optional[bool] = None) -> adsk.fusion.UserParameter:
    """Write a hard value (in mm) to a user parameter, creating it if needed."""
    expression = f"{value_mm:.4f} mm"
    p = design.userParameters.itemByName(name)
    if p:
        if p.expression != expression:
            p.expression = expression
    else:
        p = design.userParameters.add(name, adsk.core.ValueInput.createByString(expression),
                                      "mm", comment or "")
    if comment is not None and p.comment != comment:
        p.comment = comment
    if favorite is not None and p.isFavorite != favorite:
        p.isFavorite = favorite
    return p


def import_rows(design: adsk.fusion.Design, rows: List[ParamRow],
                overwrite_values: bool = False) -> Dict[str, int]:
    """Create/refresh user parameters from a Fusion parameter CSV.

    Two passes so expressions may reference parameters defined later in the
    file: first every parameter exists with its literal value, then the
    expressions are applied.  Existing literal values are left alone unless
    ``overwrite_values`` is set; expressions are always brought in line.
    """
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    for r in rows:
        p = design.userParameters.itemByName(r.name)
        literal = f"{r.value:g} {r.unit}"
        if not p:
            design.userParameters.add(r.name, adsk.core.ValueInput.createByString(literal),
                                      r.unit, r.comment)
            stats["created"] += 1
        elif overwrite_values and not r.expression and p.expression != literal:
            p.expression = literal
            stats["updated"] += 1
        else:
            stats["unchanged"] += 1
    for r in rows:
        p = design.userParameters.itemByName(r.name)
        if r.expression and p.expression != r.expression:
            p.expression = r.expression
            stats["updated"] += 1
            stats["unchanged"] = max(0, stats["unchanged"] - 1)
        if r.comment and p.comment != r.comment:
            p.comment = r.comment
        if p.isFavorite != r.favorite:
            p.isFavorite = r.favorite
    return stats
