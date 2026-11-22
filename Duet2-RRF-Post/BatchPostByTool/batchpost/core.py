"""Pure-Python part of Batch Post by Tool: grouping and naming. No Fusion imports."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class OpInfo:
    """What the add-in needs to know about one operation, in setup order."""
    name: str
    tool_number: Optional[int]      # None = no tool (e.g. a folder/pattern) or unreadable
    handle: Any = None              # the Fusion Operation object (opaque here)
    suppressed: bool = False


@dataclass
class Group:
    """A consecutive run of operations sharing one tool number."""
    index: int                      # 1-based run index in the setup
    tool_number: int
    ops: List[OpInfo] = field(default_factory=list)
    run_of_tool: int = 1            # 1 for the first run of this tool, 2 for the second ...
    tool_repeats: bool = False      # True when the tool has more than one run in the setup

    @property
    def program_name(self) -> str:
        """Name Fusion writes its own (temporary) file under. Unique per run."""
        return "run%02d_T%d" % (self.index, self.tool_number)


def group_consecutive(ops: List[OpInfo]) -> List[Group]:
    """Split the operation list into runs of consecutive equal tool numbers.

    Suppressed operations and operations without a tool are skipped and do
    not break a run (T1, T1-suppressed, T1 is one run).
    """
    groups: List[Group] = []
    for op in ops:
        if op.suppressed or op.tool_number is None:
            continue
        if groups and groups[-1].tool_number == op.tool_number:
            groups[-1].ops.append(op)
        else:
            groups.append(Group(index=len(groups) + 1, tool_number=op.tool_number, ops=[op]))
    counts = {}
    for g in groups:
        counts[g.tool_number] = counts.get(g.tool_number, 0) + 1
        g.run_of_tool = counts[g.tool_number]
    for g in groups:
        g.tool_repeats = counts[g.tool_number] > 1
    return groups


def post_property_overrides(group: Group) -> dict:
    """Post properties forced for every batch post, as name -> python value."""
    props = {
        "descriptiveFileName": True,
        "descriptiveFileMethod": "rename",       # single file, no dialog-named leftover
        "descriptiveFileNamePrefix": "op",
        "descriptiveFileNameRun": group.run_of_tool if group.tool_repeats else 0,
    }
    return props


def summary_lines(groups: List[Group]) -> List[str]:
    out = []
    for g in groups:
        names = ", ".join(op.name for op in g.ops)
        suffix = " (run %d of this tool)" % g.run_of_tool if g.tool_repeats else ""
        out.append("T%d%s: %s" % (g.tool_number, suffix, names))
    return out
