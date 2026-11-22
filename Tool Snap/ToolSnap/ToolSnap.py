"""ToolSnap - Fusion 360 add-in entry point.

Adds a TOOL SNAP panel to the Design > Solid tab:

* Snap to Tools       - (the icon) compute every tool-driven parameter and write it
* Add Shop Tool       - record a new drill / endmill in the shop inventory
* Shop Tools          - browse / filter / retire tools, export the sheet-format CSVs
* Add Fastener Size   - create the parameters for another metric size (M8, M12...)
* Import Parameters   - create the base fastener parameter set in a fresh design

All the snapping logic lives in ``core/`` (pure Python, unit-tested); the
``fusion/`` package only talks to the Fusion API.
"""

import traceback

import adsk.core

from .fusion import ui
from .fusion import cmd_snap, cmd_add_tool, cmd_shop_tools, cmd_add_size, cmd_import_params

_app = None
_ui = None
# Snap to Tools is the panel's icon; the rest sit in its drop-down, in this order.
COMMANDS = (cmd_snap, cmd_add_tool, cmd_shop_tools, cmd_add_size, cmd_import_params)


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        panel = ui.ensure_panel(_ui)
        for cmd in COMMANDS:
            cmd.start(_ui, panel)
    except Exception:
        if _ui:
            _ui.messageBox("ToolSnap failed to start:\n" + traceback.format_exc())


def stop(context):
    try:
        for cmd in COMMANDS:
            cmd.stop(_ui)
        ui.remove_panel(_ui)
    except Exception:
        if _ui:
            _ui.messageBox("ToolSnap failed to stop cleanly:\n" + traceback.format_exc())
