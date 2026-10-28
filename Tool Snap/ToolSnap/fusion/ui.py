"""Small helpers shared by the commands: panel management, handler
bookkeeping and data-file locations."""

import os
import traceback

import adsk.core

WORKSPACE_ID = "FusionSolidEnvironment"
TAB_ID = "SolidTab"
PANEL_ID = "ToolSnapPanel"
PANEL_NAME = "TOOL SNAP"

ADDIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ADDIN_DIR, "data")
RULES_PATH = os.path.join(DATA_DIR, "snap_rules.json")
TOOLS_PATH = os.path.join(DATA_DIR, "shop_tools.json")
PARAMS_CSV_PATH = os.path.join(DATA_DIR, "fastener_parameters.csv")

# Event handlers must outlive the function that created them or Fusion
# silently drops them; every command appends its handlers here.
handlers = []


def ensure_panel(ui: adsk.core.UserInterface) -> adsk.core.ToolbarPanel:
    tab = ui.workspaces.itemById(WORKSPACE_ID).toolbarTabs.itemById(TAB_ID)
    panel = tab.toolbarPanels.itemById(PANEL_ID)
    if not panel:
        panel = tab.toolbarPanels.add(PANEL_ID, PANEL_NAME)
    return panel


def remove_panel(ui: adsk.core.UserInterface) -> None:
    if not ui:
        return
    tab = ui.workspaces.itemById(WORKSPACE_ID).toolbarTabs.itemById(TAB_ID)
    panel = tab.toolbarPanels.itemById(PANEL_ID)
    if panel:
        panel.deleteMe()


def add_button(ui: adsk.core.UserInterface, panel: adsk.core.ToolbarPanel,
               cmd_id: str, name: str, tooltip: str, created_handler) -> adsk.core.CommandDefinition:
    cmd_def = ui.commandDefinitions.itemById(cmd_id)
    if cmd_def:
        cmd_def.deleteMe()
    cmd_def = ui.commandDefinitions.addButtonDefinition(cmd_id, name, tooltip)
    cmd_def.commandCreated.add(created_handler)
    handlers.append(created_handler)
    control = panel.controls.itemById(cmd_id)
    if control:
        control.deleteMe()
    control = panel.controls.addCommand(cmd_def)
    control.isPromoted = True
    return cmd_def


def remove_button(ui: adsk.core.UserInterface, cmd_id: str) -> None:
    if not ui:
        return
    tab = ui.workspaces.itemById(WORKSPACE_ID).toolbarTabs.itemById(TAB_ID)
    panel = tab.toolbarPanels.itemById(PANEL_ID)
    if panel:
        control = panel.controls.itemById(cmd_id)
        if control:
            control.deleteMe()
    cmd_def = ui.commandDefinitions.itemById(cmd_id)
    if cmd_def:
        cmd_def.deleteMe()


def report_error(ui: adsk.core.UserInterface, title: str) -> None:
    ui.messageBox(f"{title}\n\n{traceback.format_exc()}", "ToolSnap")


def active_design(app: adsk.core.Application):
    import adsk.fusion
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise RuntimeError("Open a Design (not CAM/Drawing) before running ToolSnap.")
    return design
