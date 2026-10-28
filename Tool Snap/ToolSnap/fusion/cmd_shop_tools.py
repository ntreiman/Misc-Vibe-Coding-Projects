"""'Shop Tools' command: browse, filter and sort the inventory, retire /
restore tools (singly or in bulk), see which hole parameters each tool is
picked for and the gap to the next available size, and export the inventory
as CSVs in the Google Sheet's Drill Library / Endmill Library format."""

from typing import Dict, List, Tuple

import adsk.core

from ..core import inventory, library_view as lv, rules, standards
from ..core.snap import Tool
from . import params, ui

CMD_ID = "ToolSnap_ShopTools"
TYPES = (("All tools", "all"), ("Drills", "drill"), ("Endmills", "endmill"))
SYSTEMS = (("All", "all"), ("Imperial", "imperial"), ("Metric", "metric"))
AVAIL = (("All", "all"), ("Available", "available"), ("Retired", "retired"))
UNITS = (("mm and inches", "both"), ("millimetres", "mm"), ("inches", "in"))
BULK = ("—", "Mark all shown AVAILABLE", "Mark all shown RETIRED")
N_COLS = 8
RATIO = "2:2:2:2:2:2:4:2"


class State:
    def __init__(self, tools: List[Tool], used_for: Dict[Tuple[str, str], List[str]]):
        self.tools = sorted(tools, key=lambda t: (t.type, t.diameter_mm))
        self.used_for = used_for
        self.avail = {(t.type, t.name): t.available for t in self.tools}   # edited in the dialog
        self.row_ids: List[str] = []
        self.checkbox_key: Dict[str, Tuple[str, str]] = {}
        self.counter = 0
        self.shown: List[lv.Row] = []
        self.inputs = None   # the dialog's top-level CommandInputs (inputChanged only hands us a group's)


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


def _dropdown(inputs, cid, name, items, selected=0):
    dd = inputs.addDropDownCommandInput(cid, name, adsk.core.DropDownStyles.TextListDropDownStyle)
    for i, item in enumerate(items):
        dd.listItems.add(item[0] if isinstance(item, tuple) else item, i == selected)
    return dd


def _value_of(dd, items):
    return items[dd.selectedItem.index][1]


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            cmd = args.command
            cmd.okButtonText = "Save"
            cmd.setDialogMinimumSize(820, 620)
            inputs = cmd.commandInputs
            tools = inventory.load(ui.TOOLS_PATH)
            state = State(tools, _used_for(app))
            state.inputs = inputs

            grp = inputs.addGroupCommandInput("filters", "Filter")
            grp.isExpanded = True
            f = grp.children
            _dropdown(f, "type", "Type", TYPES)
            _dropdown(f, "system", "System", SYSTEMS)
            series = f.addDropDownCommandInput("series", "Series", adsk.core.DropDownStyles.CheckBoxDropDownStyle)
            for name in sorted({lv.series_of(t) for t in tools}):
                series.listItems.add(name, True)
            _dropdown(f, "avail", "Availability", AVAIL)
            f.addStringValueInput("dmin", "Ø min", "")
            f.addStringValueInput("dmax", "Ø max", "")
            f.addStringValueInput("near", "Near Ø (closest 4 each side)", "")
            f.addStringValueInput("search", "Search (name / series)", "")
            f.addBoolValueInput("used_only", "Only tools a hole snaps to", True, "", False)

            grp = inputs.addGroupCommandInput("display", "Display")
            grp.isExpanded = True
            d = grp.children
            _dropdown(d, "units", "Units", UNITS)
            _dropdown(d, "sort", "Sort", [(lv.SORT_LABELS[s], s) for s in lv.SORTS])
            _dropdown(d, "bulk", "Shown tools →", BULK)

            table = inputs.addTableCommandInput("table", "Inventory", N_COLS, RATIO)
            table.maximumVisibleRows = 20
            table.minimumVisibleRows = 6
            inputs.addTextBoxCommandInput("status", "", "", 2, True)
            inputs.addBoolValueInput("export", "Export CSVs on Save (Drill Library / Endmill Library)",
                                     True, "", False)
            inputs.addTextBoxCommandInput(
                "info", "", "Untick Available to retire a tool without deleting it; Save persists. "
                "Step ↑ is the gap to the next larger available tool of the same type - big steps "
                "are the holes in your library. Export writes one CSV per Google Sheet tab.", 3, True)

            for ev, h in ((cmd.inputChanged, Changed(state)), (cmd.execute, Execute(state))):
                ev.add(h)
                ui.handlers.append(h)
            rebuild(inputs, state)
        except Exception:
            ui.report_error(app.userInterface, "Shop Tools failed to open")


def _num(text: str):
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        if "/" in text:
            a, b = text.split("/", 1)
            return float(a) / float(b)
        return float(text)
    except (ValueError, ZeroDivisionError):
        return None


def criteria(inputs) -> Tuple[lv.Criteria, str]:
    units = _value_of(inputs.itemById("units"), UNITS)
    entry_units = "in" if units == "in" else "mm"       # Ø min / max / near are typed in this unit
    series_dd = inputs.itemById("series")
    chosen = {series_dd.listItems.item(i).name for i in range(series_dd.listItems.count)
              if series_dd.listItems.item(i).isSelected}
    all_series = series_dd.listItems.count == len(chosen)
    c = lv.Criteria(
        tool_type=_value_of(inputs.itemById("type"), TYPES),
        system=_value_of(inputs.itemById("system"), SYSTEMS),
        series=None if all_series else chosen,
        availability=_value_of(inputs.itemById("avail"), AVAIL),
        dmin_mm=lv.to_mm(_num(inputs.itemById("dmin").value), entry_units),
        dmax_mm=lv.to_mm(_num(inputs.itemById("dmax").value), entry_units),
        near_mm=lv.to_mm(_num(inputs.itemById("near").value), entry_units),
        search=inputs.itemById("search").value.strip(),
        used_only=inputs.itemById("used_only").value,
        sort=lv.SORTS[inputs.itemById("sort").selectedItem.index],
    )
    return c, units


def _headers(units: str):
    if units == "both":
        return ("Size", "Type", "Ø mm", "Ø in", "Series", "Step ↑", "Used for", "Available")
    u = "mm" if units == "mm" else "in"
    return ("Size", "Type", f"Ø {u}", "Next ↑", "Series", f"Step ↑ {u}", "Used for", "Available")


def rebuild(inputs, state: State) -> None:
    table = inputs.itemById("table")
    table.clear()
    for cid in state.row_ids:
        old = inputs.itemById(cid)
        if old:
            old.deleteMe()
    state.row_ids = []
    state.checkbox_key = {}
    c, units = criteria(inputs)
    rows = lv.build(state.tools, state.avail, state.used_for, c)
    state.shown = rows

    def text_cell(text, row, col, tooltip=""):
        state.counter += 1
        cell = inputs.addStringValueInput(f"s{state.counter}", "", text)
        cell.isReadOnly = True
        if tooltip:
            cell.tooltip = tooltip
        table.addCommandInput(cell, row, col)
        state.row_ids.append(cell.id)

    for col, title in enumerate(_headers(units)):
        text_cell(title, 0, col)
    r = 1
    last_group = None
    for row in rows:
        t = row.tool
        if c.sort == "series" and lv.group_title(row) != last_group:
            last_group = lv.group_title(row)
            state.counter += 1
            cell = inputs.addStringValueInput(f"s{state.counter}", "", f"——  {last_group}  ——")
            cell.isReadOnly = True
            table.addCommandInput(cell, r, 0, 1, N_COLS)
            state.row_ids.append(cell.id)
            r += 1
        step = "—" if row.step_up_mm is None else ("+" + lv.fmt(row.step_up_mm, "in" if units == "in" else "mm"))
        nxt = inventory.label(row.next_up) if row.next_up else "—"
        used = ", ".join(row.used_for)
        if units == "both":
            cells = (inventory.label(t), t.type, lv.fmt(t.diameter_mm, "mm"), lv.fmt(t.diameter_mm, "in"),
                     row.series, step, used)
            tips = ("", "", "", "", "", f"next available: {nxt}", used)
        else:
            cells = (inventory.label(t), t.type, lv.fmt(t.diameter_mm, units), nxt, row.series, step, used)
            tips = ("", "", lv.fmt(t.diameter_mm, "in" if units == "mm" else "mm") + (" in" if units == "mm" else " mm"),
                    "", "", "", used)
        for col, (text, tip) in enumerate(zip(cells, tips)):
            text_cell(text, r, col, tip)
        state.counter += 1
        chk = inputs.addBoolValueInput(f"a{state.counter}", "Available", True, "", row.available)
        state.checkbox_key[chk.id] = (t.type, t.name)
        table.addCommandInput(chk, r, 7)
        state.row_ids.append(chk.id)
        r += 1
    inputs.itemById("status").text = lv.summary(rows, state.tools, state.avail) + (
        f"  Ø min / max / near are in {'inches' if units == 'in' else 'mm'}.")


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            cid = args.input.id
            st = self.state
            if cid in st.checkbox_key:
                st.avail[st.checkbox_key[cid]] = args.input.value
                return
            # an input inside a group reports the group's children as args.inputs;
            # always rebuild from the dialog's top-level collection
            inputs = st.inputs
            if cid == "bulk":
                choice = args.input.selectedItem.index
                if choice:
                    for row in st.shown:
                        st.avail[(row.tool.type, row.tool.name)] = (choice == 1)
                    args.input.listItems.item(0).isSelected = True
                    rebuild(inputs, st)
                return
            if cid in ("type", "system", "series", "avail", "dmin", "dmax", "near", "search",
                       "used_only", "units", "sort"):
                rebuild(inputs, st)
        except Exception:
            ui.report_error(adsk.core.Application.get().userInterface, "Shop Tools filter failed")


class Execute(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            inputs = self.state.inputs or args.command.commandInputs
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
                  "Browse, filter and sort the shop inventory, retire/restore tools, see which holes "
                  "use each tool, and export CSVs matching the Google Sheet's library tabs.", _created)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
