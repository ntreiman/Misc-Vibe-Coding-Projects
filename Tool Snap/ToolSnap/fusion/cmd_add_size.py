"""'Add Size' command: create the parameters for another fastener size (M8
counterbores, an M7 clearance hole, an M12 tap drill...) from the standards
table, or for an endmill class (EM6 = the owned endmill nearest 6 mm, with
its radius and pocket corner radius).  Snap to Tools picks either up
automatically."""

import adsk.core

from ..core import standards
from . import params, ui

CMD_ID = "ToolSnap_AddSize"


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            cmd = args.command
            design = ui.active_design(app)
            cmd.okButtonText = "Create parameters"
            inputs = cmd.commandInputs
            names = ui.user_parameter_names(design)
            present = set(standards.sizes_in(names))
            present_em = set(standards.endmill_classes_in(names))
            kind = inputs.addDropDownCommandInput("kind", "Kind", adsk.core.DropDownStyles.TextListDropDownStyle)
            kind.listItems.add("Fastener size (M…)", True)
            kind.listItems.add("Endmill class (EM…)", False)
            new_first = standards.new_sizes_available(present)
            size_dd = inputs.addDropDownCommandInput("size", "Size",
                                                     adsk.core.DropDownStyles.TextListDropDownStyle)
            default = new_first[0] if new_first else sorted(standards.SIZES, key=standards.sort_key)[0]
            for key in sorted(standards.SIZES, key=standards.sort_key):
                label = standards.size_label(key) + ("   (in design)" if key in present else "")
                size_dd.listItems.add(label, key == default)
            em_dd = inputs.addDropDownCommandInput("emclass", "Endmill class",
                                                   adsk.core.DropDownStyles.TextListDropDownStyle)
            em_new = [k for k in standards.ENDMILL_CLASSES if k not in present_em]
            em_default = em_new[0] if em_new else standards.ENDMILL_CLASSES[0]
            for key in standards.ENDMILL_CLASSES:
                label = standards.size_label(key) + ("   (in design)" if key in present_em else "")
                em_dd.listItems.add(label, key == em_default)
            em_dd.isVisible = False
            inputs.addTextBoxCommandInput("fam_title", "", "Features to set up:", 1, True)
            for fam in standards.FAMILIES:
                inputs.addBoolValueInput(f"fam_{fam}", standards.FAMILY_LABELS[fam], True, "", True)
            inputs.addTextBoxCommandInput("info", "", "", 4, True)
            state = {"design": design, "present": present}
            for ev, h in ((cmd.inputChanged, Changed(state)), (cmd.execute, Execute(state))):
                ev.add(h)
                ui.handlers.append(h)
            _update(inputs, state)
        except Exception:
            ui.report_error(app.userInterface, "Add Fastener Size failed to open")


def _is_endmill(inputs) -> bool:
    return inputs.itemById("kind").selectedItem.index == 1


def _selected_key(inputs):
    if _is_endmill(inputs):
        label = inputs.itemById("emclass").selectedItem.name.split()[0]   # 'EM6'
        return "em" + label[2:].replace(".", "_")
    label = inputs.itemById("size").selectedItem.name.split()[0]
    return standards.size_key(label)


def _rows_for(inputs):
    key = _selected_key(inputs)
    if _is_endmill(inputs):
        return key, standards.endmill_rows([key])
    chosen = [f for f in standards.FAMILIES if inputs.itemById(f"fam_{f}").value]
    return key, (standards.param_rows([key], chosen) if chosen else [])


def _update(inputs, state):
    endmill = _is_endmill(inputs)
    inputs.itemById("size").isVisible = not endmill
    inputs.itemById("emclass").isVisible = endmill
    inputs.itemById("fam_title").isVisible = not endmill
    for fam in standards.FAMILIES:
        inputs.itemById(f"fam_{fam}").isVisible = not endmill
    key = _selected_key(inputs)
    if endmill:
        rows = standards.endmill_rows([key])
        existing = set(ui.user_parameter_names(state["design"]))
        new = [r.name for r in rows if r.name not in existing]
        n = standards.sort_key(key)
        inputs.itemById("info").text = (
            f"{standards.size_label(key)} = the owned endmill nearest {n:g} mm. Creates {len(new)} new parameter(s): "
            f"{key}_nominal_dia (input), {key}_dia (tool-driven), {key}_radius and {key}_corner_radius "
            f"(= radius x corner_radius_factor) for pocket fillets.\nAfterwards run Snap to Tools.")
        return
    available = set(standards.families_for(key))
    chosen = []
    for fam in standards.FAMILIES:
        box = inputs.itemById(f"fam_{fam}")
        box.isEnabled = fam in available
        if fam not in available:
            box.value = False
        elif box.value:
            chosen.append(fam)
    rows = standards.param_rows([key], chosen) if chosen else []
    existing = set(ui.user_parameter_names(state["design"]))
    new = [r.name for r in rows if r.name not in existing]
    lines = [f"{standards.size_label(key)}: {len(new)} new parameter(s) will be created"
             f"{', ' + str(len(rows) - len(new)) + ' already exist and are left untouched' if len(rows) > len(new) else ''}."]
    unavailable = [standards.FAMILY_LABELS[f].split(' (')[0] for f in standards.FAMILIES if f not in available]
    if unavailable:
        lines.append("No standard head data for this size: " + ", ".join(unavailable) + ".")
    lines.append("Afterwards run Snap to Tools - the new size appears automatically.")
    inputs.itemById("info").text = "\n".join(lines)


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if args.input.id in ("kind", "size", "emclass") or args.input.id.startswith("fam_"):
                _update(args.inputs, self.state)
        except Exception:
            ui.report_error(adsk.core.Application.get().userInterface, "Add Fastener Size failed")


class Execute(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            inputs = args.command.commandInputs
            key, rows = _rows_for(inputs)
            if not rows:
                app.userInterface.messageBox("Nothing selected.", "ToolSnap")
                return
            stats = params.import_rows(self.state["design"], rows)
            app.userInterface.messageBox(
                f"{standards.size_label(key)}: {stats['created']} parameter(s) created, "
                f"{stats['unchanged'] + stats['updated']} already existed.\n\nNow run Snap to Tools.", "ToolSnap")
        except Exception:
            ui.report_error(app.userInterface, "Add Fastener Size failed")


_created = None


def start(user_interface, panel):
    global _created
    _created = Created()
    ui.add_button(user_interface, panel, CMD_ID, "Add Size",
                  "Create the parameters for another fastener size (clearance hole, tap drill, "
                  "counterbores, countersink) from ISO / DIN data, or for an endmill class "
                  "(nearest owned endmill, its radius and pocket corner radius).", _created)


def stop(user_interface):
    ui.remove_button(user_interface, CMD_ID)
