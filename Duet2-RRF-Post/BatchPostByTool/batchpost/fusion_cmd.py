"""Fusion API side of Batch Post by Tool: toolbar buttons, setup selection, posting."""

import os
import time
import traceback

import adsk.core
import adsk.cam

from . import core
from . import settings

WORKSPACE_ID = "CAMEnvironment"
PANEL_ID = "DuetBatchPostPanel"
PANEL_NAME = "DUET POST"
CMD_POST_ID = "DuetBatchPost_Run"
CMD_SETTINGS_ID = "DuetBatchPost_Settings"
TITLE = "Batch Post by Tool"

handlers = []   # Fusion drops event handlers that are garbage collected
_panels = []


# ----------------------------------------------------------------------------- toolbar

def _cam_tab(ui):
    ws = ui.workspaces.itemById(WORKSPACE_ID)
    if not ws:
        raise RuntimeError("Manufacture workspace not found.")
    tabs = ws.toolbarTabs
    for wanted in ("MillingTab", "UtilitiesTab"):
        tab = tabs.itemById(wanted)
        if tab:
            return tab
    return tabs.item(0)


def _ensure_panel(ui):
    tab = _cam_tab(ui)
    panel = tab.toolbarPanels.itemById(PANEL_ID)
    if not panel:
        panel = tab.toolbarPanels.add(PANEL_ID, PANEL_NAME)
    return panel


def _add_button(ui, panel, cmd_id, name, tooltip, handler, promoted):
    cmd_def = ui.commandDefinitions.itemById(cmd_id)
    if cmd_def:
        cmd_def.deleteMe()
    cmd_def = ui.commandDefinitions.addButtonDefinition(cmd_id, name, tooltip)
    cmd_def.commandCreated.add(handler)
    handlers.append(handler)
    control = panel.controls.itemById(cmd_id)
    if control:
        control.deleteMe()
    control = panel.controls.addCommand(cmd_def)
    control.isPromoted = promoted
    control.isPromotedByDefault = promoted


def start(ui):
    panel = _ensure_panel(ui)
    _add_button(ui, panel, CMD_POST_ID, "Batch Post by Tool",
                "Post every consecutive run of same-tool operations in the setup to its own G-code file "
                "(op_<tool>_<diameter>_<type>_<rpm>RPM.gcode) with the Duet 2 / RRF 2.05.1 post.",
                PostCreated(), True)
    _add_button(ui, panel, CMD_SETTINGS_ID, "Batch Post Settings",
                "Output folder and post file used by Batch Post by Tool.", SettingsCreated(), False)


def stop(ui):
    if not ui:
        return
    for cmd_id in (CMD_POST_ID, CMD_SETTINGS_ID):
        try:
            panel = _cam_tab(ui).toolbarPanels.itemById(PANEL_ID)
            if panel:
                control = panel.controls.itemById(cmd_id)
                if control:
                    control.deleteMe()
        except Exception:
            pass
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        if cmd_def:
            cmd_def.deleteMe()
    try:
        panel = _cam_tab(ui).toolbarPanels.itemById(PANEL_ID)
        if panel:
            panel.deleteMe()
    except Exception:
        pass


def _report(ui, title):
    ui.messageBox("%s\n\n%s" % (title, traceback.format_exc()), TITLE)


# ----------------------------------------------------------------------------- CAM access

def _active_cam(app):
    cam = adsk.cam.CAM.cast(app.activeProduct)
    if not cam:
        raise RuntimeError("Switch to the Manufacture workspace of a document with CAM setups first.")
    return cam


def _milling_setups(cam):
    result = []
    for i in range(cam.setups.count):
        s = cam.setups.item(i)
        try:
            if s.operationType != adsk.cam.OperationTypes.MillingOperation:
                continue
        except Exception:
            pass
        result.append(s)
    return result


def _param_value(params, name):
    try:
        p = params.itemByName(name)
        if p is None:
            return None
        v = p.value
        return getattr(v, "value", v)
    except Exception:
        return None


def _tool_number(op):
    """Tool number of an operation, or None when it has no tool."""
    for getter in (
        lambda: _param_value(op.tool.parameters, "tool_number"),
        lambda: _param_value(op.parameters, "tool_number"),
    ):
        try:
            v = getter()
        except Exception:
            v = None
        if v is not None:
            try:
                return int(round(float(v)))
            except (TypeError, ValueError):
                continue
    return None


def _op_infos(setup):
    infos = []
    ops = setup.allOperations
    for i in range(ops.count):
        op = ops.item(i)
        try:
            if not isinstance(op, adsk.cam.Operation):
                continue  # folders, patterns
        except Exception:
            pass
        suppressed = bool(getattr(op, "isSuppressed", False))
        infos.append(core.OpInfo(name=op.name, tool_number=_tool_number(op), handle=op, suppressed=suppressed))
    return infos


def _ensure_toolpaths(cam, groups, ui):
    missing = adsk.core.ObjectCollection.create()
    for g in groups:
        for info in g.ops:
            op = info.handle
            try:
                ok = op.hasToolpath and op.isToolpathValid
            except Exception:
                ok = getattr(op, "hasToolpath", True)
            if not ok:
                missing.add(op)
    if missing.count == 0:
        return
    future = cam.generateToolpath(missing)
    start = time.time()
    while not future.isGenerationCompleted:
        adsk.doEvents()
        if time.time() - start > 600:
            raise RuntimeError("Toolpath generation did not finish within 10 minutes.")


def _value_input(value):
    if isinstance(value, bool):
        return adsk.core.ValueInput.createByBoolean(value)
    if isinstance(value, (int, float)):
        return adsk.core.ValueInput.createByReal(float(value))
    return adsk.core.ValueInput.createByString(str(value))


def _post_group(cam, group, post_path, out_folder):
    coll = adsk.core.ObjectCollection.create()
    for info in group.ops:
        coll.add(info.handle)
    units = adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput
    post_input = adsk.cam.PostProcessInput.create(group.program_name, post_path, out_folder, units)
    post_input.isOpenInEditor = False
    try:
        props = adsk.core.NamedValues.create()
        for name, value in core.post_property_overrides(group).items():
            props.add(name, _value_input(value))
        post_input.postProperties = props
    except Exception:
        # Older API without postProperties: the post's own saved defaults apply (descriptive name on, redirect method).
        pass
    return cam.postProcess(coll, post_input)


def _new_gcode_files(folder, since):
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for n in names:
        p = os.path.join(folder, n)
        if n.lower().endswith(".gcode") and os.path.getmtime(p) >= since - 1:
            out.append(n)
    return out


def run_batch(app, ui, setup):
    cam = _active_cam(app)
    cfg = settings.load()
    out_folder = settings.resolve_output_folder(cfg)
    post_path = settings.resolve_post_path(cfg, cam.personalPostFolder)
    if not os.path.isfile(post_path):
        raise RuntimeError("Post not found:\n%s\n\nCopy Duet2Ethernet_RRF2051.cps there or set the path in Batch Post Settings." % post_path)
    if not os.path.isdir(out_folder):
        os.makedirs(out_folder)

    groups = core.group_consecutive(_op_infos(setup))
    if not groups:
        raise RuntimeError("Setup '%s' has no operations with a tool." % setup.name)
    _ensure_toolpaths(cam, groups, ui)

    started = time.time()
    failed = []
    for g in groups:
        ok = _post_group(cam, g, post_path, out_folder)
        if not ok:
            failed.append(g)
    time.sleep(0.2)
    files = _new_gcode_files(out_folder, started)
    lines = ["Setup: %s" % setup.name, "Output folder: %s" % out_folder, ""]
    lines += core.summary_lines(groups)
    lines += ["", "Files written (%d):" % len(files)] + ["  " + f for f in files]
    if failed:
        lines += ["", "FAILED to post: " + ", ".join("T%d" % g.tool_number for g in failed)]
    lines += ["", "The temporary run##_T#.gcode files are removed a few seconds after each post."]
    ui.messageBox("\n".join(lines), TITLE)
    if cfg.get("open_folder_when_done"):
        try:
            import subprocess
            import sys
            if sys.platform == "darwin":
                subprocess.Popen(["open", out_folder])
            elif sys.platform.startswith("win"):
                os.startfile(out_folder)  # noqa
        except Exception:
            pass


# ----------------------------------------------------------------------------- Batch Post command

class PostCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface
        try:
            cmd = args.command
            cam = _active_cam(app)
            setups = _milling_setups(cam)
            if not setups:
                raise RuntimeError("This document has no milling setup.")
            if len(setups) > 1:
                dd = cmd.commandInputs.addDropDownCommandInput(
                    "setup", "Setup", adsk.core.DropDownStyles.TextListDropDownStyle)
                for i, s in enumerate(setups):
                    dd.listItems.add(s.name, i == 0)
                cmd.commandInputs.addTextBoxCommandInput(
                    "hint", "", "Every consecutive run of operations sharing a tool becomes one file.", 2, True)
            # with a single setup no inputs are added, so Fusion executes the command without a dialog
            h = PostExecute(setups)
            cmd.execute.add(h)
            handlers.append(h)
        except Exception:
            _report(ui, "Batch Post by Tool could not start")


class PostExecute(adsk.core.CommandEventHandler):
    def __init__(self, setups):
        super().__init__()
        self._setups = setups

    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface
        try:
            setup = self._setups[0]
            dd = args.command.commandInputs.itemById("setup") if args.command.commandInputs.count else None
            if dd is not None:
                for s in self._setups:
                    if s.name == dd.selectedItem.name:
                        setup = s
                        break
            run_batch(app, ui, setup)
        except Exception:
            _report(ui, "Batch Post by Tool failed")


# ----------------------------------------------------------------------------- Settings command

class SettingsCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface
        try:
            cmd = args.command
            cfg = settings.load()
            inputs = cmd.commandInputs
            inputs.addStringValueInput("output_folder", "Output folder", cfg.get("output_folder") or "")
            inputs.addStringValueInput("post_path", "Post file (.cps)", cfg.get("post_path") or "")
            inputs.addBoolValueInput("open_folder", "Open folder when done", True, "", bool(cfg.get("open_folder_when_done")))
            try:
                cam = _active_cam(app)
                default_post = os.path.join(cam.personalPostFolder, settings.POST_FILENAME)
            except Exception:
                default_post = "<personal posts folder>/" + settings.POST_FILENAME
            inputs.addTextBoxCommandInput(
                "hint", "",
                "Leave a field empty for the default: output folder = ~/Downloads, post = %s" % default_post, 3, True)
            h = SettingsExecute()
            cmd.execute.add(h)
            handlers.append(h)
        except Exception:
            _report(ui, "Batch Post Settings could not open")


class SettingsExecute(adsk.core.CommandEventHandler):
    def notify(self, args):
        ui = adsk.core.Application.get().userInterface
        try:
            inputs = args.command.commandInputs
            cfg = settings.load()
            cfg["output_folder"] = inputs.itemById("output_folder").value.strip()
            cfg["post_path"] = inputs.itemById("post_path").value.strip()
            cfg["open_folder_when_done"] = inputs.itemById("open_folder").value
            settings.save(cfg)
        except Exception:
            _report(ui, "Batch Post Settings failed to save")
