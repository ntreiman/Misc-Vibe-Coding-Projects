"""'Snap to Tools' command.

Dialog = the Tool Snap tab of the spreadsheet: fit / tolerance knobs at the
top, then one row per tool-driven parameter with its target, floor, a Mode
dropdown, and the live snapped result.  OK writes the snapped diameters into
the design's user parameters as hard values; everything downstream
(counterbore depths, countersink chamfers) is still expression-driven inside
Fusion and recomputes on its own.
"""

import json
import os
from typing import Dict, List

import adsk.core

from ..core import inventory, rules, standards
from ..core.snap import MODES
from . import params, toollib, ui

CMD_ID = "ToolSnap_Snap"
SETTINGS_PATH = os.path.join(ui.DATA_DIR, "snap_settings.json")
SOURCES = ("Shop inventory (shop_tools.json)",
           "Shop inventory + Fusion local tool libraries")
COLS = ("Parameter", "Target", "Floor", "Mode", "Snapped", "Tool(s)", "Δ", "Note")
MODE_COL = 3
TEXT_COLS = tuple(c for c in range(len(COLS)) if c != MODE_COL)


def _load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_settings(data: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
    except OSError:
        pass  # purely a convenience; never block the command on it


class State:
    """Per-dialog state shared by the handlers."""

    def __init__(self, design):
        self.design = design
        self.evaluate = params.evaluator(design)
        self.ruleset = rules.load(ui.RULES_PATH)
        self.settings = _load_settings()
        self.results: List[rules.Snapped] = []
        self.problems: List[str] = []
        self.rows: List[str] = []      # parameter name per table row, in order
        self.row_index: Dict[str, int] = {}
        self._tool_cache: Dict[int, list] = {}
        names = set(ui.user_parameter_names(design))
        self.sizes = standards.sizes_in(names)      # every mX_nominal_dia in the design
        self.endmill_classes = standards.endmill_classes_in(names)   # every emN_nominal_dia
        self.has_param = names.__contains__

    def tools(self, source_index: int):
        if source_index not in self._tool_cache:
            tools = inventory.load(ui.TOOLS_PATH)
            if source_index == 1:
                extra, notes = toollib.read_local_libraries()
                tools = tools + extra
                self.problems.extend(notes)
            self._tool_cache[source_index] = tools
        return self._tool_cache[source_index]

    def compute(self, inputs):
        fit = inputs.itemById("fit").selectedItem.name
        tol_input = inputs.itemById("tol")
        um = self.design.unitsManager
        # value is in database units (cm); a half-typed expression is not valid yet
        tol_mm = um.convert(tol_input.value, um.internalUnits, "mm") if tol_input.isValidExpression else 0.0
        source = inputs.itemById("source").selectedItem.index
        overrides = {name: inputs.itemById(f"mode_{i}").selectedItem.name
                     for i, name in enumerate(self.rows) if inputs.itemById(f"mode_{i}")}
        results = rules.run(self.ruleset, self.tools(source), self.evaluate, fit, tol_mm,
                            overrides, strict=False, sizes=self.sizes, has_param=self.has_param,
                            endmill_classes=self.endmill_classes)
        self.results = results
        self.settings.update({"fit": fit, "tolerance_mm": tol_mm, "source": source,
                              "modes": overrides})
        return results


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            cmd = args.command
            state = State(ui.active_design(app))
            cmd.okButtonText = "Write parameters"
            cmd.setDialogMinimumSize(760, 520)
            inputs = cmd.commandInputs
            s = state.settings

            source = inputs.addDropDownCommandInput("source", "Tool source",
                                                    adsk.core.DropDownStyles.TextListDropDownStyle)
            for i, name in enumerate(SOURCES):
                source.listItems.add(name, i == int(s.get("source", 0)))
            fit = inputs.addDropDownCommandInput("fit", "Clearance fit (ISO 273)",
                                                 adsk.core.DropDownStyles.TextListDropDownStyle)
            default_fit = s.get("fit", state.ruleset.defaults.get("fit", "medium"))
            for name in state.ruleset.fits:
                fit.listItems.add(name, name == default_fit)
            tol0 = float(s.get("tolerance_mm", state.ruleset.defaults.get("tolerance_mm", 0)))
            inputs.addValueInput("tol", "Snap tolerance", "mm",
                                 adsk.core.ValueInput.createByString(f"{tol0:g} mm"))

            table = inputs.addTableCommandInput("table", "Snap preview", len(COLS), "5:2:2:3:2:3:2:3")
            # max first: the default max is 4 and min may not exceed it
            table.maximumVisibleRows = 22
            table.minimumVisibleRows = 8
            for c, title in enumerate(COLS):
                cell = inputs.addStringValueInput(f"hdr_{c}", title, title)
                cell.isReadOnly = True
                table.addCommandInput(cell, 0, c)

            # one table row per rule whose inputs exist in this design
            first = rules.run(state.ruleset, [], state.evaluate, default_fit, strict=False,
                              sizes=state.sizes, has_param=state.has_param,
                              endmill_classes=state.endmill_classes)
            saved_modes = s.get("modes", {})
            for snapped_rule in (r for r in first if not r.skipped):
                rule = snapped_rule.rule
                i = len(state.rows)
                state.rows.append(rule.parameter)
                state.row_index[rule.parameter] = i
                row = i + 1
                for c in TEXT_COLS:
                    cell = inputs.addStringValueInput(f"c{c}_{i}", COLS[c], "")
                    cell.isReadOnly = True
                    table.addCommandInput(cell, row, c)
                dd = inputs.addDropDownCommandInput(f"mode_{i}", "Mode",
                                                    adsk.core.DropDownStyles.TextListDropDownStyle)
                chosen = saved_modes.get(rule.parameter, rule.mode)
                for m in MODES:
                    dd.listItems.add(m, m == chosen)
                table.addCommandInput(dd, row, MODE_COL)

            inputs.addTextBoxCommandInput("status", "", "", 4, True)

            refresh(state, inputs)
            for ev, h in ((cmd.inputChanged, Changed(state)), (cmd.execute, Execute(state))):
                ev.add(h)
                ui.handlers.append(h)
        except Exception:
            ui.report_error(app.userInterface, "Snap to Tools failed to open")


def refresh(state: State, inputs) -> None:
    results = state.compute(inputs)
    for snapped in results:
        if snapped.skipped or snapped.parameter not in state.row_index:
            continue
        i = state.row_index[snapped.parameter]
        r = snapped.result
        if r is None:
            cells = (snapped.parameter, "?", "", "?", "", "", "missing parameter")
        elif r.kept:
            current = params.get_mm(state.design, snapped.parameter)
            cells = (snapped.parameter, f"{r.target_mm:.3f}", "",
                     f"{current:.4f}" if current is not None else "(absent)", r.tool_label, "", "")
        else:
            cells = (snapped.parameter,
                     f"{r.target_mm:.3f}",
                     f"{r.floor_mm:.3f}" if r.floor_mm is not None else "",
                     f"{r.snapped_mm:.4f}" if r.ok else "NONE",
                     r.tool_label,
                     f"{r.delta_mm:+.3f}" if r.ok else "",
                     snapped.note)
        for c, text in zip(TEXT_COLS, cells):
            inputs.itemById(f"c{c}_{i}").value = text
        # hover a Target / Floor cell to see the expression it came from
        inputs.itemById(f"c1_{i}").tooltip = snapped.rule.target
        floor_tip = snapped.rule.floor or ""
        if snapped.rule.ceiling:
            floor_tip += f"\nISO max: {snapped.rule.ceiling}"
        inputs.itemById(f"c2_{i}").tooltip = floor_tip
    missing = [s for s in results if s.result is None and not s.skipped]
    skipped = [s for s in results if s.skipped]
    no_tool = [s for s in results if s.result is not None and not s.ok and not s.kept]
    lines = []
    if missing:
        lines.append(f"{len(missing)} parameter(s) missing from this design - run Import Parameters first. "
                     f"({missing[0].error})")
    if no_tool:
        lines.append("No available tool for: " + ", ".join(s.parameter for s in no_tool))
    over = [s for s in results if s.result is not None and s.result.over_ceiling]
    if over:
        lines.append("Over the ISO maximum (no smaller tool available): "
                     + ", ".join(s.parameter for s in over))
    lines.extend(state.problems)
    if not lines:
        lines.append("All rows resolve to an available tool. In this design: "
                     + ", ".join(standards.size_label(k) for k in state.sizes + state.endmill_classes) + ".")
    if skipped:
        lines.append("Not set up for this design (Add Fastener Size): "
                     + ", ".join(rules.short_name(s.parameter) for s in skipped))
    inputs.itemById("status").text = "\n".join(lines)


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if args.input.id in ("source", "fit", "tol") or args.input.id.startswith("mode_"):
                refresh(self.state, args.inputs)
        except Exception:
            ui.report_error(adsk.core.Application.get().userInterface, "Snap preview failed")


class Execute(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            state = self.state
            results = state.compute(args.command.commandInputs)
            changed, skipped, kept, same = [], [], [], 0
            for s in results:
                r = s.result
                if s.skipped:
                    continue
                if s.kept:
                    kept.append(s.parameter)
                    continue
                if not s.ok:
                    skipped.append(s.parameter)
                    continue
                before = params.get_mm(state.design, s.parameter)
                comment = (f"Tool-driven ({r.mode}): {r.tool_label}, target {r.target_mm:.3f} mm"
                           if r.mode != "Off" else "Tool-driven (Off): target written unsnapped")
                params.set_mm(state.design, s.parameter, r.snapped_mm, comment=comment, favorite_if_new=True)
                if before is None or abs(before - r.snapped_mm) > 1e-6:
                    changed.append(f"{s.parameter}: "
                                   f"{'new' if before is None else f'{before:.4f}'} → {r.snapped_mm:.4f} mm  [{r.tool_label}]")
                else:
                    same += 1
            # a design migrated to a new parameter name may still carry the old one
            removed = []
            for s in results:
                lg = s.rule.legacy
                if lg and lg != s.parameter and state.has_param(s.parameter) and state.has_param(lg):
                    if params.remove_if_unused(state.design, lg):
                        removed.append(lg)
            _save_settings(state.settings)
            msg = [f"Wrote {len(changed)} changed parameter(s); {same} already matched."]
            if removed:
                msg.append("Removed unused legacy parameter(s): " + ", ".join(removed))
            msg.extend(changed[:30])
            if len(changed) > 30:
                msg.append(f"... and {len(changed) - 30} more")
            if kept:
                msg.append("\nKept as is: " + ", ".join(kept))
            if skipped:
                msg.append("\nSkipped (no tool / missing parameter): " + ", ".join(skipped))
            app.userInterface.messageBox("\n".join(msg), "ToolSnap")
        except Exception:
            ui.report_error(app.userInterface, "Snap to Tools failed while writing parameters")


_created = None


def start(user_interface, panel):
    global _created
    _created = Created()
    ui.add_button(user_interface, panel, CMD_ID, "Snap to Tools",
                  "Snap clearance holes, tap drills and counterbore diameters to the drills "
                  "and endmills in the shop inventory, then write them to user parameters.", _created,
                  promoted=True)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
