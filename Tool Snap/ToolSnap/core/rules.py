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
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional

from .snap import MODES, SnapResult, Tool, snap
from .standards import identifiers, size_label


@dataclass(frozen=True)
class Rule:
    parameter: str
    tool: str                    # "drill" | "endmill"
    target: str                  # Fusion expression -> mm
    floor: Optional[str] = None  # Fusion expression -> mm, or None (hard minimum)
    ceiling: Optional[str] = None  # Fusion expression -> mm, or None (ISO maximum, flagged)
    mode: str = "Up"
    comment: str = ""
    # optional annotations, shown as a note next to the result:
    nominal: Optional[str] = None  # thread nominal Ø   -> "% thread" for tap drills
    pitch: Optional[str] = None    # thread pitch        (needs nominal too)
    head_od: Optional[str] = None  # screw head Ø        -> actual radial clearance of a counterbore
    legacy: Optional[str] = None   # older parameter name; written in place when only it exists

    def filled(self, m: str, fit: str) -> "Rule":
        def fill(s: Optional[str]) -> Optional[str]:
            return None if s is None else s.replace("{em}", m).replace("{m}", m).replace("{fit}", fit)
        return Rule(parameter=fill(self.parameter), tool=self.tool, target=fill(self.target),
                    floor=fill(self.floor), ceiling=fill(self.ceiling), mode=self.mode,
                    comment=fill(self.comment), nominal=fill(self.nominal),
                    pitch=fill(self.pitch), head_od=fill(self.head_od), legacy=fill(self.legacy))


@dataclass
class RuleSet:
    sizes: List[str]
    fits: List[str]
    defaults: Dict[str, object]
    rules: List[Rule]
    endmill_classes: List[str] = None

    def expand(self, fit: str, sizes: Optional[List[str]] = None,
               endmill_classes: Optional[List[str]] = None) -> List[Rule]:
        """Instantiate the templated rules for every size / endmill class and the given fit.

        ``sizes`` / ``endmill_classes`` override the file's defaults - the Fusion
        dialog passes what is actually present in the design (every
        ``mX_nominal_dia`` / ``emN_nominal_dia``).
        """
        if fit not in self.fits:
            raise ValueError(f"fit must be one of {self.fits}, got {fit!r}")
        use = self.sizes if sizes is None else sizes
        ems = (self.endmill_classes or []) if endmill_classes is None else endmill_classes
        out: List[Rule] = []
        for rule in self.rules:
            if "{em}" in rule.parameter:
                per = ems
            elif "{m}" in rule.parameter:
                per = use
            else:
                per = [""]
            out.extend(rule.filled(m, fit) for m in per)
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
                          floor=raw.get("floor"), ceiling=raw.get("ceiling"), mode=mode,
                          comment=raw.get("comment", ""),
                          nominal=raw.get("nominal"), pitch=raw.get("pitch"),
                          head_od=raw.get("head_od"), legacy=raw.get("legacy")))
    return RuleSet(sizes=list(data.get("sizes", [])),
                   fits=list(data.get("fits", ["fine", "medium", "coarse"])),
                   defaults=dict(data.get("defaults", {})),
                   rules=rules,
                   endmill_classes=list(data.get("endmill_classes", [])))


@dataclass
class Snapped:
    rule: Rule
    result: Optional[SnapResult]   # None when an expression could not be evaluated
    note: str = ""                 # "% thread" / "radial x mm" annotation
    error: str = ""                # why result is None
    skipped: bool = False          # family not set up for this size (inputs absent) - not an error

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
    parts = []
    if rule.nominal and rule.pitch:
        pct = thread_percent(evaluate(rule.nominal), evaluate(rule.pitch), result.snapped_mm)
        parts.append(f"{pct:.0f}% thread")
    if rule.head_od:
        radial = (result.snapped_mm - evaluate(rule.head_od)) / 2
        parts.append(f"radial {radial:.2f} mm")
    elif rule.tool == "endmill":
        parts.append(f"radius {result.snapped_mm / 2:.3f} mm")
    if result.over_ceiling:
        parts.append(f"OVER ISO max {result.ceiling_mm:.3f}")
    return ", ".join(parts)


def inputs_of(rule: Rule) -> List[str]:
    """Every parameter name a rule reads."""
    names: List[str] = []
    for e in (rule.target, rule.floor, rule.ceiling, rule.nominal, rule.pitch, rule.head_od):
        if e:
            names.extend(identifiers(e))
    return sorted(set(names))


def run(ruleset: RuleSet,
        tools: List[Tool],
        evaluate: Callable[[str], float],
        fit: str,
        tolerance_mm: float = 0.0,
        mode_overrides: Optional[Dict[str, str]] = None,
        strict: bool = True,
        sizes: Optional[List[str]] = None,
        has_param: Optional[Callable[[str], bool]] = None,
        endmill_classes: Optional[List[str]] = None) -> List[Snapped]:
    """Evaluate every expanded rule and snap it.

    ``evaluate`` turns a Fusion expression into mm - inside Fusion that is the
    design's UnitsManager, in tests it is ``core.expr.evaluate`` over a dict.
    ``mode_overrides`` maps parameter name -> mode for per-row choices made in
    the dialog.  With ``strict=False`` a rule whose expressions fail to
    evaluate (parameter missing from the design) yields ``result=None`` and
    an ``error`` instead of raising, so the dialog can show it.  ``sizes``
    selects which fastener sizes to expand; with ``has_param`` a rule whose
    inputs are absent is marked ``skipped`` (that family just isn't set up for
    that size) rather than treated as an error.
    """
    overrides = mode_overrides or {}
    out = []
    for rule in ruleset.expand(fit, sizes, endmill_classes):
        if has_param is not None:
            if rule.legacy and has_param(rule.legacy) and not has_param(rule.parameter):
                rule = replace(rule, parameter=rule.legacy)   # keep writing the design's own name
            missing = [n for n in inputs_of(rule) if not has_param(n)]
            if missing:
                out.append(Snapped(rule, None, error="needs " + ", ".join(missing), skipped=True))
                continue
        try:
            target = evaluate(rule.target)
            floor = evaluate(rule.floor) if rule.floor else None
            ceiling = evaluate(rule.ceiling) if rule.ceiling else None
            mode = overrides.get(rule.parameter, rule.mode)
            result = snap(target, tools, rule.tool, mode, floor, tolerance_mm, ceiling)
            out.append(Snapped(rule, result, _note(rule, result, evaluate)))
        except Exception as exc:  # noqa: BLE001 - reported per row when not strict
            if strict:
                raise
            out.append(Snapped(rule, None, error=str(exc)))
    return out


_SHORT = (("_counterbore_ID_socket", " cbore socket"), ("_counterbore_ID_round", " cbore button"),
          ("_clearance_hole", " clearance"), ("_pilot_drill", " tap drill"), ("_dia", " endmill"))


def short_name(parameter: str) -> str:
    """'m4_counterbore_ID_socket' -> 'M4 cbore socket' (for compact UI columns)."""
    for suffix, label in _SHORT:
        if parameter.endswith(suffix):
            return size_label(parameter[:-len(suffix)]) + label
    return parameter
