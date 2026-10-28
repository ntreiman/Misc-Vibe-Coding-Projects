"""'Shop Tools' command: browse and filter the inventory, retire / restore
tools, see which hole parameters each tool is picked for, and export the
inventory as CSVs in the Google Sheet's Drill Library / Endmill Library format."""

from typing import Dict, List, Tuple

import adsk.core

from ..core import inventory, rules, standards
from ..core.snap import Tool
from . import params, ui

CMD_ID = "ToolSnap_ShopTools"
TYPES = ("All", "Drills", "Endmills")
AVAIL = ("All", "Available", "Retired")
COLS = ("Size", "Type", "Ø mm", "Ø in", "Category", "Used for", "Available")
RATIO = "2:2:2:2:2:4:2"


class State:
    def __init__(self, tools: List[Tool], used_for: Dict[Tuple[str, str], List[str]]):
        self.tools = sorted(tools, key=lambda t: (t.type, t.diameter_mm))
        self.used_for = used_for
        self.avail = {(t.type, t.name): t.available for t in self.tools}   # edited in the dialog
        self.row_ids: List[str] = []          # input ids of the current table rows
        self.checkbox_key: Dict[str, Tuple[str, str]] = {}
        self.counter = 0


def _used_for(app) -> Dict[Tuple[str, str], List[str]]:
    """tool (type, name) -> hole parameters it is currently picked for."""
    try:
        design = ui.active_design(app)
        names = set(ui.user_parameter_names(design))
        ruleset = rules.load(ui.RULES_PATH)
        tools = inventory.load(ui.TOOLS_PATH)
        fit = ruleset.defaults.get("fit", "medium")
        out: Dict[Tuple[str, str], List[str]] = {}
        for s in rules.run(ruleset, tools, params.evaluator(design), fit, strict=False,
                           sizes=standards.sizes_in(names), has_param=names.__contains__):
            if s.ok and not s.kept:
                for name in s.result.tools:
                    out.setdefault((s.rule.tool, name), []).append(rules.short_name(s.parameter))
        return out
    except Exception:  # noqa: BLE001 - no design open, or not parametric: column stays empty
        return {}


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            cmd = args.command
            cmd.okButtonText = "Save"
            cmd.setDialogMinimumSize(760, 560)
            inputs = cmd.commandInputs
            tools = inventory.load(ui.TOOLS_PATH)
            state = State(tools, _used_for(app))

            dd = inputs.addDropDownCommandInput("type", "Type", adsk.core.DropDownStyles.TextListDropDownStyle)
            for i, n in enumerate(TYPES):
                dd.listItems.add(n, i == 0)
            cats = sorted({t.category for t in tools if t.category})
            dd = inputs.addDropDownCommandInput("cat", "Category", adsk.core.DropDownStyles.TextListDropDownStyle)
            dd.listItems.add("All", True)
            for c in cats:
                dd.listItems.add(c, False)
            dd = inputs.addDropDownCommandInput("avail", "Availability", adsk.core.DropDownStyles.TextListDropDownStyle)
            for i, n in enumerate(AVAIL):
                dd.listItems.add(n, i == 0)
            inputs.addStringValueInput("dmin", "Ø min (mm)", "")
            inputs.addStringValueInput("dmax", "Ø max (mm)", "")
            inputs.addStringValueInput("search", "Name contains", "")
            inputs.addBoolValueInput("used_only", "Only tools a hole snaps to", True, "", False)

            table = inputs.addTableCommandInput("table", "Inventory", len(COLS), RATIO)
            table.maximumVisibleRows = 20
            table.minimumVisibleRows = 6
            inputs.addTextBoxCommandInput("status", "", "", 2, True)
            inputs.addBoolValueInput("export", "Export CSVs on Save (Drill Library / Endmill Library)",
                                     True, "", False)
            inputs.addTextBoxCommandInput(
                "info", "", "Untick Available to retire a tool without deleting it; Save persists. "
                "Export writes one CSV per Google Sheet tab into a folder you choose.", 2, True)

            for ev, h in ((cmd.inputChanged, Changed(state)), (cmd.execute, Execute(state))):
                ev.add(h)
                ui.handlers.append(h)
            rebuild(inputs, state)
        except Exception:
            ui.report_error(app.userInterface, "Shop Tools failed to open")


def _num(text: str):
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def visible_tools(inputs, state: State) -> List[Tool]:
    which = inputs.itemById("type").selectedItem.index
    cat = inputs.itemById("cat").selectedItem.name
    av = inputs.itemById("avail").selectedItem.index
    dmin = _num(inputs.itemById("dmin").value)
    dmax = _num(inputs.itemById("dmax").value)
    search = inputs.itemById("search").value.strip().lower()
    used_only = inputs.itemById("used_only").value
    out = []
    for t in state.tools:
        if which == 1 and t.type != "drill" or which == 2 and t.type != "endmill":
            continue
        if cat != "All" and t.category != cat:
            continue
        available = state.avail[(t.type, t.name)]
        if av == 1 and not available or av == 2 and available:
            continue
        if dmin is not None and t.diameter_mm < dmin - 1e-9 or dmax is not None and t.diameter_mm > dmax + 1e-9:
            continue
        if search and search not in t.name.lower() and search not in inventory.label(t).lower():
            continue
        if used_only and (t.type, t.name) not in state.used_for:
            continue
        out.append(t)
    return out


def rebuild(inputs, state: State) -> None:
    table = inputs.itemById("table")
    table.clear()
    for cid in state.row_ids:
        old = inputs.itemById(cid)
        if old:
            old.deleteMe()
    state.row_ids = []
    state.checkbox_key = {}

    def add(cell, row, col):
        table.addCommandInput(cell, row, col)
        state.row_ids.append(cell.id)

    for c, title in enumerate(COLS):
        cell = inputs.addStringValueInput(f"h{state.counter}_{c}", title, title)
        cell.isReadOnly = True
        add(cell, 0, c)
    shown = visible_tools(inputs, state)
    for row, t in enumerate(shown, start=1):
        state.counter += 1
        n = state.counter
        used = ", ".join(state.used_for.get((t.type, t.name), []))
        texts = (inventory.label(t), t.type, f"{t.diameter_mm:.3f}", f"{t.diameter_mm / inventory.INCH_MM:.4f}",
                 t.category, used)
        for c, text in enumerate(texts):
            cell = inputs.addStringValueInput(f"c{n}_{c}", COLS[c], text)
            cell.isReadOnly = True
            if c == 5 and used:
                cell.tooltip = used
            add(cell, row, c)
        chk = inputs.addBoolValueInput(f"av{n}", "Available", True, "", state.avail[(t.type, t.name)])
        state.checkbox_key[chk.id] = (t.type, t.name)
        add(chk, row, 6)
    n_avail = sum(state.avail.values())
    inputs.itemById("status").text = (f"Showing {len(shown)} of {len(state.tools)} tools "
                                      f"({n_avail} available, {len(state.tools) - n_avail} retired).")


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            cid = args.input.id
            if cid in self.state.checkbox_key:
                self.state.avail[self.state.checkbox_key[cid]] = args.input.value
                return
            if cid in ("type", "cat", "avail", "dmin", "dmax", "search", "used_only"):
                rebuild(args.inputs, self.state)
        except Exception:
            ui.report_error(adsk.core.Application.get().userInterface, "Shop Tools filter failed")


class Execute(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            inputs = args.command.commandInputs
            tools = self.state.tools
            changed = 0
            for t in list(tools):
                want = self.state.avail[(t.type, t.name)]
                if want != t.available:
                    tools = inventory.set_available(tools, t.name, t.type, want)
                    changed += 1
            if changed:
                inventory.save(ui.TOOLS_PATH, tools)
            msg = [f"Availability changed on {changed} tool(s)." if changed else "No availability changes."]
            if inputs.itemById("export").value:
                dlg = app.userInterface.createFolderDialog()
                dlg.title = "Folder for Drill Library.csv and Endmill Library.csv"
                if dlg.showDialog() == adsk.core.DialogResults.DialogOK:
                    written = inventory.export_sheet_csvs(tools, dlg.folder)
                    msg.append("Exported:\n" + "\n".join(written.values()))
                else:
                    msg.append("Export cancelled.")
            app.userInterface.messageBox("\n".join(msg), "ToolSnap")
        except Exception:
            ui.report_error(app.userInterface, "Shop Tools failed")


_created = None


def start(user_interface, panel):
    global _created
    _created = Created()
    ui.add_button(user_interface, panel, CMD_ID, "Shop Tools",
                  "Browse and filter the shop inventory, retire/restore tools, see which holes use "
                  "each tool, and export CSVs matching the Google Sheet's library tabs.", _created)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
