"""BatchPostByTool - Fusion 360 add-in entry point.

Adds a DUET POST panel to the Manufacture workspace with two commands:

* Batch Post by Tool   - post every consecutive run of same-tool operations
                         of the setup to its own G-code file, using the
                         Duet2Ethernet_RRF2051 post with descriptive file
                         names (op_<tool>_<dia>_<type>_<rpm>RPM.gcode).
                         If the document has one setup it runs immediately;
                         with several it asks which one.
* Batch Post Settings  - output folder and post file used by the command.

Grouping logic lives in ``batchpost/core.py`` (pure Python, unit tested);
``batchpost/fusion_cmd.py`` is the only module that talks to the Fusion API.
"""

import traceback

import adsk.core

from .batchpost import fusion_cmd

_app = None
_ui = None


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        fusion_cmd.start(_ui)
    except Exception:
        if _ui:
            _ui.messageBox("BatchPostByTool failed to start:\n" + traceback.format_exc())


def stop(context):
    try:
        fusion_cmd.stop(_ui)
    except Exception:
        if _ui:
            _ui.messageBox("BatchPostByTool failed to stop cleanly:\n" + traceback.format_exc())
