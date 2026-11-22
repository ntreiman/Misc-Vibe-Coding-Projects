"""Filtering, sorting and annotation for the Shop Tools table.

Pure Python so the view logic is unit-tested; ``fusion/cmd_shop_tools.py``
only turns the result into dialog rows.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .inventory import INCH_MM, label
from .snap import Tool

UNITS = ("both", "mm", "in")
SORTS = ("dia_asc", "dia_desc", "name", "series")
SORT_LABELS = {"dia_asc": "Ø ascending", "dia_desc": "Ø descending",
               "name": "Name", "series": "Series, then Ø"}
SYSTEMS = ("all", "imperial", "metric")
AVAILABILITY = ("all", "available", "retired")
TYPE_LABEL = {"drill": "drill", "endmill": "endmill"}


def is_metric(t: Tool) -> bool:
    return t.category.lower() == "metric" or t.name.strip().lower().endswith("mm")


def series_of(t: Tool) -> str:
    """Number / Letter / Fractional / Metric / Imperial (endmills) / whatever the inventory says."""
    return t.category or ("Metric" if is_metric(t) else "Imperial")


def fmt(dia_mm: float, units: str) -> str:
    """'3.454 mm' style text for one unit."""
    if units == "in":
        return f"{dia_mm / INCH_MM:.4f}"
    return f"{dia_mm:.3f}"


def to_mm(value: Optional[float], units: str) -> Optional[float]:
    if value is None:
        return None
    return value * INCH_MM if units == "in" else value


@dataclass
class Criteria:
    tool_type: str = "all"               # all | drill | endmill
    system: str = "all"                  # all | imperial | metric
    series: Optional[Set[str]] = None    # None = any
    availability: str = "all"            # all | available | retired
    dmin_mm: Optional[float] = None
    dmax_mm: Optional[float] = None
    near_mm: Optional[float] = None      # show the closest tools around this diameter
    near_count: int = 4                  # ... this many on each side
    search: str = ""
    used_only: bool = False
    sort: str = "dia_asc"


@dataclass
class Row:
    tool: Tool
    available: bool
    series: str
    used_for: List[str] = field(default_factory=list)
    step_up_mm: Optional[float] = None     # gap to the next larger available tool of the same type
    next_up: Optional[Tool] = None


def step_table(tools: Sequence[Tool], avail: Dict[Tuple[str, str], bool]) -> Dict[Tuple[str, str], Tuple[Optional[float], Optional[Tool]]]:
    """For every tool: (gap to, and) the next larger *available* tool of its type."""
    out: Dict[Tuple[str, str], Tuple[Optional[float], Optional[Tool]]] = {}
    for tool_type in ("drill", "endmill"):
        avail_sorted = sorted((t for t in tools if t.type == tool_type and avail.get((t.type, t.name), t.available)),
                              key=lambda t: t.diameter_mm)
        for t in (t for t in tools if t.type == tool_type):
            nxt = next((a for a in avail_sorted if a.diameter_mm > t.diameter_mm + 1e-9), None)
            out[(t.type, t.name)] = (round(nxt.diameter_mm - t.diameter_mm, 4), nxt) if nxt else (None, None)
    return out


def _matches(t: Tool, available: bool, used: bool, c: Criteria) -> bool:
    if c.tool_type != "all" and t.type != c.tool_type:
        return False
    if c.system == "metric" and not is_metric(t) or c.system == "imperial" and is_metric(t):
        return False
    if c.series is not None and series_of(t) not in c.series:
        return False
    if c.availability == "available" and not available or c.availability == "retired" and available:
        return False
    if c.dmin_mm is not None and t.diameter_mm < c.dmin_mm - 1e-9:
        return False
    if c.dmax_mm is not None and t.diameter_mm > c.dmax_mm + 1e-9:
        return False
    if c.search:
        s = c.search.lower()
        if s not in t.name.lower() and s not in label(t).lower() and s not in series_of(t).lower():
            return False
    if c.used_only and not used:
        return False
    return True


def build(tools: Sequence[Tool],
          avail: Dict[Tuple[str, str], bool],
          used_for: Dict[Tuple[str, str], List[str]],
          c: Criteria) -> List[Row]:
    steps = step_table(tools, avail)
    rows = []
    for t in tools:
        key = (t.type, t.name)
        available = avail.get(key, t.available)
        if not _matches(t, available, key in used_for, c):
            continue
        gap, nxt = steps[key]
        rows.append(Row(t, available, series_of(t), used_for.get(key, []), gap, nxt))

    if c.near_mm is not None:
        below = sorted((r for r in rows if r.tool.diameter_mm <= c.near_mm), key=lambda r: -r.tool.diameter_mm)[:c.near_count]
        above = sorted((r for r in rows if r.tool.diameter_mm > c.near_mm), key=lambda r: r.tool.diameter_mm)[:c.near_count]
        rows = below + above

    if c.sort == "dia_desc":
        rows.sort(key=lambda r: (-r.tool.diameter_mm, r.tool.type))
    elif c.sort == "name":
        rows.sort(key=lambda r: (r.tool.type, _name_key(r.tool.name)))
    elif c.sort == "series":
        rows.sort(key=lambda r: (r.tool.type, r.series, r.tool.diameter_mm))
    else:
        rows.sort(key=lambda r: (r.tool.diameter_mm, r.tool.type))
    return rows


def _name_key(name: str):
    try:
        return (0, float(name), name)
    except ValueError:
        return (1, 0.0, name)


def group_title(row: Row) -> str:
    return f"{row.series} {row.tool.type}s"


def summary(rows: Sequence[Row], tools: Sequence[Tool], avail: Dict[Tuple[str, str], bool]) -> str:
    n_avail = sum(avail.get((t.type, t.name), t.available) for t in tools)
    return (f"Showing {len(rows)} of {len(tools)} tools "
            f"({n_avail} available, {len(tools) - n_avail} retired).")
