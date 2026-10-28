"""Fastener standards data and the parameter set it generates.

One table drives everything: the bundled ``fastener_parameters.csv`` (M2-M6,
every family) is generated from it, and the *Add Fastener Size* command uses
it to create the parameters for any other size.  Values and their sources:

* clearance holes      ISO 273 fine / medium / coarse series
* hole tolerances      H12 / H13 / H14 -> IT grade from ISO 286 Table 1
* pitch, tap drill     ISO 262 coarse pitch, tap drill = D - P (standard charts)
* 6H minor diameter    ISO 965-1: D1 = D - 1.082532 P, TD1 grade 6 by pitch
* socket head          ISO 4762 (dk max, k)
* button head          ISO 7380 (dk, k); M2 / M2.5 are vendor-typical
* countersunk head     DIN 7991 actual dk and k (ISO 10642 dk actual agrees)

Spot-check anything you lean on against the standard itself.
"""

import re
from typing import Dict, Iterable, List, Optional

from .paramcsv import ParamRow
from . import expr

FAMILIES = ("clearance", "tap", "counterbore_socket", "counterbore_round", "countersink")
FAMILY_LABELS = {
    "clearance": "Clearance hole (ISO 273 fine / medium / coarse)",
    "tap": "Tap drill (6H minor-diameter band)",
    "counterbore_socket": "Counterbore for socket head cap screw",
    "counterbore_round": "Counterbore for button head screw",
    "countersink": "Countersink chamfer for flat head screw",
}
FITS = ("fine", "medium", "coarse")
FIT_GRADE = {"fine": "H12", "medium": "H13", "coarse": "H14"}

GLOBALS = [  # name, value, comment
    ("countersink_depth_clearance", 0.3, "How far below flush a flat head sits"),
    ("counterbore_depth_clearance", 0.3, "How far below flush a counterbored head sits"),
    ("counterbore_radial_clearance", 1.0, "Target radial gap between head OD and counterbore wall"),
]

# size key -> nominal, pitch, ISO 273 (fine, medium, coarse), tap drill,
#             socket (dk, k) | None, button (dk, k) | None, flat (dk, k) | None
SIZES: Dict[str, dict] = {
    "m1_6": dict(d=1.6, p=0.35, iso273=(1.7, 1.8, 2.0), tap=1.25, socket=(3.0, 1.6), button=None, flat=None),
    "m2":   dict(d=2.0, p=0.4,  iso273=(2.2, 2.4, 2.6), tap=1.6,  socket=(3.8, 2.0), button=(3.5, 1.3), flat=(4.0, 1.2)),
    "m2_5": dict(d=2.5, p=0.45, iso273=(2.7, 2.9, 3.1), tap=2.05, socket=(4.5, 2.5), button=(4.7, 1.375), flat=(5.0, 1.5)),
    "m3":   dict(d=3.0, p=0.5,  iso273=(3.2, 3.4, 3.6), tap=2.5,  socket=(5.5, 3.0), button=(5.7, 1.65), flat=(6.0, 1.7)),
    "m3_5": dict(d=3.5, p=0.6,  iso273=(3.7, 3.9, 4.2), tap=2.9,  socket=None, button=None, flat=None),
    "m4":   dict(d=4.0, p=0.7,  iso273=(4.3, 4.5, 4.8), tap=3.3,  socket=(7.0, 4.0), button=(7.6, 2.2), flat=(8.0, 2.3)),
    "m5":   dict(d=5.0, p=0.8,  iso273=(5.3, 5.5, 5.8), tap=4.2,  socket=(8.5, 5.0), button=(9.5, 2.75), flat=(10.0, 2.8)),
    "m6":   dict(d=6.0, p=1.0,  iso273=(6.4, 6.6, 7.0), tap=5.0,  socket=(10.0, 6.0), button=(10.5, 3.3), flat=(12.0, 3.3)),
    "m7":   dict(d=7.0, p=1.0,  iso273=(7.4, 7.6, 8.0), tap=6.0,  socket=None, button=None, flat=None),
    "m8":   dict(d=8.0, p=1.25, iso273=(8.4, 9.0, 10.0), tap=6.8, socket=(13.0, 8.0), button=(14.0, 4.4), flat=(16.0, 4.4)),
    "m10":  dict(d=10.0, p=1.5, iso273=(10.5, 11.0, 12.0), tap=8.5, socket=(16.0, 10.0), button=(17.5, 5.5), flat=(20.0, 5.5)),
    "m12":  dict(d=12.0, p=1.75, iso273=(13.0, 13.5, 14.5), tap=10.2, socket=(18.0, 12.0), button=(21.0, 6.6), flat=(24.0, 6.5)),
    "m14":  dict(d=14.0, p=2.0, iso273=(15.0, 15.5, 16.5), tap=12.0, socket=(21.0, 14.0), button=None, flat=(27.0, 7.0)),
    "m16":  dict(d=16.0, p=2.0, iso273=(17.0, 17.5, 18.5), tap=14.0, socket=(24.0, 16.0), button=(28.0, 8.8), flat=(30.0, 7.5)),
    "m18":  dict(d=18.0, p=2.5, iso273=(19.0, 20.0, 21.0), tap=15.5, socket=None, button=None, flat=None),
    "m20":  dict(d=20.0, p=2.5, iso273=(21.0, 22.0, 24.0), tap=17.5, socket=(30.0, 20.0), button=None, flat=(36.0, 8.5)),
}

# ISO 965-1 TD1, tolerance grade 6, by pitch (mm)
TD1_GRADE6 = {0.35: 0.100, 0.4: 0.112, 0.45: 0.125, 0.5: 0.140, 0.6: 0.160, 0.7: 0.180,
              0.75: 0.190, 0.8: 0.200, 1.0: 0.236, 1.25: 0.265, 1.5: 0.300, 1.75: 0.335,
              2.0: 0.375, 2.5: 0.450}

# ISO 286 Table 1: (upper bound of size range, IT12, IT13, IT14)
IT_TABLE = [(3, 0.10, 0.14, 0.25), (6, 0.12, 0.18, 0.30), (10, 0.15, 0.22, 0.36),
            (18, 0.18, 0.27, 0.43), (30, 0.21, 0.33, 0.52), (50, 0.25, 0.39, 0.62)]
D1_FACTOR = 1.082532   # H = 0.866025 P, D1 = D - 2 * (5/8) H


def size_label(key: str) -> str:
    """'m2_5' -> 'M2.5'"""
    return "M" + key[1:].replace("_", ".")


def size_key(label: str) -> str:
    """'M2.5' / 'm2.5' / '2.5' -> 'm2_5'"""
    s = label.strip().lower().lstrip("m").replace(",", ".")
    return "m" + s.replace(".", "_")


def sort_key(key: str) -> float:
    return float(key[1:].replace("_", "."))


def it_grade(d: float, grade: int) -> float:
    """IT12/13/14 fundamental tolerance for a hole of diameter d (mm)."""
    for upper, it12, it13, it14 in IT_TABLE:
        if d <= upper:
            return {12: it12, 13: it13, 14: it14}[grade]
    raise ValueError(f"no IT table entry for {d} mm")


def it_range(d: float) -> str:
    lo = 0
    for upper, *_ in IT_TABLE:
        if d <= upper:
            return f"{lo}-{upper}"
        lo = upper
    raise ValueError(d)


def families_for(key: str) -> List[str]:
    """Families the table can populate for this size."""
    s = SIZES[key]
    out = ["clearance", "tap"]
    if s["socket"]:
        out.append("counterbore_socket")
    if s["button"]:
        out.append("counterbore_round")
    if s["flat"]:
        out.append("countersink")
    return out


def _row(name, expression, value, comment, favorite=False, unit="mm"):
    return ParamRow(name=name, unit=unit, expression=expression, value=value,
                    comment=comment, favorite=favorite)


def param_rows(sizes: Iterable[str], families: Iterable[str] = FAMILIES,
               include_globals: bool = True) -> List[ParamRow]:
    """Generate the parameter set for ``sizes`` x ``families``.

    Rows come out grouped by family across sizes (the layout of the bundled
    CSV).  Expression-driven rows get their Value evaluated so the CSV is
    self-consistent; tool-driven rows hold their target until Snap runs.
    """
    sizes = sorted(sizes, key=sort_key)
    fam = set(families)
    rows: List[ParamRow] = []
    blocks: Dict[str, List[ParamRow]] = {k: [] for k in (
        "nominal", "clearance", "fine", "medium", "coarse", "fine_max", "medium_max", "coarse_max",
        "pilot", "pilot_nominal", "pitch", "tap_min", "tap_max",
        "socket_h", "socket_od", "flat_h", "flat_od", "round_h", "round_od",
        "globals", "cb_od_round", "cb_depth_round", "cb_od_socket", "cb_depth_socket",
        "csk_slip", "csk_tapped")}

    for key in sizes:
        s = SIZES[key]; d = s["d"]; p = s["p"]; lbl = size_label(key)
        blocks["nominal"].append(_row(f"{key}_nominal_dia", "", d, f"{lbl} nominal thread diameter"))
        if "clearance" in fam:
            vals = dict(zip(FITS, s["iso273"]))
            blocks["clearance"].append(_row(f"{key}_clearance_hole", "", vals["medium"],
                                            "Tool-driven: written by ToolSnap from the shop inventory", True))
            for fit in FITS:
                v = vals[fit]; g = FIT_GRADE[fit]; it = it_grade(v, int(g[1:]))
                blocks[fit].append(_row(f"{key}_clearance_hole_{fit}", "", v, f"ISO 273 {fit} series"))
                blocks[f"{fit}_max"].append(_row(
                    f"{key}_clearance_hole_{fit}_max", f"{key}_clearance_hole_{fit} + {it:g} mm", round(v + it, 3),
                    f"ISO 273 {fit} = {g}: upper limit, IT{g[1:]} over {it_range(v)} mm = {it:g} (ISO 286)"))
        if "tap" in fam or "countersink" in fam:
            blocks["pitch"].append(_row(f"{key}_thread_pitch", "", p,
                                        "ISO metric coarse pitch; drives the % thread note in ToolSnap"))
        if "tap" in fam:
            d1 = d - D1_FACTOR * p; td1 = TD1_GRADE6[p]
            blocks["pilot"].append(_row(f"{key}_pilot_drill", "", s["tap"],
                                        "Tool-driven: written by ToolSnap from the shop inventory", True))
            blocks["pilot_nominal"].append(_row(f"{key}_pilot_drill_nominal", "", s["tap"],
                                                "Standard tap drill, ISO metric coarse thread (~75% thread)"))
            blocks["tap_min"].append(_row(f"{key}_tap_drill_min", f"{key}_nominal_dia - {D1_FACTOR} * {key}_thread_pitch",
                                          round(d1, 3), "6H minor diameter minimum = basic D1 (ISO 965-1)"))
            blocks["tap_max"].append(_row(f"{key}_tap_drill_max", f"{key}_tap_drill_min + {td1:g} mm", round(d1 + td1, 3),
                                          f"6H minor diameter maximum: TD1 grade 6 for P={p:g} is {td1:g} (ISO 965-1)"))
        if "counterbore_socket" in fam and s["socket"]:
            dk, k = s["socket"]
            blocks["socket_h"].append(_row(f"{key}_socket_head_height", "", k, f"ISO 4762 {lbl} head height k"))
            blocks["socket_od"].append(_row(f"{key}_socket_head_OD", "", dk, f"ISO 4762 {lbl} head diameter dk max"))
            blocks["cb_od_socket"].append(_row(f"{key}_counterbore_ID_socket", "", dk + 2.0,
                                               "Tool-driven: written by ToolSnap from the shop inventory", True))
            blocks["cb_depth_socket"].append(_row(f"{key}_counterbore_depth_socket",
                                                  f"{key}_socket_head_height + counterbore_depth_clearance", None, "", True))
        if "counterbore_round" in fam and s["button"]:
            dk, k = s["button"]
            blocks["round_h"].append(_row(f"{key}_round_head_height", "", k, f"ISO 7380 {lbl} button head height k"))
            blocks["round_od"].append(_row(f"{key}_round_head_OD", "", dk, f"ISO 7380 {lbl} button head diameter dk"))
            blocks["cb_od_round"].append(_row(f"{key}_counterbore_ID_round", "", dk + 2.0,
                                              "Tool-driven: written by ToolSnap from the shop inventory", True))
            blocks["cb_depth_round"].append(_row(f"{key}_counterbore_depth_round",
                                                 f"{key}_round_head_height + counterbore_depth_clearance", None, "", True))
        if "countersink" in fam and s["flat"]:
            dk, k = s["flat"]
            blocks["flat_h"].append(_row(f"{key}_flat_head_height", "", k, f"DIN 7991 {lbl} countersunk head height k"))
            blocks["flat_od"].append(_row(f"{key}_flat_head_OD", "", dk, f"DIN 7991 {lbl} countersunk head diameter dk (actual)"))
            note = "45 deg equal-distance chamfer leg on the hole edge"
            if "clearance" in fam:
                blocks["csk_slip"].append(_row(
                    f"{key}_countersink_chamfer_clearance",
                    f"{key}_flat_head_height + countersink_depth_clearance + ({key}_nominal_dia - {key}_clearance_hole) / 2",
                    None, note, True))
            if "tap" in fam:
                blocks["csk_tapped"].append(_row(
                    f"{key}_countersink_chamfer_tapped",
                    f"{key}_flat_head_height + countersink_depth_clearance + ({key}_nominal_dia - {key}_pilot_drill) / 2",
                    None, note, True))
    if include_globals:
        blocks["globals"] = [_row(n, "", v, c) for n, v, c in GLOBALS]
    for k in blocks:
        rows.extend(blocks[k])

    # evaluate expression rows so Value is consistent with Expression
    values = {r.name: r.value for r in rows if r.value is not None}
    for r in rows:
        if r.expression:
            r.value = round(expr.evaluate(r.expression, values), 4)
            values[r.name] = r.value
    return rows


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_UNITS = {"mm", "cm", "m", "in", "ft", "deg", "rad"}


def identifiers(expression: str) -> List[str]:
    """Parameter names referenced by a Fusion expression (unit words excluded)."""
    return [t for t in _IDENT.findall(expression) if t not in _UNITS]


def sizes_in(names: Iterable[str]) -> List[str]:
    """Size keys present in a set of parameter names, by their *_nominal_dia."""
    found = [n[:-len("_nominal_dia")] for n in names if n.endswith("_nominal_dia")]
    return sorted((k for k in found if re.fullmatch(r"m\d+(_\d+)?", k)), key=sort_key)


def new_sizes_available(existing: Iterable[str]) -> List[str]:
    have = set(existing)
    return [k for k in sorted(SIZES, key=sort_key) if k not in have]


def resolve_size(key: str) -> Optional[dict]:
    return SIZES.get(key)
