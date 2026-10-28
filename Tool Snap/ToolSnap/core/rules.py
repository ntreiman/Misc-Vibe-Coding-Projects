"""Snap rules: which user parameters are tool-driven and how to compute their
target and floor.

``snap_rules.json`` keeps the rules compact with two placeholders:

* ``{m}``   - expanded over ``sizes`` (``m2`` .. ``m6``), so one rule covers
              every fastener size
* ``{fit}`` - the active ISO 273 clearance series (``fine`` / ``medium`` /
              ``coarse``)

A rule's ``target`` and ``floor`` are ordinary Fusion expressions over user
parameters, which is what makes this flexible: add a rule for ``m8`` or a
dowel pin without touching Python.
"""

import json
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .snap import MODES, SnapResult, Tool, snap


@dataclass(frozen=True)
class Rule:
    parameter: str
    tool: str                    # "drill" | "endmill"
    target: str                  # Fusion expression -> mm
    floor: Optional[str] = None  # Fusion expression -> mm, or None
    mode: str = "Up"
    comment: str = ""
    # optional annotations, shown as a note next to the result:
    nominal: Optional[str] = None  # thread nominal Ø   -> "% thread" for tap drills
    pitch: Optional[str] = None    # thread pitch        (needs nominal too)
    head_od: Optional[str] = None  # screw head Ø        -> actual radial clearance of a counterbore

    def filled(self, m: str, fit: str) -> "Rule":
        def fill(s: Optional[str]) -> Optional[str]:
            return None if s is None else s.replace("{m}", m).replace("{fit}", fit)
        return Rule(parameter=fill(self.parameter), tool=self.tool, target=fill(self.target),
                    floor=fill(self.floor), mode=self.mode, comment=fill(self.comment),
                    nominal=fill(self.nominal), pitch=fill(self.pitch), head_od=fill(self.head_od))


@dataclass
class RuleSet:
    sizes: List[str]
    fits: List[str]
    defaults: Dict[str, object]
    rules: List[Rule]

    def expand(self, fit: str) -> List[Rule]:
        """Instantiate the templated rules for every size and the given fit."""
        if fit not in self.fits:
            raise ValueError(f"fit must be one of {self.fits}, got {fit!r}")
        out: List[Rule] = []
        for rule in self.rules:
            sizes = self.sizes if "{m}" in rule.parameter else [""]
            out.extend(rule.filled(m, fit) for m in sizes)
        return out


def load(path: str) -> RuleSet:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    rules = []
    for raw in data["rules"]:
        mode = raw.get("mode", "Up")
        if mode not in MODES:
            raise ValueError(f"rule {raw.get('parameter')}: unknown mode {mode!r}")
        if raw["tool"] not in ("drill", "endmill"):
            raise ValueError(f"rule {raw.get('parameter')}: tool must be drill or endmill")
        rules.append(Rule(parameter=raw["parameter"], tool=raw["tool"], target=raw["target"],
                          floor=raw.get("floor"), mode=mode, comment=raw.get("comment", ""),
                          nominal=raw.get("nominal"), pitch=raw.get("pitch"),
                          head_od=raw.get("head_od")))
    return RuleSet(sizes=list(data.get("sizes", [])),
                   fits=list(data.get("fits", ["fine", "medium", "coarse"])),
                   defaults=dict(data.get("defaults", {})),
                   rules=rules)


@dataclass
class Snapped:
    rule: Rule
    result: Optional[SnapResult]   # None when an expression could not be evaluated
    note: str = ""                 # "% thread" / "radial x mm" annotation
    error: str = ""                # why result is None

    @property
    def parameter(self) -> str:
        return self.rule.parameter

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.ok

    @property
    def kept(self) -> bool:
        return self.result is not None and self.result.kept


# Machinery's Handbook convention: % thread = (D - drill) / (1.299 * pitch),
# the one tap-drill charts use when they say "75 % thread".
THREAD_FACTOR = 1.299


def thread_percent(nominal_mm: float, pitch_mm: float, drill_mm: float) -> float:
    return 100.0 * (nominal_mm - drill_mm) / (THREAD_FACTOR * pitch_mm)


def _note(rule: Rule, result: SnapResult, evaluate) -> str:
    if not result.ok:
        return ""
    if rule.nominal and rule.pitch:
        pct = thread_percent(evaluate(rule.nominal), evaluate(rule.pitch), result.snapped_mm)
        return f"{pct:.0f}% thread"
    if rule.head_od:
        radial = (result.snapped_mm - evaluate(rule.head_od)) / 2
        return f"radial {radial:.2f} mm"
    return ""


def run(ruleset: RuleSet,
        tools: List[Tool],
        evaluate: Callable[[str], float],
        fit: str,
        tolerance_mm: float = 0.0,
        mode_overrides: Optional[Dict[str, str]] = None,
        strict: bool = True) -> List[Snapped]:
    """Evaluate every expanded rule and snap it.

    ``evaluate`` turns a Fusion expression into mm - inside Fusion that is the
    design's UnitsManager, in tests it is ``core.expr.evaluate`` over a dict.
    ``mode_overrides`` maps parameter name -> mode for per-row choices made in
    the dialog.  With ``strict=False`` a rule whose expressions fail to
    evaluate (parameter missing from the design) yields ``result=None`` and
    an ``error`` instead of raising, so the dialog can show it.
    """
    overrides = mode_overrides or {}
    out = []
    for rule in ruleset.expand(fit):
        try:
            target = evaluate(rule.target)
            floor = evaluate(rule.floor) if rule.floor else None
            mode = overrides.get(rule.parameter, rule.mode)
            result = snap(target, tools, rule.tool, mode, floor, tolerance_mm)
            out.append(Snapped(rule, result, _note(rule, result, evaluate)))
        except Exception as exc:  # noqa: BLE001 - reported per row when not strict
            if strict:
                raise
            out.append(Snapped(rule, None, error=str(exc)))
    return out
