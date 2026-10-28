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
            for m in sizes:
                def fill(s: Optional[str]) -> Optional[str]:
                    return None if s is None else s.replace("{m}", m).replace("{fit}", fit)
                out.append(Rule(parameter=fill(rule.parameter), tool=rule.tool,
                                target=fill(rule.target), floor=fill(rule.floor),
                                mode=rule.mode, comment=fill(rule.comment)))
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
                          floor=raw.get("floor"), mode=mode, comment=raw.get("comment", "")))
    return RuleSet(sizes=list(data.get("sizes", [])),
                   fits=list(data.get("fits", ["fine", "medium", "coarse"])),
                   defaults=dict(data.get("defaults", {})),
                   rules=rules)


@dataclass
class Snapped:
    rule: Rule
    result: SnapResult

    @property
    def parameter(self) -> str:
        return self.rule.parameter


def run(ruleset: RuleSet,
        tools: List[Tool],
        evaluate: Callable[[str], float],
        fit: str,
        tolerance_mm: float = 0.0,
        mode_overrides: Optional[Dict[str, str]] = None) -> List[Snapped]:
    """Evaluate every expanded rule and snap it.

    ``evaluate`` turns a Fusion expression into mm - inside Fusion that is the
    design's UnitsManager, in tests it is ``core.expr.evaluate`` over a dict.
    ``mode_overrides`` maps parameter name -> mode for per-row choices made in
    the dialog.
    """
    overrides = mode_overrides or {}
    out = []
    for rule in ruleset.expand(fit):
        target = evaluate(rule.target)
        floor = evaluate(rule.floor) if rule.floor else None
        mode = overrides.get(rule.parameter, rule.mode)
        out.append(Snapped(rule, snap(target, tools, rule.tool, mode, floor, tolerance_mm)))
    return out
