"""'Add Shop Tool' command: append a drill / endmill to shop_tools.json."""

import adsk.core

from ..core import inventory
from . import ui

CMD_ID = "ToolSnap_AddTool"


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            kind = inputs.addDropDownCommandInput("kind", "Tool type",
                                                  adsk.core.DropDownStyles.TextListDropDownStyle)
            kind.listItems.add("Endmill", True)
            kind.listItems.add("Drill", False)
            unit = inputs.addDropDownCommandInput("unit", "Diameter unit",
                                                  adsk.core.DropDownStyles.TextListDropDownStyle)
            unit.listItems.add("mm", True)
            unit.listItems.add("in", False)
            # plain number so the user types what is printed on the tool,
            # in the unit chosen above (no Fusion unit conversion surprises)
            inputs.addStringValueInput("dia", "Diameter", "")
            inputs.addStringValueInput("name", "Name (optional)", "")
            inputs.addTextBoxCommandInput("hint", "",
                                          'Name defaults to the size, e.g. "10 mm" or "7/16". '
                                          "Re-adding an existing name replaces it.", 2, True)
            inputs.addBoolValueInput("avail", "Available", True, "", True)
            for ev, h in ((cmd.execute, Execute()), (cmd.validateInputs, Validate())):
                ev.add(h)
                ui.handlers.append(h)
        except Exception:
            ui.report_error(adsk.core.Application.get().userInterface, "Add Shop Tool failed to open")


def _read(inputs):
    kind = inputs.itemById("kind").selectedItem.name.lower()
    unit = inputs.itemById("unit").selectedItem.name
    dia_text = inputs.itemById("dia").value.strip()
    name = inputs.itemById("name").value
    avail = inputs.itemById("avail").value
    return kind, unit, _parse_dia(dia_text), name, avail


def _parse_dia(text):
    """Accept '10', '0.4375' or a fraction like '7/16'."""
    if "/" in text:
        num, den = text.split("/", 1)
        return float(num) / float(den)
    return float(text)


class Validate(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            _, _, dia, _, _ = _read(args.inputs)
            args.areInputsValid = dia > 0
        except Exception:  # noqa: BLE001
            args.areInputsValid = False


class Execute(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            kind, unit, dia, name, avail = _read(args.command.commandInputs)
            if "/" in args.command.commandInputs.itemById("dia").value and not name:
                name = args.command.commandInputs.itemById("dia").value.strip()
            tools = inventory.load(ui.TOOLS_PATH)
            tools = inventory.add_tool(tools, name, kind, dia, unit, available=avail)
            inventory.save(ui.TOOLS_PATH, tools)
            added = tools[-1]
            app.userInterface.messageBox(
                f"Added {added.type} \"{added.name}\" = {added.diameter_mm:g} mm to the shop inventory.\n"
                "Run Snap to Tools to update the parameters.", "ToolSnap")
        except Exception:
            ui.report_error(app.userInterface, "Add Shop Tool failed")


_created = None


def start(user_interface, panel):
    global _created
    _created = Created()
    ui.add_button(user_interface, panel, CMD_ID, "Add Shop Tool",
                  "Record a new drill or endmill in the shop inventory (shop_tools.json).", _created)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
