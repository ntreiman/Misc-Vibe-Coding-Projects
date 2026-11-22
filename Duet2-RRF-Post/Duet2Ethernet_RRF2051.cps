/**
  Copyright (C) 2012-2018 by Autodesk, Inc.
  Copyright (C) 2021 by Bruce Royce  (UltimateRepRapPost, https://github.com/BruceRoyce/UltimateRepRapPost)
  Copyright (C) 2026 modifications for Duet 2 Ethernet / RepRapFirmware 2.05.1
  All rights reserved.

  Licensed under the Apache License, Version 2.0 (the "License"); you may not use this
  file except in compliance with the License. You may obtain a copy of the License at
  http://www.apache.org/licenses/LICENSE-2.0 . Distributed on an "AS IS" BASIS, WITHOUT
  WARRANTIES OR CONDITIONS OF ANY KIND. See the License for the specific language
  governing permissions and limitations under the License.

  NOTICE OF MODIFICATION (Apache 2.0, section 4b):
  This file is a modified version of UltimateRRPost.cps R1.5 (2021-03-17) by Bruce Royce.
  See CHANGELOG.md next to this file for the list of changes and the reasons for them.

  $R 2.7 $
  $Date: 2026-11-22 $
*/

description = "Duet 2 Ethernet / RRF 2.05.1 CNC (UltimateRepRapPost fork)";
vendor = "Duet3D RepRapFirmware";
vendorUrl = "https://docs.duet3d.com/User_manual/Reference/Gcodes";
legal = "Copyright (C) 2012-2018 by Autodesk, Inc. / (C) 2021 Bruce Royce / Apache License 2.0";
certificationLevel = 2;
minimumRevision = 24000;

longDescription = "Milling post for a 3-axis CNC running Duet 2 Ethernet with RepRapFirmware 2.05.1 in CNC mode (M453). " +
  "Fork of Bruce Royce's UltimateRepRapPost with corrected startup/tool-change retract sequencing, no G28 retracts, " +
  "G53 machine-coordinate tool-change position, configurable spindle dwell, and RRF 2.x compatible dwell/end-of-program codes.";

extension = "gcode";
setCodePage("ascii");

capabilities = CAPABILITY_MILLING;
tolerance = spatial(0.002, MM);

minimumChordLength = spatial(0.25, MM);
minimumCircularRadius = spatial(0.1, MM);
maximumCircularRadius = spatial(1000, MM);
minimumCircularSweep = toRad(0.1);
maximumCircularSweep = toRad(180);
allowHelicalMoves = true;
allowedCircularPlanes = (1 << PLANE_XY); // RRF 2.05.1 G2/G3 support XY arcs (optionally helical in Z) only

var groupNames = [
  "1- Safe Z and Retracts",
  "2- Workspace",
  "3- Spindle",
  "4- Tool Change",
  "5- Probes (after tool change)",
  "6- Operator Messages",
  "7- Formatting",
  "8- Linear Backlash Compensation"
];

// ---------------------------------------------------------------------------
// user-defined properties
// ---------------------------------------------------------------------------
properties = {
  // 1- Safe Z and Retracts
  retractMode: "wcs",          // "wcs": Fusion clearance height in the active WCS. "machine": G53 to safeMachineZ at program start, tool changes and WCS changes
  safeMachineZ: 0,             // MACHINE coordinate Z (G53) known to clear stock, clamps and fixtures. Used by "machine" retract mode, manual tool changes and end-of-program parking
  splitRapids: true,           // split combined XY+Z rapids: Z first when going up, XY first when going down
  endPosition: "retract",      // "retract": retract only. "park": retract to safe machine Z (G53) and move to the tool change XY

  // 2- Workspace
  useWhichWCS: "1",            // only if the Fusion setup WCS offset is 0: which G54..G59.3 to use
  startConfirmation: true,     // blocking M291 before any motion: operator confirms homed, zeroed, first tool mounted

  // 3- Spindle
  spindleDwellMode: "proportional", // "proportional" (upstream behaviour), "fixed", "none"
  spindleRPMCatchupTime6K: 15, // seconds for 0 -> 6000 RPM (proportional mode)
  spindleDwellFixedSeconds: 5, // seconds (fixed mode)
  spindleStopDwellSeconds: 10, // seconds to wait after M5 before moving to a tool change position / at program end

  // 4- Tool Change
  toolCallMode: "none",        // "none": no Tn (comment only). "fusion": T<fusion tool number>. "fixed": T<fixedToolNumber>
  fixedToolNumber: 0,
  manualToolChange: true,      // park with G53 and prompt the operator (M291 S3) at every tool change
  toolChangeXPos: 0,           // MACHINE coordinate X (G53) for tool changes
  toolChangeYPos: 0,           // MACHINE coordinate Y (G53) for tool changes
  homeOnToolChange: false,     // emit G28 (HOME ALL AXES in RRF) after the new tool is confirmed. Off unless you know your homeall.g is safe with a tool mounted

  // 5- Probes
  probeToolOnChange: "0",      // "0" none, "1" Z-probe plate (M585), "2" corner probe (M585). Both REWRITE the active WCS origin with G10 L20 and save it with M500
  probeZThickness: 3,
  probeZRetract: 5,
  probeZSafeInside: 5,         // XY distance inside the WCS origin corner where the Z plate is probed
  probe3dOnStart: false,
  probe3DPlacement: "0",
  probe3DLength: 50,
  probe3DWidth: 50,
  probe3DThickness: 5,
  probe3DRetract: 10,

  // 6- Operator Messages
  informationalMessages: true, // non-blocking M291 S0/S1 messages (operation names, dwell notices, program end)
  beepOn: true,                // M300 before prompts that need attention

  // 7- Formatting
  showSequenceNumbers: false,
  sequenceNumberStart: 10,
  sequenceNumberIncrement: 5,
  useRadius: true,             // arcs with R instead of I/J
  writeMachine: true,
  writeTools: true,
  writeVersion: true,
  endProgramM0: false,         // emit M0 as the last command. In RRF 2.05.1 M0 runs stop.g, disables all drives and flags every axis as NOT homed
  descriptiveFileName: true,   // write the program to op_<n>_<diameter>_<tool type>_<rpm>RPM.gcode (one block per tool)
  descriptiveFileNamePrefix: "op", // "op" (literal, before every tool number), "none", "operation" (operation names), "program" (program name/number)
  descriptiveFileMethod: "redirect", // "redirect": write a second file, keep the dialog-named file as a pointer. "rename": rename the dialog-named file at the end (one file, no overwrite prompt)

  // 8- Linear Backlash Compensation (unchanged from upstream apart from being OFF by default)
  applyBacklashCompensation: false,
  backlashCompensationMethod: "steps",
  backlashCompensationTolerance: 0.05,
  stepsPerUnitX: 400,
  stepsPerUnitY: 400,
  stepsPerUnitZ: 400,
  measuredBacklashXFor1mm: 0,
  measuredBacklashXFor10mm: 0,
  measuredBacklashYFor1mm: 0,
  measuredBacklashYFor10mm: 0,
  measuredBacklashZFor1mm: 0,
  measuredBacklashZFor10mm: 0
};

// user-defined property definitions
propertyDefinitions = {
  retractMode: {
    title: "Retract strategy for program start, tool changes and WCS changes",
    description: "WCS clearance: retract to the Fusion clearance height of the operation (in the active WCS) BEFORE any XY move. Requires that this height clears all clamps along the XY path. " +
      "Machine Z (G53): retract to 'Safe machine Z' in machine coordinates before XY moves, then descend to the Fusion clearance height over the start point. Requires a correct 'Safe machine Z'.",
    group: groupNames[0], type: "enum",
    values: [
      { title: "Fusion clearance height in active WCS", id: "wcs" },
      { title: "Safe machine Z with G53", id: "machine" }
    ]
  },
  safeMachineZ: {
    title: "Safe machine Z (G53, machine coordinates) - SET THIS",
    description: "Z in MACHINE coordinates (as shown by G53 / M114 machine position) that clears stock, clamps and fixtures with the longest tool mounted. Used for G53 retracts, manual tool change parking and end-of-program parking. The post cannot know your machine, there is no safe default.",
    group: groupNames[0], type: "number"
  },
  splitRapids: {
    title: "Split combined XY+Z rapids",
    description: "A rapid that changes Z and XY at once is output as two moves: Z first when moving up, XY first when moving down.",
    group: groupNames[0], type: "boolean"
  },
  endPosition: {
    title: "End of program position",
    description: "Retract only, or retract to Safe machine Z (G53) and park at the tool change XY (G53).",
    group: groupNames[0], type: "enum",
    values: [
      { title: "Retract only", id: "retract" },
      { title: "Park at tool change XY (G53)", id: "park" }
    ]
  },
  useWhichWCS: {
    title: "WCS when the Fusion setup WCS offset is 0",
    description: "Only used when the Fusion Setup has WCS offset 0 (unspecified). A non-zero setup WCS offset always wins: 1 = G54, 2 = G55 ... 7 = G59.1, 8 = G59.2, 9 = G59.3.",
    group: groupNames[1], type: "enum",
    values: [
      { title: "G54 (WCS 1)", id: "1" }, { title: "G55 (WCS 2)", id: "2" }, { title: "G56 (WCS 3)", id: "3" },
      { title: "G57 (WCS 4)", id: "4" }, { title: "G58 (WCS 5)", id: "5" }, { title: "G59 (WCS 6)", id: "6" },
      { title: "G59.1 (WCS 7)", id: "7" }, { title: "G59.2 (WCS 8)", id: "8" }, { title: "G59.3 (WCS 9)", id: "9" }
    ]
  },
  startConfirmation: {
    title: "Start confirmation prompt (blocking)",
    description: "Before any motion, show a blocking M291 (OK / Cancel) asking the operator to confirm the machine is homed, the WCS is set and the first tool is mounted. Cancel aborts the job.",
    group: groupNames[1], type: "boolean"
  },
  spindleDwellMode: {
    title: "Spindle start / speed change dwell",
    description: "Proportional: catch-up time per 6000 RPM of change, minimum 5 s (upstream behaviour). Fixed: always the fixed number of seconds. None: no dwell at all.",
    group: groupNames[2], type: "enum",
    values: [
      { title: "Proportional to RPM change", id: "proportional" },
      { title: "Fixed seconds", id: "fixed" },
      { title: "None", id: "none" }
    ]
  },
  spindleRPMCatchupTime6K: {
    title: "Spindle catch-up time for 6000 RPM (s)",
    description: "Proportional mode: seconds the spindle needs from 0 to 6000 RPM. Scaled for other RPM changes, doubled on a direction change.",
    group: groupNames[2], type: "number"
  },
  spindleDwellFixedSeconds: {
    title: "Fixed spindle dwell (s)",
    description: "Fixed mode: seconds to wait after every M3/M4 speed change.",
    group: groupNames[2], type: "number"
  },
  spindleStopDwellSeconds: {
    title: "Spindle stop dwell (s)",
    description: "Seconds to wait after M5 before moving to the tool change position and at program end. 0 disables.",
    group: groupNames[2], type: "number"
  },
  toolCallMode: {
    title: "Tn output",
    description: "RRF 2.05.1 drives the spindle with M3 S regardless of the selected tool. None: never output Tn (tool is written as a comment). Fusion number: output T<n> from the Fusion tool. Fixed: always output the fixed tool number (for a config.g that defines one spindle tool).",
    group: groupNames[3], type: "enum",
    values: [
      { title: "None (comment only)", id: "none" },
      { title: "Fusion tool number", id: "fusion" },
      { title: "Fixed tool number", id: "fixed" }
    ]
  },
  fixedToolNumber: {
    title: "Fixed tool number",
    description: "Used when Tn output is 'Fixed tool number'.",
    group: groupNames[3], type: "integer"
  },
  manualToolChange: {
    title: "Manual tool change",
    description: "At every tool change: M5, spindle stop dwell, G53 to Safe machine Z, G53 to tool change XY, M400, blocking M291 prompt (Cancel aborts). Requires Safe machine Z and tool change XY to be set.",
    group: groupNames[3], type: "boolean"
  },
  toolChangeXPos: {
    title: "Tool change X (G53 machine coordinate)",
    description: "Machine coordinate X of the tool change position.",
    group: groupNames[3], type: "number"
  },
  toolChangeYPos: {
    title: "Tool change Y (G53 machine coordinate)",
    description: "Machine coordinate Y of the tool change position.",
    group: groupNames[3], type: "number"
  },
  homeOnToolChange: {
    title: "Home all axes (G28) after tool change - CAUTION",
    description: "Emits G28 after the operator confirms the new tool. In RepRapFirmware G28 HOMES the machine (runs homeall.g). Only enable if your homing macros are safe to run with a tool mounted over the work.",
    group: groupNames[3], type: "boolean"
  },
  probeToolOnChange: {
    title: "Probe after each tool change",
    description: "Z-Probe: touch plate on the stock top, sets the active WCS Z with G10 L20 and saves with M500. Corner probe: XYZ corner block, sets X, Y and Z of the active WCS. Both REWRITE your WCS origin. Needs a probe wired to endstop input E0 (E3 in M585), active low.",
    group: groupNames[4], type: "enum",
    values: [
      { title: "No probe", id: "0" },
      { title: "Z-Probe plate", id: "1" },
      { title: "Corner probe", id: "2" }
    ]
  },
  probeZThickness: { title: "Z-Probe thickness (mm)", description: "Thickness of the Z touch plate.", group: groupNames[4], type: "number" },
  probeZRetract: { title: "Retract after Z-probe (mm)", description: "Relative Z lift after the Z probe to release the plate.", group: groupNames[4], type: "number" },
  probeZSafeInside: { title: "Z-Probe XY position inside origin (mm)", description: "The Z plate is probed at WCS X=Y=this value, i.e. this far inside the stock corner.", group: groupNames[4], type: "number" },
  probe3dOnStart: { title: "Corner probe at program start", description: "Runs the corner probe on the first tool before the first operation. First tool must be mounted.", group: groupNames[4], type: "boolean" },
  probe3DPlacement: {
    title: "Corner probe placement", description: "Stock corner the corner probe sits on.", group: groupNames[4], type: "enum",
    values: [
      { title: "Bottom-Left", id: "0" }, { title: "Top-Left", id: "1" }, { title: "Top-Right", id: "2" }, { title: "Bottom-Right", id: "3" }
    ]
  },
  probe3DLength: { title: "Corner probe length X (mm)", description: "How far the corner probe sticks out from the stock side in X.", group: groupNames[4], type: "number" },
  probe3DWidth: { title: "Corner probe width Y (mm)", description: "How far the corner probe sticks out from the stock side in Y.", group: groupNames[4], type: "number" },
  probe3DThickness: { title: "Corner probe thickness Z (mm)", description: "Thickness of the corner probe above the stock top.", group: groupNames[4], type: "number" },
  probe3DRetract: { title: "Retract after corner probe (mm)", description: "Distance to back off in each axis to release the corner probe.", group: groupNames[4], type: "number" },
  informationalMessages: {
    title: "Informational messages (non-blocking)",
    description: "Non-blocking M291 S0/S1 messages: current operation, spindle dwell notice, program end. Safety prompts (start confirmation, tool change, probe mounting) are always written.",
    group: groupNames[5], type: "boolean"
  },
  beepOn: { title: "Beep (M300) before prompts", description: "M300 before prompts that need the operator.", group: groupNames[5], type: "boolean" },
  showSequenceNumbers: { title: "Use sequence numbers", description: "N-numbers on every block.", group: groupNames[6], type: "boolean" },
  sequenceNumberStart: { title: "Start sequence number", description: "First N-number.", group: groupNames[6], type: "integer" },
  sequenceNumberIncrement: { title: "Sequence number increment", description: "N-number increment.", group: groupNames[6], type: "integer" },
  useRadius: { title: "Radius arcs", description: "Arcs with R instead of I/J. Arcs over 90 degrees are split.", group: groupNames[6], type: "boolean" },
  writeMachine: { title: "Write machine", description: "Machine settings in the header.", group: groupNames[6], type: "boolean" },
  writeTools: { title: "Write tool list", description: "Tool list in the header.", group: groupNames[6], type: "boolean" },
  writeVersion: { title: "Write version", description: "Post version in the header.", group: groupNames[6], type: "boolean" },
  descriptiveFileName: {
    title: "Descriptive output file name (tool number, diameter, type, RPM)",
    description: "Writes the program to op_<tool number>_<diameter>_<tool type>_<rpm>RPM.gcode in the output folder, one block per tool in order of use, e.g. op_1_6_spot_drill_5000RPM.gcode (see 'Descriptive file name prefix' for the prefix). The file named in the post dialog is still created and contains a single comment pointing to the real file (the Fusion kernel cannot rename its own output).",
    group: groupNames[6], type: "boolean"
  },
  descriptiveFileMethod: {
    title: "Descriptive file name method",
    description: "Redirect (default): the program is written to the descriptive file and the file named in the post dialog is kept with a one-line pointer, so Fusion asks to overwrite it on the next post. Single file: the program is written to the dialog-named file as usual, copied to the descriptive name once Fusion has finished writing it, and the dialog-named file is removed 3 seconds later by a small background script (so Fusion still finds it when it validates the post). One file, no overwrite prompt. Keep 'Open NC file in editor' unchecked with it.",
    group: groupNames[6], type: "enum",
    values: [
      { title: "Redirect (second file, keeps dialog-named file)", id: "redirect" },
      { title: "Single file (copy, then remove dialog-named file)", id: "rename" }
    ]
  },
  descriptiveFileNamePrefix: {
    title: "Descriptive file name prefix",
    description: "What goes in front of the tool number when 'Descriptive output file name' is on: 'op' before every tool number (op_1_..._op_2_...), nothing, the Fusion operation name(s), or the program name/number from the post dialog.",
    group: groupNames[6], type: "enum",
    values: [
      { title: "op (before every tool number)", id: "op" },
      { title: "None", id: "none" },
      { title: "Operation name(s)", id: "operation" },
      { title: "Program name/number", id: "program" }
    ]
  },
  endProgramM0: {
    title: "End program with M0 - CAUTION",
    description: "In RRF 2.05.1 M0 from the job file runs stop.g (if present), switches drives to idle and flags ALL axes as not homed. Leave off to let the file end normally with the motors holding position.",
    group: groupNames[6], type: "boolean"
  },
  applyBacklashCompensation: { title: "Apply Backlash Compensation", description: "Compensate for backlash on motion direction changes (upstream feature, unchanged).", group: groupNames[7], type: "boolean" },
  backlashCompensationMethod: {
    title: "Backlash Compensation Method",
    description: "Steps: rewrites M92 steps/mm around direction changes without altering coordinates. Distance: adds extra distance to the affected moves.",
    group: groupNames[7], type: "enum",
    values: [{ title: "Steps", id: "steps" }, { title: "Distance", id: "distance" }]
  },
  backlashCompensationTolerance: { title: "Accuracy tolerance", description: "Direction changes shorter than this do not trigger compensation.", group: groupNames[7], type: "number" },
  stepsPerUnitX: { title: "X steps per mm [Steps method]", description: "M92 X from config.g", group: groupNames[7], type: "number" },
  stepsPerUnitY: { title: "Y steps per mm [Steps method]", description: "M92 Y from config.g", group: groupNames[7], type: "number" },
  stepsPerUnitZ: { title: "Z steps per mm [Steps method]", description: "M92 Z from config.g", group: groupNames[7], type: "number" },
  measuredBacklashXFor1mm: { title: "X backlash for 1mm", description: "Measured shortfall on a 1mm X move after a direction change.", group: groupNames[7], type: "number" },
  measuredBacklashXFor10mm: { title: "X backlash for 10mm", description: "Measured shortfall on a 10mm X move after a direction change.", group: groupNames[7], type: "number" },
  measuredBacklashYFor1mm: { title: "Y backlash for 1mm", description: "Measured shortfall on a 1mm Y move after a direction change.", group: groupNames[7], type: "number" },
  measuredBacklashYFor10mm: { title: "Y backlash for 10mm", description: "Measured shortfall on a 10mm Y move after a direction change.", group: groupNames[7], type: "number" },
  measuredBacklashZFor1mm: { title: "Z backlash for 1mm", description: "Measured shortfall on a 1mm Z move after a direction change.", group: groupNames[7], type: "number" },
  measuredBacklashZFor10mm: { title: "Z backlash for 10mm", description: "Measured shortfall on a 10mm Z move after a direction change.", group: groupNames[7], type: "number" }
};

// ---------------------------------------------------------------------------
// formats and modals
// ---------------------------------------------------------------------------
var permittedCommentChars = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,=_->()/:+";
var nFormat = createFormat({ prefix: "N", decimals: 0 });
var gFormat = createFormat({ prefix: "G", decimals: 1 });
var mFormat = createFormat({ prefix: "M", decimals: 0 });
var xyzFormat = createFormat({ decimals: (unit == MM ? 3 : 4), forceDecimal: false });
var rFormat = xyzFormat; // radius
var feedFormat = createFormat({ decimals: (unit == MM ? 0 : 1), forceDecimal: false });
var toolFormat = createFormat({ decimals: 0 });
var rpmFormat = createFormat({ decimals: 0 });
var milliFormat = createFormat({ decimals: 0 }); // milliseconds for G4 P
var taperFormat = createFormat({ decimals: 1, scale: DEG });

var xOutput = createVariable({ prefix: "X" }, xyzFormat);
var yOutput = createVariable({ prefix: "Y" }, xyzFormat);
var zOutput = createVariable({ prefix: "Z" }, xyzFormat);
var feedOutput = createVariable({ prefix: "F", force: false }, feedFormat);
var sOutput = createVariable({ prefix: "S", force: false }, rpmFormat);

// circular output
var iOutput = createReferenceVariable({ prefix: "I", force: false }, xyzFormat);
var jOutput = createReferenceVariable({ prefix: "J", force: false }, xyzFormat);

var gMotionModal = createModal({ force: true }, gFormat); // G0-G3 always written (RRF has no modal motion group guarantee we want to rely on)
var gAbsIncModal = createModal({}, gFormat); // G90-91
var gUnitModal = createModal({}, gFormat); // G20-21

// ---------------------------------------------------------------------------
// collected state
// ---------------------------------------------------------------------------
var sequenceNumber;
var currentWorkOffset;        // 1..9, WCS currently selected in the output
var atSafeMachineZ = false;   // true right after a G53 retract to safeMachineZ (XY may then move first)
var spindleState = { rpm: 0, clockwise: true, on: false };
var redirectedOutput = false; // true while output goes to the descriptive file name
var renameOutputTo = undefined; // single-file method: destination path, applied in onTerminate() once the output file is complete
var stubCleanupScript = undefined; // single-file method: path of the background script that removes the dialog-named file
var motionBox = {
  mBox: [[null, null], [null, null], [null, null]],
  set: function (axis, v) {
    if (this.mBox[axis][0] === null || v < this.mBox[axis][0]) { this.mBox[axis][0] = v; }
    if (this.mBox[axis][1] === null || v > this.mBox[axis][1]) { this.mBox[axis][1] = v; }
  },
  text: function (axis) {
    if (this.mBox[axis][0] === null) { return "[no moves]"; }
    return "[min: " + xyzFormat.format(this.mBox[axis][0]) + " | max: " + xyzFormat.format(this.mBox[axis][1]) + "]";
  }
};
// backlash compensation state (upstream)
var bCompensation = {
  x1: 0, y1: 0, z1: 0, x10: 0, y10: 0, z10: 0,
  stepsPerUnit: [400, 400, 400],
  tolerance: 0.05,
  lastM92: [0, 0, 0],
  firstTime: [true, true, true],
  lastRequestedPosition: [0, 0, 0],
  oldPos: [0, 0, 0],
  lastDir: ["none", "none", "none"],
  isFirstTime: function (axis) {
    if (this.firstTime[axis]) { this.firstTime[axis] = false; return true; }
    return false;
  },
  x: function () { return (this.x1 > 0 || this.x10 > 0); },
  y: function () { return (this.y1 > 0 || this.y10 > 0); },
  z: function () { return (this.z1 > 0 || this.z10 > 0); }
};

// ---------------------------------------------------------------------------
// output helpers
// ---------------------------------------------------------------------------
function writeBlock() {
  var text = formatWords(arguments);
  if (!text) {
    return;
  }
  if (properties.showSequenceNumbers) {
    writeWords2(nFormat.format(sequenceNumber % 100000), arguments);
    sequenceNumber += properties.sequenceNumberIncrement;
  } else {
    writeWords(arguments);
  }
}

function writeComment(text) {
  writeln(";" + filterText(String(text).toUpperCase(), permittedCommentChars));
}

/** Dwell in seconds. RRF G4: P = milliseconds, S = seconds. We always use P in whole milliseconds. */
function writeDwellSeconds(seconds) {
  var ms = Math.round(Number(seconds) * 1000);
  if (ms < 1) {
    return;
  }
  writeBlock(gFormat.format(4), "P" + milliFormat.format(ms));
}

/** M291 message box. mode: 0 auto-close, 1 close button (both non-blocking), 2 OK (blocking), 3 OK/Cancel (blocking, Cancel aborts). */
function writeDialog(message, title, mode, timeoutSeconds, jog) {
  var clean = function (s, max) {
    s = String(s).replace(/["';]/g, "").replace(/[^\x20-\x7E]/g, "");
    return (s.length > max) ? s.substr(0, max) : s;
  };
  title = clean(title, 30);
  var extra = "";
  if ((mode == 0 || mode == 1) && timeoutSeconds > 0) {
    extra += " T" + Math.round(timeoutSeconds);
  }
  if ((mode == 2 || mode == 3) && jog) {
    extra += " X1 Y1 Z1";
  }
  // RRF 2.x limits the whole command line to 160 characters
  var budget = 160 - ("M291 P\"\" R\"\" S" + mode + extra).length - title.length - 2;
  message = clean(message, Math.max(20, budget));
  writeBlock(mFormat.format(291), "P\"" + message + "\"", "R\"" + title + "\"", "S" + mode + extra);
}

function writeInfo(message, title, timeoutSeconds) {
  if (properties.informationalMessages) {
    writeDialog(message, title, 1, timeoutSeconds > 0 ? timeoutSeconds : 5, false);
  }
}

function beep() {
  if (properties.beepOn) {
    writeBlock(mFormat.format(300));
  }
}

function forceXYZ() {
  xOutput.reset();
  yOutput.reset();
  zOutput.reset();
}

function forceAny() {
  forceXYZ();
  feedOutput.reset();
}

function trackMotion(x, y, z) {
  if (x !== undefined) { motionBox.set(0, x); }
  if (y !== undefined) { motionBox.set(1, y); }
  if (z !== undefined) { motionBox.set(2, z); }
}

/** Map a Fusion work offset number (1..9) to its G-code word. */
function wcsCode(workOffset) {
  if (workOffset <= 6) {
    return gFormat.format(53 + workOffset); // G54..G59
  }
  return "G59." + (workOffset - 6); // G59.1..G59.3
}

/** Resolve the work offset to use for a section: setup WCS offset wins, 0 falls back to the post property. */
function resolveWorkOffset(section) {
  var workOffset = section.workOffset;
  if (workOffset == 0) {
    workOffset = parseInt(properties.useWhichWCS, 10);
    if (!(workOffset >= 1 && workOffset <= 9)) {
      workOffset = 1;
    }
  }
  if (workOffset > 9) {
    error(localize("Work offset out of range. RepRapFirmware supports G54 to G59.3 (1 to 9)."));
    return 1;
  }
  return workOffset;
}

function writeWorkOffset(workOffset) {
  if (workOffset != currentWorkOffset) {
    writeBlock(wcsCode(workOffset));
    currentWorkOffset = workOffset;
  }
}

/** Retract to the configured safe machine Z in machine coordinates. */
function writeMachineZRetract() {
  writeBlock(gFormat.format(53), gMotionModal.format(0), "Z" + xyzFormat.format(Number(properties.safeMachineZ)));
  zOutput.reset();
  atSafeMachineZ = true;
}

/** Spindle: M3/M4 S<rpm> plus the configured dwell. */
function writeSpindle(rpm, clockwise, forceDwell) {
  var rpmChanged = (rpmFormat.areDifferent(rpm, spindleState.rpm) || !spindleState.on);
  var dirChanged = (spindleState.on && (clockwise != spindleState.clockwise));
  if (!rpmChanged && !dirChanged) {
    return;
  }
  if (rpm < 1) {
    error(localize("Spindle speed out of range."));
    return;
  }
  if (rpm > 99999) {
    warning(localize("Spindle speed exceeds maximum value."));
  }
  writeBlock(mFormat.format(clockwise ? 3 : 4), "S" + rpmFormat.format(rpm));

  var dwell = 0;
  if (properties.spindleDwellMode == "fixed") {
    dwell = Number(properties.spindleDwellFixedSeconds);
  } else if (properties.spindleDwellMode == "proportional") {
    var rpmDiff = dirChanged ? (rpm + spindleState.rpm) : Math.abs(rpm - spindleState.rpm);
    dwell = rpmDiff * Number(properties.spindleRPMCatchupTime6K) / 6000;
    if (dwell < 5) {
      dwell = 5; // upstream minimum
    }
  }
  spindleState.rpm = rpm;
  spindleState.clockwise = clockwise;
  spindleState.on = true;
  if (dwell > 0) {
    writeComment("Dwell for spindle to reach speed");
    writeInfo("Waiting " + Math.round(dwell) + " s for the spindle to reach " + rpmFormat.format(rpm) + " RPM", "Spindle", Math.min(20, Math.round(dwell)));
    writeDwellSeconds(dwell);
  }
}

function writeSpindleStop(withDwell) {
  writeBlock(mFormat.format(5));
  if (withDwell && Number(properties.spindleStopDwellSeconds) > 0 && spindleState.on) {
    writeComment("Wait for spindle to stop");
    writeDwellSeconds(Number(properties.spindleStopDwellSeconds));
  }
  spindleState.on = false;
  spindleState.rpm = 0;
}

function writeToolCall(toolNumber) {
  switch (properties.toolCallMode) {
    case "fusion":
      writeBlock("T" + toolFormat.format(toolNumber));
      break;
    case "fixed":
      writeBlock("T" + toolFormat.format(properties.fixedToolNumber));
      break;
    default:
      writeComment("Tool T" + toolFormat.format(toolNumber) + " (no Tn output, see post property Tn output)");
  }
}

/** Build "op_1_6_spot_drill_5000RPM[_op_2_...]" (or another prefix) from the tools in order of first use. */
function buildDescriptiveFileName() {
  var safe = function (text) {
    return String(text).toLowerCase().replace(/[^a-z0-9.\-]+/g, "_").replace(/^_+|_+$/g, "");
  };
  var diaFormat = createFormat({ decimals: (unit == MM ? 3 : 4), forceDecimal: false });
  var seen = {};
  var parts = [];
  for (var i = 0; i < getNumberOfSections(); ++i) {
    var t = getSection(i).getTool();
    if (seen[t.number]) {
      continue;
    }
    seen[t.number] = true;
    parts.push((properties.descriptiveFileNamePrefix == "op" ? "op_" : "") +
      toolFormat.format(t.number) + "_" + diaFormat.format(t.diameter) + "_" +
      safe(getToolTypeName(t.type)) + "_" + rpmFormat.format(t.spindleRPM) + "RPM");
  }
  var base = "";
  if (properties.descriptiveFileNamePrefix == "program") {
    base = safe(programName ? programName : "");
  } else if (properties.descriptiveFileNamePrefix == "operation") {
    var names = [];
    for (var j = 0; j < getNumberOfSections(); ++j) {
      var sec = getSection(j);
      var opName = sec.hasParameter("operation-comment") ? safe(sec.getParameter("operation-comment")) : "";
      if (opName && names.indexOf(opName) < 0) {
        names.push(opName);
      }
    }
    base = names.join("_");
  }
  return (base ? base + "_" : "") + parts.join("_");
}

function descriptiveFilePath() {
  var name = buildDescriptiveFileName() + "." + extension;
  var folder = FileSystem.getFolderPath(getOutputPath());
  return FileSystem.getCombinedPath(folder, name);
}

/** Redirect all output to the descriptive file name. Leaves a one-line pointer in the file Fusion named. */
function startDescriptiveOutput() {
  if (typeof redirectToFile != "function" || typeof getOutputPath != "function" || typeof FileSystem == "undefined") {
    warning(localize("Descriptive file name is not available in this post kernel. Writing to the normal output file."));
    return;
  }
  if (properties.descriptiveFileMethod == "rename") {
    return; // handled at the end of onClose by finishDescriptiveOutput()
  }
  var path = descriptiveFilePath();
  writeln("; Program written to " + FileSystem.getFilename(path) + " (post property 'Descriptive output file name')");
  redirectToFile(path);
  redirectedOutput = true;
}

/** End of onClose: close a redirection, or remember the rename target for onTerminate(). */
function finishDescriptiveOutput() {
  if (redirectedOutput) {
    closeRedirection();
    redirectedOutput = false;
    return;
  }
  if (properties.descriptiveFileName && properties.descriptiveFileMethod == "rename" &&
      typeof getOutputPath == "function" && typeof FileSystem != "undefined") {
    renameOutputTo = descriptiveFilePath(); // the file is not complete yet; see onTerminate()
    writeStubCleanupScript(getOutputPath());
  }
}

/**
  Fusion checks that the dialog-named output file exists after the post has finished, so it cannot be removed
  from inside the post. This writes a small script that deletes it 3 seconds later; onTerminate() launches it.
*/
function writeStubCleanupScript(stubPath) {
  if (typeof redirectToFile != "function" || typeof executeNoWait != "function") {
    return;
  }
  var isWindows = (stubPath.indexOf("\\") >= 0);
  var folder = FileSystem.getFolderPath(stubPath);
  var scriptName = ".remove_" + FileSystem.getFilename(stubPath) + (isWindows ? ".cmd" : ".sh");
  stubCleanupScript = FileSystem.getCombinedPath(folder, scriptName);
  redirectToFile(stubCleanupScript);
  if (isWindows) {
    writeln("@echo off");
    writeln("ping -n 4 127.0.0.1 >nul");
    writeln("del /q \"" + stubPath + "\"");
    writeln("del /q \"%~f0\"");
  } else {
    writeln("#!/bin/sh");
    writeln("sleep 3");
    writeln("rm -f \"" + stubPath + "\"");
    writeln("rm -f \"$0\"");
  }
  closeRedirection();
}

/** Called by the kernel after the primary output file has been written and closed. Only then is its content complete. */
function onTerminate() {
  if (!renameOutputTo) {
    return;
  }
  var src = getOutputPath();
  var dest = renameOutputTo;
  renameOutputTo = undefined;
  var copied = false;
  try {
    if (FileSystem.isFile(dest)) {
      FileSystem.remove(dest);
    }
    FileSystem.copyFile(src, dest);
    copied = true;
  } catch (e) {
    warning(localize("Could not copy the output file to the descriptive name. The program is in the dialog-named file. Use the 'Redirect' method."));
  }
  if (stubCleanupScript) {
    var script = stubCleanupScript;
    stubCleanupScript = undefined;
    try {
      if (copied) {
        var isWindows = (src.indexOf("\\") >= 0);
        var folder = FileSystem.getFolderPath(src);
        if (isWindows) {
          executeNoWait("cmd.exe", "/c \"" + script + "\"", true, folder);
        } else {
          executeNoWait("/bin/sh", "\"" + script + "\"", true, folder);
        }
      } else {
        FileSystem.remove(script);
      }
    } catch (e2) {
      warning(localize("Could not start the cleanup of the dialog-named file; it was left in place."));
    }
  }
}

// ---------------------------------------------------------------------------
// program start
// ---------------------------------------------------------------------------
function onOpen() {
  if (properties.useRadius) {
    maximumCircularSweep = toRad(90); // avoid potential center calculation errors for CNC
  }
  // Words are always space separated: RRF 2.05.1 splits several commands on one line (e.g. "G53 G0 Z5", "G90 G0 X0 Y0")
  // only at a space followed by G or M. Without spaces the second command would be swallowed as a parameter.
  setWordSeparator(" ");
  sequenceNumber = properties.sequenceNumberStart;

  // post sanity checks before writing anything
  if (unit != MM) {
    warning(localize("Program is in inches (G20 is written). Enter Safe machine Z and the tool change position in inches as well."));
  }
  if (properties.retractMode == "machine" || properties.manualToolChange || properties.endPosition == "park") {
    if (Number(properties.safeMachineZ) == 0) {
      warning(localize("Safe machine Z is 0. Confirm that machine coordinate Z0 is a safe height on your machine, or set the 'Safe machine Z' post property."));
    }
  }
  if ((getNumberOfSections() > 0) && (getSection(0).workOffset == 0)) {
    for (var i = 0; i < getNumberOfSections(); ++i) {
      if (getSection(i).workOffset > 0) {
        error(localize("Using multiple work offsets is not possible if the initial work offset is 0."));
        return;
      }
    }
  }
  for (var s = 0; s < getNumberOfSections(); ++s) {
    if (getSection(s).isMultiAxis()) {
      error(localize("Multi-axis toolpaths are not supported by this post."));
      return;
    }
  }

  if (properties.descriptiveFileName) {
    startDescriptiveOutput();
  }

  setupBacklashCompensation();

  // ---- header ----
  if (programName) {
    writeComment("Program Name: " + programName);
  }
  if (programComment) {
    writeComment(programComment);
  }
  var d = new Date();
  var pad = function (n) { return (n < 10 ? "0" : "") + n; };
  writeComment("GCode created on " + d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " at " + pad(d.getHours()) + "-" + pad(d.getMinutes()) + "-" + pad(d.getSeconds()));
  writeln("");
  if (properties.writeVersion) {
    writeComment(localize("Post: ") + description);
    if ((typeof getHeaderVersion == "function") && getHeaderVersion()) {
      writeComment(localize("   post version") + ": " + getHeaderVersion());
    }
    if ((typeof getHeaderDate == "function") && getHeaderDate()) {
      writeComment(localize("   post modified") + ": " + getHeaderDate().replace(/:/g, "-"));
    }
    writeComment("   Target: Duet 2 Ethernet, RepRapFirmware 2.05.1, CNC mode (M453)");
  }
  var vendor = machineConfiguration.getVendor();
  var model = machineConfiguration.getModel();
  var mdescription = machineConfiguration.getDescription();
  if (properties.writeMachine && (vendor || model || mdescription)) {
    writeComment(localize("Machine"));
    if (vendor) { writeComment("  " + localize("vendor") + ": " + vendor); }
    if (model) { writeComment("  " + localize("model") + ": " + model); }
    if (mdescription) { writeComment("  " + localize("description") + ": " + mdescription); }
  }

  // tool list
  if (properties.writeTools) {
    var zRanges = {};
    if (is3D()) {
      for (var i = 0; i < getNumberOfSections(); ++i) {
        var section = getSection(i);
        var zRange = section.getGlobalZRange();
        var stool = section.getTool();
        if (zRanges[stool.number]) {
          zRanges[stool.number].expandToRange(zRange);
        } else {
          zRanges[stool.number] = zRange;
        }
      }
    }
    var tools = getToolTable();
    if (tools.getNumberOfTools() > 0) {
      writeComment("Tools in this program");
      for (var t = 0; t < tools.getNumberOfTools(); ++t) {
        var ltool = tools.getTool(t);
        var comment = "   T" + toolFormat.format(ltool.number) + " D=" + xyzFormat.format(ltool.diameter) + " " +
          localize("CR") + "=" + xyzFormat.format(ltool.cornerRadius);
        if ((ltool.taperAngle > 0) && (ltool.taperAngle < Math.PI)) {
          comment += " " + localize("TAPER") + "=" + taperFormat.format(ltool.taperAngle) + localize("deg");
        }
        if (zRanges[ltool.number]) {
          comment += " - " + localize("ZMIN") + "=" + xyzFormat.format(zRanges[ltool.number].getMinimum());
        }
        comment += " - " + getToolTypeName(ltool.type);
        writeComment(comment);
      }
    }
  }

  // configuration summary and prerequisites, so the operator can check them in the file
  writeln("");
  writeComment("Post settings used");
  writeComment("  Retract strategy: " + (properties.retractMode == "machine" ? "G53 safe machine Z before XY moves" : "Fusion clearance height in active WCS before XY moves"));
  writeComment("  Safe machine Z (G53): " + xyzFormat.format(Number(properties.safeMachineZ)) + (properties.retractMode == "machine" || properties.manualToolChange || properties.endPosition == "park" ? " (USED)" : " (not used)"));
  writeComment("  Manual tool change: " + (properties.manualToolChange ? "yes, park at G53 X" + xyzFormat.format(Number(properties.toolChangeXPos)) + " Y" + xyzFormat.format(Number(properties.toolChangeYPos)) : "no"));
  writeComment("  Tn output: " + properties.toolCallMode + ", Probe after tool change: " + ["none", "Z plate", "corner"][parseInt(properties.probeToolOnChange, 10)]);
  writeComment("  Spindle dwell: " + properties.spindleDwellMode + ", Spindle stop dwell: " + Number(properties.spindleStopDwellSeconds) + "s");
  writeComment("  Home on tool change (G28): " + (properties.homeOnToolChange ? "YES" : "no") + ", End with M0: " + (properties.endProgramM0 ? "YES" : "no"));
  writeComment("Prerequisites before pressing start");
  writeComment("  1. Machine homed. 2. Firmware in CNC mode (M453). 3. Active WCS origin set for this setup (G10 L20).");
  writeComment("  4. First tool mounted and its Z zero valid. 5. Safe machine Z and tool change XY clear all clamps with the longest tool.");
  writeComment("  The post does not know the machine position at start. The first motion is a Z move in the chosen retract strategy.");
  writeln("");
  writeComment("-+- Program begins here -+-");

  // absolute coordinates and units
  writeBlock(gAbsIncModal.format(90));
  switch (unit) {
    case IN:
      writeBlock(gUnitModal.format(20));
      break;
    case MM:
      writeBlock(gUnitModal.format(21));
      break;
  }

  if (properties.startConfirmation) {
    var firstTool = (getNumberOfSections() > 0) ? getSection(0).getTool() : undefined;
    var toolText = firstTool ? ("T" + toolFormat.format(firstTool.number) + " D" + xyzFormat.format(firstTool.diameter)) : "";
    beep();
    writeDialog("Homed, WCS zeroed, " + toolText + " mounted? First move is Z retract. OK starts, Cancel aborts", "Start job", 3, 0, false);
  }
}

function onComment(message) {
  var comments = String(message).split(";");
  for (var c in comments) {
    writeComment(comments[c]);
  }
}

function onPassThrough(text) {
  var commands = String(text).split(",");
  for (var c in commands) {
    writeBlock(commands[c]);
  }
}

// ---------------------------------------------------------------------------
// sections
// ---------------------------------------------------------------------------
function onSection() {
  var insertToolCall = isFirstSection() ||
    (currentSection.getForceToolChange && currentSection.getForceToolChange()) ||
    (tool.number != getPreviousSection().getTool().number);
  var newWorkOffset = isFirstSection() ||
    (resolveWorkOffset(getPreviousSection()) != resolveWorkOffset(currentSection));

  var remaining = currentSection.workPlane;
  if (!isSameDirection(remaining.forward, new Vector(0, 0, 1))) {
    error(localize("Tool orientation is not supported."));
    return;
  }
  setRotation(remaining);

  var cycleType = hasParameter("operation:cycleType") ? getParameter("operation:cycleType") : "";
  if (cycleType == "tapping" || cycleType == "right-tapping" || cycleType == "left-tapping" || cycleType == "tapping-with-chip-breaking") {
    error(localize("Tapping cycles are not supported by this post (no rigid tapping on RepRapFirmware)."));
    return;
  }

  writeln("");
  if (hasParameter("operation-comment")) {
    var comment = getParameter("operation-comment");
    if (comment) {
      writeComment("TITLE-> Operation " + comment);
      writeInfo("Now operating: " + comment, "Current operation", 5);
    }
  }

  var workOffset = resolveWorkOffset(currentSection);

  // ---- retract before anything moves in XY at a tool change or WCS change ----
  if (!isFirstSection() && (insertToolCall || newWorkOffset)) {
    if (properties.retractMode == "machine") {
      writeMachineZRetract();
    } else {
      // WCS mode: make sure we are at least at the previous operation's clearance height before switching
      var prevClearance = getFramePosition(getPreviousSection().getInitialPosition()).z;
      if (getCurrentPosition().z < prevClearance) {
        writeBlock(gMotionModal.format(0), "Z" + xyzFormat.format(prevClearance));
        zOutput.reset();
      }
    }
  }

  // ---- tool change ----
  if (insertToolCall) {
    if (tool.number > 256) {
      warning(localize("Tool number exceeds maximum value."));
    }
    if (isFirstSection()) {
      writeComment("LOGGING-> First tool T" + toolFormat.format(tool.number) + " must already be mounted");
      writeToolCall(tool.number);
      if (properties.probe3dOnStart) {
        writeWorkOffset(workOffset);
        writeCornerProbeBlock(workOffset);
      }
    } else if (properties.manualToolChange) {
      writeManualToolChange(workOffset);
    } else {
      writeSpindleStop(false);
      writeToolCall(tool.number);
    }
    if (tool.comment) {
      writeComment(tool.comment);
    }
    currentWorkOffset = undefined; // force the WCS to be re-selected after a tool change
  }

  // ---- spindle ----
  writeSpindle(tool.spindleRPM, tool.clockwise, insertToolCall);

  // ---- work coordinate system ----
  writeWorkOffset(workOffset);

  // ---- initial positioning: Z clearance first, XY second ----
  forceAny();
  gMotionModal.reset();
  var initialPosition = getFramePosition(currentSection.getInitialPosition());

  if (atSafeMachineZ) {
    // We are at the user-declared safe machine Z (G53). Traverse in XY there, then descend to the Fusion clearance height.
    writeBlock(gAbsIncModal.format(90), gMotionModal.format(0), xOutput.format(initialPosition.x), yOutput.format(initialPosition.y));
    writeBlock(gMotionModal.format(0), zOutput.format(initialPosition.z));
    atSafeMachineZ = false;
  } else if (properties.retractMode == "machine" && (isFirstSection() || insertToolCall || newWorkOffset)) {
    writeMachineZRetract();
    writeBlock(gAbsIncModal.format(90), gMotionModal.format(0), xOutput.format(initialPosition.x), yOutput.format(initialPosition.y));
    writeBlock(gMotionModal.format(0), zOutput.format(initialPosition.z));
    atSafeMachineZ = false;
  } else {
    // WCS clearance strategy: Z to the operation's clearance height BEFORE any XY move.
    // Always written for the first section, tool changes and WCS changes (the controller position is unknown to the post).
    // Between operations with the same tool it is written only if the tool is below the new clearance height.
    if (isFirstSection() || insertToolCall || newWorkOffset || (getCurrentPosition().z < initialPosition.z)) {
      writeBlock(gAbsIncModal.format(90), gMotionModal.format(0), zOutput.format(initialPosition.z));
    }
    writeBlock(gMotionModal.format(0), xOutput.format(initialPosition.x), yOutput.format(initialPosition.y));
    // If the tool is still above the clearance height (same tool, previous operation ended higher), the first
    // recorded move of the operation brings Z down. No extra Z move is written here.
  }
  trackMotion(initialPosition.x, initialPosition.y, initialPosition.z);
}

function onSectionEnd() {
  forceAny();
}

/** Manual tool change: stop spindle, park in machine coordinates, prompt, optional homing/probing. */
function writeManualToolChange(workOffset) {
  writeComment("TITLE-> ---- TOOL CHANGE ROUTINE BEGINS ----");
  writeSpindleStop(true);
  writeBlock(gAbsIncModal.format(90));
  writeMachineZRetract(); // Z first, in machine coordinates
  writeBlock(gFormat.format(53), gMotionModal.format(0), "X" + xyzFormat.format(Number(properties.toolChangeXPos)), "Y" + xyzFormat.format(Number(properties.toolChangeYPos)));
  writeBlock(mFormat.format(400));
  writeToolCall(tool.number);
  beep();
  writeDialog("Change to T" + toolFormat.format(tool.number) + " D" + xyzFormat.format(tool.diameter) + " " + getToolTypeName(tool.type) +
    ". OK when the tool is secured and hands are clear. Cancel aborts", "Tool change", 3, 0, false);
  var toolChangeMoved = false;
  if (properties.homeOnToolChange) {
    writeComment("CAUTION-> G28 homes all axes (homeall.g)");
    writeBlock(gFormat.format(28));
    toolChangeMoved = true;
  }
  if (properties.probeToolOnChange != "0") {
    writeWorkOffset(workOffset);
    if (properties.probeToolOnChange == "1") {
      writeZProbeBlock(workOffset);
    } else {
      writeCornerProbeBlock(workOffset);
    }
    toolChangeMoved = true;
  }
  if (toolChangeMoved) {
    // position after homing/probing is not the parked safe Z any more: retract again before XY moves
    writeMachineZRetract();
  }
  writeComment("TITLE-> ---- TOOL CHANGE ROUTINE ENDS ----");
}

// ---------------------------------------------------------------------------
// motion
// ---------------------------------------------------------------------------
function onDwell(seconds) {
  if (seconds > 99999) {
    warning(localize("Dwelling time is way too long."));
  }
  writeDwellSeconds(seconds);
}

function onSpindleSpeed(spindleSpeed) {
  writeSpindle(spindleSpeed, spindleState.clockwise, false);
}

var pendingRadiusCompensation = -1;

function onRadiusCompensation() {
  pendingRadiusCompensation = radiusCompensation;
}

function onRapid(_x, _y, _z) {
  var cx = axialBacklashCompensation(0, _x);
  var cy = axialBacklashCompensation(1, _y);
  var cz = axialBacklashCompensation(2, _z);
  var x = xOutput.format(cx);
  var y = yOutput.format(cy);
  var z = zOutput.format(cz);
  if (x || y || z) {
    if (pendingRadiusCompensation >= 0) {
      error(localize("Radius compensation mode cannot be changed at rapid traversal."));
      return;
    }
    if (properties.splitRapids && z && (x || y)) {
      if (_z > getCurrentPosition().z) {
        writeBlock(gMotionModal.format(0), z); // going up: Z first
        writeBlock(gMotionModal.format(0), x, y);
      } else {
        writeBlock(gMotionModal.format(0), x, y); // going down: XY first at the higher Z
        writeBlock(gMotionModal.format(0), z);
      }
    } else {
      writeBlock(gMotionModal.format(0), x, y, z);
    }
    trackMotion(cx, cy, cz);
    feedOutput.reset();
  }
}

function onLinear(_x, _y, _z, feed) {
  var cx = axialBacklashCompensation(0, _x);
  var cy = axialBacklashCompensation(1, _y);
  var cz = axialBacklashCompensation(2, _z);
  var x = xOutput.format(cx);
  var y = yOutput.format(cy);
  var z = zOutput.format(cz);
  var f = feedOutput.format(feed);
  if (x || y || z) {
    if (pendingRadiusCompensation >= 0) {
      pendingRadiusCompensation = -1;
      switch (radiusCompensation) {
        case RADIUS_COMPENSATION_LEFT:
        case RADIUS_COMPENSATION_RIGHT:
          error(localize("Controller radius compensation (G41/G42) is not supported by RepRapFirmware. Use 'In computer' compensation in the operation."));
          return;
        default:
          writeBlock(gMotionModal.format(1), x, y, z, f);
      }
    } else {
      writeBlock(gMotionModal.format(1), x, y, z, f);
    }
    trackMotion(cx, cy, cz);
  } else if (f) {
    if (getNextRecord().isMotion()) { // try not to output feed without motion
      feedOutput.reset(); // force feed on next line
    } else {
      writeBlock(gMotionModal.format(1), f);
    }
  }
}

function onRapid5D(_x, _y, _z, _a, _b, _c) {
  error(localize("Multi-axis motion is not supported by this post."));
}

function onLinear5D(_x, _y, _z, _a, _b, _c, feed) {
  error(localize("Multi-axis motion is not supported by this post."));
}

function onCircular(clockwise, cx, cy, cz, x, y, z, feed) {
  if (pendingRadiusCompensation >= 0) {
    error(localize("Radius compensation cannot be activated/deactivated for a circular move."));
    return;
  }
  if (properties.applyBacklashCompensation && properties.backlashCompensationMethod == "distance") {
    linearize(tolerance); // distance compensation shifts coordinates; arcs would no longer close
    return;
  }
  var start = getCurrentPosition();

  if (isFullCircle()) {
    if (properties.useRadius || isHelical()) { // radius mode does not support full arcs
      linearize(tolerance);
      return;
    }
    switch (getCircularPlane()) {
      case PLANE_XY:
        writeBlock(gAbsIncModal.format(90), gMotionModal.format(clockwise ? 2 : 3), iOutput.format(cx - start.x, 0), jOutput.format(cy - start.y, 0), feedOutput.format(feed));
        break;
      default:
        linearize(tolerance);
    }
  } else if (!properties.useRadius) {
    switch (getCircularPlane()) {
      case PLANE_XY:
        writeBlock(gAbsIncModal.format(90), gMotionModal.format(clockwise ? 2 : 3), xOutput.format(x), yOutput.format(y), zOutput.format(z), iOutput.format(cx - start.x, 0), jOutput.format(cy - start.y, 0), feedOutput.format(feed));
        break;
      default:
        linearize(tolerance);
    }
  } else { // use radius mode
    var r = getCircularRadius();
    if (toDeg(getCircularSweep()) > (180 + 1e-9)) {
      r = -r; // allow up to <360 deg arcs
    }
    switch (getCircularPlane()) {
      case PLANE_XY:
        writeBlock(gMotionModal.format(clockwise ? 2 : 3), xOutput.format(x), yOutput.format(y), zOutput.format(z), "R" + rFormat.format(r), feedOutput.format(feed));
        break;
      default:
        linearize(tolerance);
    }
  }
  trackMotion(x, y, z);
  // keep the backlash bookkeeping in step with the arc end point (steps method only; distance method linearizes above)
  if (properties.applyBacklashCompensation) {
    bCompensation.oldPos = [x, y, z];
    bCompensation.lastRequestedPosition = [x, y, z];
  }
}

// ---------------------------------------------------------------------------
// canned cycles: RepRapFirmware has none, every cycle is expanded into G0/G1/G4
// ---------------------------------------------------------------------------
function onCycle() {
}

function onCyclePoint(x, y, z) {
  switch (cycleType) {
    case "tapping":
    case "left-tapping":
    case "right-tapping":
    case "tapping-with-chip-breaking":
      error(localize("Tapping cycles are not supported by this post."));
      return;
    default:
      expandCyclePoint(x, y, z);
  }
}

function onCycleEnd() {
  zOutput.reset();
}

// ---------------------------------------------------------------------------
// commands
// ---------------------------------------------------------------------------
function onCommand(command) {
  switch (command) {
    case COMMAND_START_SPINDLE:
      writeSpindle(tool.spindleRPM, tool.clockwise, false);
      return;
    case COMMAND_SPINDLE_CLOCKWISE:
      writeSpindle(tool.spindleRPM, true, false);
      return;
    case COMMAND_SPINDLE_COUNTERCLOCKWISE:
      writeSpindle(tool.spindleRPM, false, false);
      return;
    case COMMAND_STOP_SPINDLE:
      writeSpindleStop(false);
      return;
    case COMMAND_STOP:
    case COMMAND_OPTIONAL_STOP:
      // RRF M0 ends the job and M1 is sleep: a blocking dialog is the equivalent of a program stop
      writeBlock(mFormat.format(400));
      writeDialog("Program stop requested by the CAM program. OK to continue", "Program stop", 2, 0, false);
      return;
    case COMMAND_END:
      return; // M2 is not supported by RRF 2.05.1; the file simply ends
    case COMMAND_COOLANT_ON:
    case COMMAND_COOLANT_OFF:
      return; // no coolant / dust collector output in this post
    case COMMAND_LOCK_MULTI_AXIS:
    case COMMAND_UNLOCK_MULTI_AXIS:
    case COMMAND_BREAK_CONTROL:
    case COMMAND_TOOL_MEASURE:
      return;
  }
  onUnsupportedCommand(command);
}

// ---------------------------------------------------------------------------
// program end
// ---------------------------------------------------------------------------
function onClose() {
  writeln("");
  writeComment("-+- Program end -+-");
  // retract first, then stop the spindle
  if (properties.retractMode == "machine" || properties.endPosition == "park") {
    writeMachineZRetract();
  } else if (getNumberOfSections() > 0) {
    var clearance = getFramePosition(getSection(getNumberOfSections() - 1).getInitialPosition()).z;
    if (getCurrentPosition().z < clearance) {
      writeBlock(gMotionModal.format(0), "Z" + xyzFormat.format(clearance));
    }
  }
  writeSpindleStop(true);
  if (properties.endPosition == "park") {
    writeBlock(gFormat.format(53), gMotionModal.format(0), "X" + xyzFormat.format(Number(properties.toolChangeXPos)), "Y" + xyzFormat.format(Number(properties.toolChangeYPos)));
  }
  writeBlock(mFormat.format(400));
  writeInfo("Program finished. Spindle off", "Program end", 10);
  if (properties.endProgramM0) {
    writeComment("CAUTION-> M0 runs stop.g, idles drives and flags axes as not homed");
    writeBlock(mFormat.format(0));
  }
  writeComment("Tool motion box (commanded coordinates in the active WCS, after any compensation)");
  writeComment(" on X: " + motionBox.text(0));
  writeComment(" on Y: " + motionBox.text(1));
  writeComment(" on Z: " + motionBox.text(2));
  finishDescriptiveOutput(); // keep last
}

// ---------------------------------------------------------------------------
// probing routines (upstream, adapted). Both rewrite the active WCS origin with G10 L20 and store it with M500.
// Hardware assumptions (unchanged from upstream): probe on endstop input E0 (M585 E3), active low (L0).
// ---------------------------------------------------------------------------
function get3dProbeDirection() {
  var left2Right = 1;
  var south2North = 1;
  switch (String(properties.probe3DPlacement)) {
    case "1": left2Right = 1; south2North = -1; break; // top-left
    case "2": left2Right = -1; south2North = -1; break; // top-right
    case "3": left2Right = -1; south2North = 1; break; // bottom-right
    default: left2Right = 1; south2North = 1; // bottom-left
  }
  return [left2Right, south2North];
}

function get3dProbeMove(axis, type) {
  var thisValue = 10;
  var thisTractValue = 10;
  var flag = -1;
  var excess = 3; // millimetres
  var traXcess = 0;
  if (type != "probe") {
    if (type == "intetract") {
      flag = 1;
      traXcess = 5;
    }
  }
  var dir = get3dProbeDirection();
  switch (axis) {
    case "y":
      thisValue = (Number(properties.probe3DWidth) + excess) * dir[1];
      thisTractValue = (thisTractValue + traXcess) * dir[1];
      break;
    default:
      thisValue = (Number(properties.probe3DLength) + excess) * dir[0];
      thisTractValue = (thisTractValue + traXcess) * dir[0];
  }
  if (type != "probe") {
    thisValue = thisTractValue;
  }
  thisValue *= flag;
  return thisValue;
}

function writeCornerProbeBlock(workOffset) {
  writeComment("TITLE-> CORNER PROBE BEGINS --");
  var toolDia = Number(xyzFormat.format(tool.diameter));
  var dir = get3dProbeDirection();
  var probeMotionDir = [0, 0];
  if (dir[0] < 0) { probeMotionDir[0] = 1; }
  if (dir[1] < 1) { probeMotionDir[1] = 1; }
  var offsetX = -1 * dir[0] * (Number(properties.probe3DRetract) + toolDia / 2);
  var offsetY = -1 * dir[1] * (Number(properties.probe3DRetract) + toolDia / 2);
  var offsetZ = Number(properties.probe3DThickness) + 3;
  beep();
  writeDialog("Mount the CORNER PROBE under the tool. Failure can break the tool. Cancel stops all", "Corner probe", 3, 0, true);
  writeBlock("G21");
  writeBlock("G91");
  writeBlock("M563 P999 S\"XYZ-Probe\"");
  writeBlock("T999");
  writeBlock("M585 Z60 E3 L0 F200 S1");
  writeBlock("G10 L20 P" + workOffset + " Z0");
  writeBlock("G1 H1 Z3 F1500");
  writeBlock("G1 H1 X" + get3dProbeMove("x", "probe") + " F1500");
  writeBlock("M400");
  writeBlock("G1 Z-4 F1500");
  writeBlock("M585 X60 E3 L0 F300 S" + probeMotionDir[0]);
  writeBlock("G10 L20 P" + workOffset + " X0");
  writeBlock("G1 H1 X" + get3dProbeMove("x", "retract") + " F1500");
  writeBlock("G1 H1 Z4 F1500");
  writeBlock("M400");
  writeBlock("G1 Y" + get3dProbeMove("y", "probe") + " F1500");
  writeBlock("M400");
  writeBlock("G1 H1 X" + get3dProbeMove("x", "intetract") + " F1500");
  writeBlock("G1 Z-4 F1500");
  writeBlock("M400");
  writeBlock("M585 Y60 E3 L0 F300 S" + probeMotionDir[1]);
  writeBlock("G10 L20 P" + workOffset + " Y0");
  writeBlock("G1 H1 Y" + get3dProbeMove("y", "retract") + " F2000");
  writeBlock("M400");
  writeBlock("G1 H1 Z4 F2000");
  writeBlock("M400");
  writeBlock("G1 H1 X" + (get3dProbeMove("x", "intetract") * -1) + " F2000");
  writeBlock("M563 P999 D-1 H-1");
  writeBlock("T-1");
  writeBlock("G90");
  writeComment("CHANGING-> Setting WCS " + workOffset + " to the probed values");
  writeBlock("G10 L20 P" + workOffset + " X" + xyzFormat.format(offsetX) + " Y" + xyzFormat.format(offsetY) + " Z" + xyzFormat.format(offsetZ));
  writeBlock("M500");
  beep();
  writeDialog("Remove the corner probe. OK when clear", "Corner probe", 2, 0, true);
  writeComment("TITLE-> CORNER PROBE ENDS --");
  atSafeMachineZ = false;
  gAbsIncModal.reset(); // raw G90/G91 were written above
  forceXYZ();
}

function writeZProbeBlock(workOffset) {
  writeComment("TITLE-> Z PROBE BEGINS --");
  // move over the probing spot in XY while still at the parked safe machine Z, then prompt
  writeBlock(wcsCode(workOffset));
  writeBlock(gMotionModal.format(0), "X" + xyzFormat.format(Number(properties.probeZSafeInside)), "Y" + xyzFormat.format(Number(properties.probeZSafeInside)));
  writeBlock("M400");
  beep();
  writeDialog("Place the " + Number(properties.probeZThickness) + "mm Z PLATE under the tool. Jog Z close. Failure can break the tool. Cancel stops all", "Z probe", 3, 0, true);
  writeBlock("G91");
  writeBlock("M563 P999 S\"XYZ-Probe\"");
  writeBlock("T999");
  writeBlock("M585 Z60 E3 L0 F300 S1");
  writeBlock("M563 P999 D-1 H-1");
  writeBlock("T-1");
  writeComment("CHANGING-> Setting WCS " + workOffset + " Z to the probed plate top for the new tool stickout");
  writeBlock("G10 L20 P" + workOffset + " Z" + xyzFormat.format(Number(properties.probeZThickness)));
  writeBlock("M500");
  writeBlock("G1 Z" + xyzFormat.format(Number(properties.probeZRetract)) + " F300");
  writeBlock("G90");
  beep();
  writeDialog("Remove the Z plate. OK when clear", "Z probe", 2, 0, false);
  writeComment("TITLE-> Z PROBE ENDS --");
  atSafeMachineZ = false;
  gAbsIncModal.reset(); // raw G90/G91 were written above
  forceXYZ();
}

// ---------------------------------------------------------------------------
// Linear backlash compensation (upstream feature, kept; off by default)
// ---------------------------------------------------------------------------
function setupBacklashCompensation() {
  bCompensation.x1 = Number(properties.measuredBacklashXFor1mm);
  bCompensation.y1 = Number(properties.measuredBacklashYFor1mm);
  bCompensation.z1 = Number(properties.measuredBacklashZFor1mm);
  bCompensation.x10 = Number(properties.measuredBacklashXFor10mm);
  bCompensation.y10 = Number(properties.measuredBacklashYFor10mm);
  bCompensation.z10 = Number(properties.measuredBacklashZFor10mm);
  if (properties.applyBacklashCompensation && (
    bCompensation.x1 > 1.5 || bCompensation.x10 > 2.5 ||
    bCompensation.y1 > 1.5 || bCompensation.y10 > 2.5 ||
    bCompensation.z1 > 1.5 || bCompensation.z10 > 2.5)) {
    error(localize("Backlash values are too large for compensation. Fix the machine mechanically first."));
  }
  bCompensation.stepsPerUnit = [Number(properties.stepsPerUnitX), Number(properties.stepsPerUnitY), Number(properties.stepsPerUnitZ)];
  bCompensation.tolerance = Number(properties.backlashCompensationTolerance);
  bCompensation.lastM92 = bCompensation.stepsPerUnit.slice();
  if (properties.applyBacklashCompensation) {
    writeComment("------------------------------------------------------------");
    writeComment("Backlash compensation on motor direction changes is applied");
    writeComment("Backlash values on X: " + bCompensation.x1 + "..." + bCompensation.x10);
    writeComment("Backlash values on Y: " + bCompensation.y1 + "..." + bCompensation.y10);
    writeComment("Backlash values on Z: " + bCompensation.z1 + "..." + bCompensation.z10);
    if (properties.backlashCompensationMethod == "steps") {
      writeComment(" - Compensation by M92 steps per mm adjustments");
      writeComment(" - Steps per mm: M92 X" + bCompensation.stepsPerUnit[0] + " Y" + bCompensation.stepsPerUnit[1] + " Z" + bCompensation.stepsPerUnit[2]);
    } else {
      writeComment(" - Compensation by motion distance adjustments");
      writeComment(" - Check the tool motion box at the end of this file");
    }
    writeComment("------------------------------------------------------------");
  }
}

function axialBacklashCompensation(axis, _value) {
  if (properties.applyBacklashCompensation) {
    if (properties.backlashCompensationMethod == "distance") {
      return axialBacklashCompensationByDistance(axis, _value);
    }
    return axialBacklashCompensationBySteps(axis, _value);
  }
  return _value;
}

function axialBacklashCompensationBySteps(axis, _value) {
  if (!bCompensation.isFirstTime(axis)) {
    var axisLetter = ["X", "Y", "Z"];
    if (isMoveReallyNeeded(axis, _value)) {
      var diff = getBacklashCompensationValue(axis, _value, bCompensation.oldPos[axis]);
      if (diff != 0) {
        var motionDistance = Math.abs(_value - bCompensation.oldPos[axis]);
        if (motionDistance != 0 && motionDistance > bCompensation.tolerance) {
          var compensatedSteps = (motionDistance + Math.abs(diff)) * bCompensation.stepsPerUnit[axis] / motionDistance;
          if (compensatedSteps != bCompensation.lastM92[axis]) {
            writeBlock("M92 " + axisLetter[axis] + compensatedSteps);
            bCompensation.lastM92[axis] = compensatedSteps;
          }
        }
      } else {
        if (bCompensation.lastM92[axis] != bCompensation.stepsPerUnit[axis]) {
          writeBlock("M92 " + axisLetter[axis] + bCompensation.stepsPerUnit[axis]);
          bCompensation.lastM92[axis] = bCompensation.stepsPerUnit[axis];
        }
      }
    }
  }
  bCompensation.oldPos[axis] = _value;
  bCompensation.lastRequestedPosition[axis] = _value;
  return _value;
}

function axialBacklashCompensationByDistance(axis, _value) {
  var _holder = _value;
  var isThisMoveReallyNeeded = isMoveReallyNeeded(axis, _value);
  bCompensation.lastRequestedPosition[axis] = _value;
  var first = bCompensation.isFirstTime(axis);
  if (first) {
    bCompensation.oldPos[axis] = _holder;
  } else if (isThisMoveReallyNeeded) {
    var diff = getBacklashCompensationValue(axis, _value, bCompensation.oldPos[axis]);
    if (Math.abs(_value - bCompensation.oldPos[axis]) > bCompensation.tolerance) {
      _value = _value + diff;
    }
    bCompensation.oldPos[axis] = _value;
  }
  bToggleOutput(axis, isThisMoveReallyNeeded || first);
  return _value;
}

function isMoveReallyNeeded(axis, _value) {
  return (bCompensation.lastRequestedPosition[axis] != _value);
}

function bToggleOutput(axis, state) {
  var outputs = [xOutput, yOutput, zOutput];
  if (state) {
    outputs[axis].enable();
  } else {
    outputs[axis].disable();
  }
}

function getBacklashCompensationValue(axis, newPos, oldPos) {
  if (newPos == oldPos) {
    return 0;
  }
  var compFlag = false;
  var compensationValue = [0, 0, 0]; // for 1mm, for 10mm, applicable value
  switch (axis) {
    case 0: compFlag = bCompensation.x(); compensationValue[0] = bCompensation.x1; compensationValue[1] = bCompensation.x10; break;
    case 1: compFlag = bCompensation.y(); compensationValue[0] = bCompensation.y1; compensationValue[1] = bCompensation.y10; break;
    case 2: compFlag = bCompensation.z(); compensationValue[0] = bCompensation.z1; compensationValue[1] = bCompensation.z10; break;
  }
  if (!compFlag) {
    return 0;
  }
  var thisDirection = (oldPos < newPos ? "up" : "down");
  if (thisDirection != bCompensation.lastDir[axis]) {
    if (bCompensation.lastDir[axis] == "none") {
      bCompensation.lastDir[axis] = thisDirection;
      return 0;
    }
    bCompensation.lastDir[axis] = thisDirection;
    if (Math.abs(newPos - oldPos) > 1) {
      compensationValue[2] = Math.abs(compensationValue[1]);
    } else {
      compensationValue[2] = Math.abs(compensationValue[0]);
    }
  }
  return (thisDirection == "up" ? compensationValue[2] : -compensationValue[2]);
}
