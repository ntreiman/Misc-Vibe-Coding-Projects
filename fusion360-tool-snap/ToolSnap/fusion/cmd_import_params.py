"""'Import Parameters' command: create the fastener parameter set (ISO 273
fits, tap drills, head geometry, derived counterbore/countersink expressions)
in the active design from the bundled Fusion parameter CSV."""

import adsk.core

from ..core import paramcsv
from . import params, ui

CMD_ID = "ToolSnap_ImportParams"


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            rows = paramcsv.load(ui.PARAMS_CSV_PATH)
            inputs.addTextBoxCommandInput(
                "info", "",
                f"Creates any of the {len(rows)} fastener parameters missing from this design "
                "and applies their expressions (counterbore depths, countersink chamfers...).\n"
                f"Source: {ui.PARAMS_CSV_PATH}", 4, True)
            inputs.addBoolValueInput("overwrite", "Reset existing literal values to the CSV",
                                     True, "", False)
            inputs.addBoolValueInput("snap_after", "Run Snap to Tools afterwards", True, "", True)
            h = Execute()
            cmd.execute.add(h)
            ui.handlers.append(h)
        except Exception:
            ui.report_error(adsk.core.Application.get().userInterface, "Import Parameters failed to open")


class Execute(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            design = ui.active_design(app)
            inputs = args.command.commandInputs
            rows = paramcsv.load(ui.PARAMS_CSV_PATH)
            stats = params.import_rows(design, rows, inputs.itemById("overwrite").value)
            msg = (f"Parameters: {stats['created']} created, {stats['updated']} updated, "
                   f"{stats['unchanged']} unchanged.")
            if inputs.itemById("snap_after").value:
                from . import cmd_snap
                app.userInterface.commandDefinitions.itemById(cmd_snap.CMD_ID).execute()
            else:
                app.userInterface.messageBox(msg, "ToolSnap")
        except Exception:
            ui.report_error(app.userInterface, "Import Parameters failed")


_created = None


def start(user_interface, panel):
    global _created
    _created = Created()
    ui.add_button(user_interface, panel, CMD_ID, "Import Parameters",
                  "Create the fastener parameter set (ISO fits, tap drills, head sizes, "
                  "counterbore & countersink expressions) in this design.", _created)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
