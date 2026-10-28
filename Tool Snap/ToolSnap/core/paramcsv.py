"""Read/write Fusion's parameter CSV (the format of the ExportedParameters tab
and of Parameters -> Import/Export in Fusion): Name, Unit, Expression, Value,
Comments, Favorite.
"""

import csv
from dataclasses import dataclass
from typing import Dict, List

COLUMNS = ["Name", "Unit", "Expression", "Value", "Comments", "Favorite"]


@dataclass
class ParamRow:
    name: str
    unit: str
    expression: str
    value: float
    comment: str = ""
    favorite: bool = False


def _truthy(s: str) -> bool:
    return str(s).strip().lower() in ("true", "1", "yes", "y")


def load(path: str) -> List[ParamRow]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for raw in reader:
            name = (raw.get("Name") or "").strip()
            if not name:
                continue
            rows.append(ParamRow(name=name,
                                 unit=(raw.get("Unit") or "mm").strip(),
                                 expression=(raw.get("Expression") or "").strip(),
                                 value=float(raw.get("Value") or 0),
                                 comment=(raw.get("Comments") or "").strip(),
                                 favorite=_truthy(raw.get("Favorite") or "")))
        return rows


def save(path: str, rows: List[ParamRow]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for r in rows:
            writer.writerow([r.name, r.unit, r.expression, f"{r.value:g}", r.comment,
                             "true" if r.favorite else "false"])


def values(rows: List[ParamRow]) -> Dict[str, float]:
    return {r.name: r.value for r in rows}
