"""The shop tool inventory: a plain JSON file you can edit by hand or through
the "Add Shop Tool" command in Fusion.

Format::

    {"tools": [{"name": "29", "type": "drill", "diameter_mm": 3.4544,
                "available": true, "category": "Number"}, ...]}
"""

import json
import os
from typing import List, Optional

from .snap import Tool

TOOL_TYPES = ("drill", "endmill")
INCH_MM = 25.4


def load(path: str) -> List[Tool]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    tools = []
    for raw in data.get("tools", []):
        tools.append(Tool(name=str(raw["name"]),
                          type=str(raw["type"]).lower(),
                          diameter_mm=float(raw["diameter_mm"]),
                          available=bool(raw.get("available", True)),
                          category=str(raw.get("category", ""))))
    return tools


def save(path: str, tools: List[Tool]) -> None:
    payload = {
        "_comment": ("Shop tool inventory used by ToolSnap. Holes snap to drills, "
                     "counterbores to endmills. Set available=false to keep a tool "
                     "in the list without using it."),
        "tools": [{"name": t.name, "type": t.type, "diameter_mm": round(t.diameter_mm, 4),
                   "available": t.available, "category": t.category} for t in tools],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    os.replace(tmp, path)


def find(tools: List[Tool], name: str, tool_type: str) -> Optional[Tool]:
    for t in tools:
        if t.type == tool_type and t.name == name:
            return t
    return None


def add_tool(tools: List[Tool], name: str, tool_type: str, diameter: float,
             unit: str = "mm", category: str = "", available: bool = True) -> List[Tool]:
    """Return a new list with the tool added (or replaced if name+type exists)."""
    tool_type = tool_type.lower()
    if tool_type not in TOOL_TYPES:
        raise ValueError(f"tool type must be one of {TOOL_TYPES}, got {tool_type!r}")
    if diameter <= 0:
        raise ValueError("diameter must be positive")
    dia_mm = diameter * INCH_MM if unit.lower() in ("in", "inch", "inches") else diameter
    name = name.strip() or default_name(dia_mm, unit)
    if not category:
        category = "Metric" if unit.lower() == "mm" else "Imperial"
    new = Tool(name=name, type=tool_type, diameter_mm=round(dia_mm, 4),
               available=available, category=category)
    out = [t for t in tools if not (t.type == tool_type and t.name == name)]
    out.append(new)
    return out


def set_available(tools: List[Tool], name: str, tool_type: str, available: bool) -> List[Tool]:
    return [Tool(t.name, t.type, t.diameter_mm, available, t.category)
            if (t.type == tool_type and t.name == name) else t for t in tools]


def default_name(dia_mm: float, unit: str) -> str:
    if unit.lower() == "mm":
        return f"{dia_mm:g} mm"
    return f'{dia_mm / INCH_MM:.4g}"'
