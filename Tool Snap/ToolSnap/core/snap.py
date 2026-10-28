"""Snap a target diameter to a tool you actually own.

This is a direct port of the ``Tool Snap`` tab in the "Tools and Fastener
Parameters" spreadsheet, so the two can be cross-checked against each other:

* ``Up``      -> smallest available tool >= max(target - tol, floor)
* ``Down``    -> largest available tool <= target + tol that is still >= floor;
                 falls back to ``Up`` when nothing qualifies
* ``Nearest`` -> whichever of Up / Down is closer to the target (ties go Up,
                 i.e. the larger clearance)
* ``Off``     -> pass the target straight through (e.g. helical-bored
                 counterbores on a CNC, where any diameter is machinable)

Everything here is pure Python so it runs under plain ``python -m pytest``
without Fusion.
"""

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

MODES = ("Up", "Nearest", "Down", "Off")
ROUNDING = 4  # decimal places, same as the spreadsheet


@dataclass(frozen=True)
class Tool:
    name: str
    type: str          # "drill" | "endmill"
    diameter_mm: float
    available: bool = True
    category: str = ""


@dataclass
class SnapResult:
    target_mm: float
    floor_mm: Optional[float]
    mode: str
    up_mm: Optional[float]
    down_mm: Optional[float]
    snapped_mm: Optional[float]
    tools: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.snapped_mm is not None

    @property
    def delta_mm(self) -> Optional[float]:
        if self.snapped_mm is None:
            return None
        return round(self.snapped_mm - self.target_mm, ROUNDING)

    @property
    def tool_label(self) -> str:
        if self.mode == "Off":
            return "(not snapped)"
        return " / ".join(self.tools) if self.tools else "no tool"


def _available(tools: Iterable[Tool], tool_type: str) -> List[Tool]:
    return [t for t in tools if t.available and t.type == tool_type]


def snap(target_mm: float,
         tools: Sequence[Tool],
         tool_type: str,
         mode: str = "Up",
         floor_mm: Optional[float] = None,
         tolerance_mm: float = 0.0) -> SnapResult:
    """Pick the diameter to cut for ``target_mm`` from ``tools`` of ``tool_type``."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    floor = floor_mm or 0.0
    pool = _available(tools, tool_type)
    dias = sorted({t.diameter_mm for t in pool})

    up_candidates = [d for d in dias if d >= max(target_mm - tolerance_mm, floor)]
    down_candidates = [d for d in dias if d <= target_mm + tolerance_mm and d >= floor]
    up = up_candidates[0] if up_candidates else None
    down = down_candidates[-1] if down_candidates else None

    if mode == "Off":
        pick = target_mm
    elif mode == "Up":
        pick = up
    elif mode == "Down":
        pick = down if down is not None else up
    else:  # Nearest
        if up is None:
            pick = down
        elif down is None:
            pick = up
        else:
            pick = up if (up - target_mm) <= (target_mm - down) else down

    snapped = round(pick, ROUNDING) if pick is not None else None
    names = []
    if snapped is not None and mode != "Off":
        names = [t.name for t in pool if round(t.diameter_mm, ROUNDING) == snapped]
    return SnapResult(target_mm=target_mm, floor_mm=floor_mm, mode=mode,
                      up_mm=up, down_mm=down, snapped_mm=snapped, tools=names)
