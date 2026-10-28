"""'Shop Tools' command: browse the inventory, toggle availability, and export
it as CSVs in the Google Sheet's Drill Library / Endmill Library format."""

import adsk.core

from ..core import inventory

from . import ui

CMD_ID = "ToolSnap_ShopTools"
FILTERS = ("All tools", "Drills", "Endmills")
COLS = ("Name", "Type", "Ø mm", "Ø in", "Category", "Available")


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            cmd = args.command
            cmd.okButtonText = "Save"
            cmd.setDialogMinimumSize(640, 520)
            inputs = cmd.commandInputs
            tools = inventory.load(ui.TOOLS_PATH)

            flt = inputs.addDropDownCommandInput("filter", "Show",
                                                 adsk.core.DropDownStyles.TextListDropDownStyle)
            for i, name in enumerate(FILTERS):
                flt.listItems.add(name, i == 0)
            inputs.addBoolValueInput("avail_only", "Available only", True, "", False)

            table = inputs.addTableCommandInput("table", "Inventory", len(COLS), "3:2:2:2:2:2")
            table.maximumVisibleRows = 24
            table.minimumVisibleRows = 8
            for c, title in enumerate(COLS):
                cell = inputs.addStringValueInput(f"hdr_{c}", title, title)
                cell.isReadOnly = True
                table.addCommandInput(cell, 0, c)
            # one row per tool; filtering only hides rows so the checkboxes keep their state
            for i, t in enumerate(sorted(tools, key=lambda t: (t.type, t.diameter_mm))):
                row = i + 1
                texts = (t.name, t.type, f"{t.diameter_mm:.4f}", f"{t.diameter_mm / inventory.INCH_MM:.4f}",
                         t.category)
                for c, text in enumerate(texts):
                    cell = inputs.addStringValueInput(f"c{c}_{i}", COLS[c], text)
                    cell.isReadOnly = True
                    table.addCommandInput(cell, row, c)
                chk = inputs.addBoolValueInput(f"avail_{i}", "Available", True, "", t.available)
                table.addCommandInput(chk, row, 5)

            inputs.addBoolValueInput("export", "Export CSVs on Save (Drill Library / Endmill Library)",
                                     True, "", False)
            inputs.addTextBoxCommandInput(
                "info", "",
                f"{len(tools)} tools, {sum(t.available for t in tools)} available. "
                "Untick a tool to retire it without deleting it. Export writes one CSV per Google "
                "Sheet tab into a folder you choose.", 3, True)

            state = {"tools": sorted(tools, key=lambda t: (t.type, t.diameter_mm))}
            for ev, h in ((cmd.inputChanged, Changed(state)), (cmd.execute, Execute(state))):
                ev.add(h)
                ui.handlers.append(h)
            _apply_filter(inputs, state)
        except Exception:
            ui.report_error(app.userInterface, "Shop Tools failed to open")


def _apply_filter(inputs, state):
    which = inputs.itemById("filter").selectedItem.index   # 0 all, 1 drills, 2 endmills
    only_avail = inputs.itemById("avail_only").value
    for i, t in enumerate(state["tools"]):
        show = (which == 0 or (which == 1) == (t.type == "drill"))
        if only_avail and not inputs.itemById(f"avail_{i}").value:
            show = False
        for c in range(5):
            inputs.itemById(f"c{c}_{i}").isVisible = show
        inputs.itemById(f"avail_{i}").isVisible = show


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if args.input.id in ("filter", "avail_only"):
                _apply_filter(args.inputs, self.state)
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
            tools = self.state["tools"]
            changed = 0
            for i, t in enumerate(tools):
                want = inputs.itemById(f"avail_{i}").value
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
                  "Browse the shop inventory, retire/restore tools, and export it as CSVs "
                  "matching the Google Sheet's Drill Library and Endmill Library tabs.", _created)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
