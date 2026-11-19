/*
  Scenario suite for Duet2Ethernet_RRF2051.cps executed on tests/mock-kernel.js.
  Run:  node tests/run-tests.js
  Writes every scenario's G-code to tests/output/ and the headline examples to examples/.
*/
"use strict";
const path = require("path");
const fs = require("fs");
const { run } = require("./mock-kernel.js");

const CPS = path.join(__dirname, "..", "Duet2Ethernet_RRF2051.cps");
const OUT = path.join(__dirname, "output");
const EXAMPLES = path.join(__dirname, "..", "examples");
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(EXAMPLES, { recursive: true });

// ---------------------------------------------------------------- jobs
const T1 = { number: 1, diameter: 6.35, spindleRPM: 5000, type: 11 };   // spot drill-ish
const T2 = { number: 2, diameter: 6, spindleRPM: 12000 };
const T3 = { number: 3, diameter: 3, spindleRPM: 18000, clockwise: false };

function grid64() { // 8 x 8 holes like the user's 1001.cnc.gcode (64 spot drills)
  const pts = [];
  for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) pts.push({ x: 20 + c * 12.7, y: 20 + r * 12.7, z: -0.508 });
  return pts;
}
const spotDrill64 = {
  name: "Spot drill 64", tool: T1, workOffset: 1, initial: { x: 20, y: 20, z: 15.24 },
  cycle: { type: "drilling", retract: 5.08, feedrate: 203, points: grid64() }, moves: []
};
const pecking = {
  name: "Drill chip breaking", tool: T1, workOffset: 1, initial: { x: 20, y: 20, z: 15.24 },
  cycle: { type: "chip-breaking", retract: 5.08, feedrate: 150, incrementalDepth: 2, chipBreakDistance: 0.5, dwell: 0.5,
    points: [{ x: 20, y: 20, z: -6 }, { x: 40, y: 20, z: -6 }, { x: 60, y: 20, z: -6 }] }, moves: []
};
const contour = {
  name: "2D Contour1", tool: T2, workOffset: 1, initial: { x: 0, y: -10, z: 15 },
  moves: [
    { type: "rapid", z: 5 }, { type: "linear", z: -3, feed: 300 },
    { type: "linear", x: 0, y: 0, feed: 1000 }, { type: "linear", x: 50, y: 0 },
    { type: "arc", x: 60, y: 10, cx: 50, cy: 10, clockwise: false, feed: 1000 },
    { type: "linear", x: 60, y: 40 }, { type: "linear", x: 0, y: 40 }, { type: "linear", x: 0, y: 0 },
    { type: "rapid", z: 15 }
  ]
};
const pocket = {
  name: "2D Pocket1", tool: T2, workOffset: 1, initial: { x: 30, y: 20, z: 15 },
  moves: [
    { type: "rapid", z: 5 }, { type: "linear", z: -2, feed: 200 },
    { type: "linear", x: 35, y: 20, feed: 800 }, { type: "arc", x: 25, y: 20, cx: 30, cy: 20, clockwise: true, feed: 800 },
    { type: "arc", x: 35, y: 20, cx: 30, cy: 20, clockwise: true, feed: 800 },
    { type: "linear", x: 40, y: 20 }, { type: "arc", x: 20, y: 20, cx: 30, cy: 20, clockwise: true, feed: 800 },
    { type: "arc", x: 40, y: 20, cx: 30, cy: 20, clockwise: true, feed: 800 },
    { type: "rapid", z: 15 }
  ]
};
const adaptive = {
  name: "Adaptive1", tool: T2, workOffset: 1, initial: { x: 5, y: 5, z: 15 },
  moves: (() => {
    const m = [{ type: "rapid", z: 3 }, { type: "linear", x: 5, y: 5, z: -1, feed: 500 }];
    for (let i = 0; i < 30; i++) m.push({ type: "linear", x: 5 + (i % 2) * 40, y: 5 + i, z: -1 - i * 0.1, feed: 1500 });
    m.push({ type: "rapid", x: 10, y: 10, z: 8 });   // combined XYZ rapid going up
    m.push({ type: "rapid", x: 30, y: 30, z: 2 });   // combined XYZ rapid going down
    m.push({ type: "linear", z: -2, feed: 400 });
    m.push({ type: "linear", x: 40, y: 30, feed: 1500 });
    m.push({ type: "rapid", z: 15 });
    return m;
  })()
};
const facing_G55 = { name: "Face G55", tool: T2, workOffset: 2, initial: { x: 0, y: 0, z: 12 },
  moves: [{ type: "rapid", z: 2 }, { type: "linear", z: 0, feed: 300 }, { type: "linear", x: 80, y: 0, feed: 2000 }, { type: "linear", x: 80, y: 10 }, { type: "linear", x: 0, y: 10 }, { type: "rapid", z: 12 }] };
const ccwOp_T3 = { name: "Engrave T3 CCW", tool: T3, workOffset: 1, initial: { x: 10, y: 10, z: 10 },
  moves: [{ type: "rapid", z: 2 }, { type: "linear", z: -0.3, feed: 200 }, { type: "linear", x: 30, y: 10, feed: 600 }, { type: "rapid", z: 10 }] };
const withManualNC = { name: "Contour with manual NC", tool: T2, workOffset: 1, initial: { x: 0, y: 0, z: 15 },
  moves: [{ type: "comment", text: "operator note" }, { type: "command", command: "COMMAND_STOP" }, { type: "rapid", z: 5 }, { type: "linear", z: -1, feed: 300 },
    { type: "dwell", seconds: 2 }, { type: "spindle", rpm: 15000 }, { type: "linear", x: 20, y: 0, feed: 900 }, { type: "passthrough", text: "M117 custom" }, { type: "rapid", z: 15 }] };
const tapping = { name: "Tap", tool: T1, workOffset: 1, initial: { x: 0, y: 0, z: 15 }, cycle: { type: "tapping", retract: 5, feedrate: 100, points: [{ x: 0, y: 0, z: -5 }] }, moves: [] };

function clone(o) { return JSON.parse(JSON.stringify(o)); }
function pocket2(rpm) { const p = clone(pocket); p.name = "2D Pocket2"; p.tool = Object.assign({}, T2, { spindleRPM: rpm }); p.initial = { x: 70, y: 20, z: 15 }; return p; }

const scenarios = [
  { id: "01_spot_drill_64_defaults", job: { sections: [spotDrill64] }, props: {}, example: "spot_drill_64_holes_defaults.gcode" },
  { id: "02_spot_drill_64_machineZ", job: { sections: [spotDrill64] }, props: { retractMode: "machine", safeMachineZ: -2, toolChangeXPos: 5, toolChangeYPos: 5 }, example: "spot_drill_64_holes_machineZ_retract.gcode" },
  { id: "03_pecking_with_dwell", job: { sections: [pecking] }, props: {} },
  { id: "04_contour_radius_arcs", job: { sections: [contour] }, props: {} },
  { id: "05_contour_ij_arcs", job: { sections: [contour] }, props: { useRadius: false } },
  { id: "06_pocket_same_tool_rpm_change", job: { sections: [pocket, pocket2(14000)] }, props: {} },
  { id: "07_adaptive_split_rapids", job: { sections: [adaptive] }, props: {} },
  { id: "08_adaptive_no_split", job: { sections: [adaptive] }, props: { splitRapids: false } },
  { id: "09_toolchange_manual_defaults", job: { sections: [spotDrill64, contour, pocket, ccwOp_T3] }, props: { safeMachineZ: -1, toolChangeXPos: 10, toolChangeYPos: 10 }, example: "multi_tool_manual_toolchange_wcs_retract.gcode" },
  { id: "10_toolchange_manual_machineZ", job: { sections: [spotDrill64, contour, pocket, ccwOp_T3] }, props: { retractMode: "machine", safeMachineZ: -1, toolChangeXPos: 10, toolChangeYPos: 10, endPosition: "park" }, example: "multi_tool_manual_toolchange_machineZ_retract.gcode" },
  { id: "11_toolchange_not_manual", job: { sections: [spotDrill64, contour] }, props: { manualToolChange: false } },
  { id: "12_toolchange_with_zprobe", job: { sections: [spotDrill64, contour] }, props: { probeToolOnChange: "1", safeMachineZ: -1 } },
  { id: "13_toolchange_with_cornerprobe_and_home", job: { sections: [spotDrill64, contour] }, props: { probeToolOnChange: "2", homeOnToolChange: true, safeMachineZ: -1 } },
  { id: "14_g54_then_g55", job: { sections: [contour, facing_G55] }, props: {}, example: "g54_then_g55_wcs_change.gcode" },
  { id: "15_g54_then_g55_machineZ", job: { sections: [contour, facing_G55] }, props: { retractMode: "machine", safeMachineZ: -1 } },
  { id: "16_setup_wcs0_uses_property", job: { sections: [Object.assign(clone(contour), { workOffset: 0 })] }, props: { useWhichWCS: "2" } },
  { id: "17_setup_wcs0_mixed_error", job: { sections: [Object.assign(clone(contour), { workOffset: 0 }), facing_G55] }, props: {}, expectError: /multiple work offsets/ },
  { id: "18_wcs9_allowed", job: { sections: [Object.assign(clone(contour), { workOffset: 9 })] }, props: {} },
  { id: "19_tn_fusion", job: { sections: [spotDrill64, contour] }, props: { toolCallMode: "fusion" } },
  { id: "20_tn_fixed", job: { sections: [spotDrill64, contour] }, props: { toolCallMode: "fixed", fixedToolNumber: 0 } },
  { id: "21_spindle_dwell_none", job: { sections: [spotDrill64, pocket] }, props: { spindleDwellMode: "none", spindleStopDwellSeconds: 0 } },
  { id: "22_spindle_dwell_fixed", job: { sections: [spotDrill64, pocket] }, props: { spindleDwellMode: "fixed", spindleDwellFixedSeconds: 3 } },
  { id: "23_quiet_no_confirm_M0_park", job: { sections: [contour] }, props: { informationalMessages: false, startConfirmation: false, endProgramM0: true, endPosition: "park", safeMachineZ: -1, toolChangeXPos: 0, toolChangeYPos: 300 } },
  { id: "24_manual_nc_commands", job: { sections: [withManualNC] }, props: {} },
  { id: "25_tapping_rejected", job: { sections: [tapping] }, props: {}, expectError: /Tapping/ },
  { id: "26_sequence_numbers", job: { sections: [contour] }, props: { showSequenceNumbers: true } },
  { id: "27_backlash_steps", job: { sections: [adaptive] }, props: { applyBacklashCompensation: true, backlashCompensationMethod: "steps", measuredBacklashXFor1mm: 0.05, measuredBacklashXFor10mm: 0.1, measuredBacklashYFor1mm: 0.05, measuredBacklashYFor10mm: 0.1 } },
  { id: "28_backlash_distance", job: { sections: [adaptive] }, props: { applyBacklashCompensation: true, backlashCompensationMethod: "distance", measuredBacklashXFor1mm: 0.05, measuredBacklashXFor10mm: 0.1 } },
  { id: "29_corner_probe_on_start", job: { sections: [contour] }, props: { probe3dOnStart: true } }
];

// ---------------------------------------------------------------- assertions
const problems = [];
function check(id, cond, msg) { if (!cond) problems.push(id + ": " + msg); }

function motionLines(lines) {
  return lines.map((l, i) => ({ l: l.replace(/^N\d+\s*/, ""), i })).filter(o => /^G5?3?\s*G?[0-3]\b|^G[0-3]\b|^G53/.test(o.l));
}
function firstMotion(lines) {
  for (const l of lines) { const t = l.replace(/^N\d+\s*/, ""); if (/^(G53\s*)?G[0-3](\s|$)/.test(t)) return t; }
  return null;
}
function hasWord(line, w) { return new RegExp("(^|\\s)" + w + "(\\s|$)").test(line); }

function genericChecks(s, res) {
  const id = s.id, lines = res.lines.map(l => l.replace(/^N\d+\s*/, ""));
  const code = lines.filter(l => !l.startsWith(";") && !l.startsWith("!!!"));
  // RRF 2.05.1 compatibility
  for (const l of code) {
    check(id, !/^G28\b/.test(l) || s.props.homeOnToolChange, "G28 (HOME) emitted: " + l);
    check(id, !/^M0\b/.test(l) || s.props.endProgramM0, "M0 emitted: " + l);
    check(id, !/^M[12]\b/.test(l), "M1/M2 emitted: " + l);
    check(id, !/^M6\b/.test(l), "M6 emitted: " + l);
    check(id, !/^S\d/.test(l), "bare S word line: " + l);
    check(id, !/G10 L2 /.test(l), "G10 L2 overwrites a WCS origin: " + l);
    check(id, !/^G60|R0 /.test(l), "G60/R0 restore used: " + l);
    check(id, !/^G4[0-3]\b/.test(l), "G40-43 emitted: " + l);
    check(id, !/G9[89]|G8[0-9]/.test(l), "canned cycle code emitted: " + l);
    check(id, !/^G53\s*$/.test(l), "lonely G53 (RRF G53 is per-line): " + l);
    if (/^G4\b/.test(l)) check(id, /^G4 P\d+$/.test(l), "G4 must be 'G4 P<integer ms>': " + l);
    if (/^M291/.test(l)) {
      check(id, l.length <= 160, "M291 line over 160 chars (" + l.length + "): " + l);
      check(id, /S[0-3](\s|$)/.test(l), "M291 mode: " + l);
      check(id, !/S0(\s|$)/.test(l) || /T\d/.test(l), "M291 S0 without timeout: " + l);
    }
    check(id, !/G1 H1 Z500/.test(l), "flush routine present: " + l);
    check(id, !/^G0 .*F\d/.test(l), "F on rapid: " + l);
    check(id, !/undefined|NaN/.test(l), "undefined/NaN in output: " + l);
  }
  // first motion must be pure Z
  const fm = firstMotion(lines);
  check(id, fm !== null, "no motion");
  if (fm) {
    check(id, /Z/.test(fm) && !/X|Y/.test(fm), "first motion is not Z-only: " + fm);
    if (s.props.retractMode === "machine") check(id, /^G53 G0 Z/.test(fm), "machine mode first motion must be G53 G0 Z: " + fm);
  }
  // ordering: G90 and G21 before first motion; WCS selected before first WCS motion
  const idxFirstMotion = lines.findIndex(l => l === fm);
  check(id, lines.slice(0, idxFirstMotion).some(l => l === "G90" || l.startsWith("G90")), "G90 before first motion");
  check(id, lines.slice(0, idxFirstMotion).some(l => l === "G21"), "G21 before first motion");
  const firstWcsMotion = lines.findIndex(l => /^G0 /.test(l));
  check(id, lines.slice(0, firstWcsMotion).some(l => /^G5[4-9]/.test(l)), "WCS selected before first G0");
  // spindle on before any cutting move and off at the end
  let relMode = false, firstG1 = -1;
  for (let i = 0; i < lines.length; i++) { const l = lines[i]; if (/^G91\b/.test(l)) relMode = true; else if (/^G90\b/.test(l)) relMode = false; else if (!relMode && /^G1 /.test(l)) { firstG1 = i; break; } }
  check(id, lines.slice(0, firstG1).some(l => /^M[34] S\d+/.test(l)), "spindle M3/M4 S before first cutting G1");
  const lastM5 = lines.lastIndexOf("M5"), lastMotion = lines.map((l, i) => /^(G53 )?G[0-3] /.test(l) ? i : -1).filter(i => i >= 0).pop();
  check(id, lastM5 > 0, "no M5 at end");
  if (s.props.endPosition === "park") check(id, lastMotion > lastM5, "park move should follow M5");
  // every section's cutting coordinates preserved in order
  const expectedG1 = [];
  for (const sec of s.job.sections) {
    let p = { x: sec.initial.x, y: sec.initial.y, z: sec.initial.z };
    for (const m of (sec.moves || [])) {
      if (m.type === "linear") { const q = { x: m.x === undefined ? p.x : m.x, y: m.y === undefined ? p.y : m.y, z: m.z === undefined ? p.z : m.z }; if (q.x !== p.x || q.y !== p.y || q.z !== p.z) expectedG1.push(q); p = q; }
      else if (m.type === "rapid" || m.type === "arc") { p = { x: m.x === undefined ? p.x : m.x, y: m.y === undefined ? p.y : m.y, z: m.z === undefined ? p.z : m.z }; }
    }
  }
  if (!s.props.applyBacklashCompensation) {
    // replay the output to recover positions after each G1 and compare
    let cur = { x: null, y: null, z: null }; const seenG1 = []; let rel = false;
    for (const l of code) {
      if (/^G91\b/.test(l)) { rel = true; continue; } if (/^G90\b/.test(l) && !/G0|G1/.test(l)) { rel = false; continue; }
      if (rel || /\bH1\b/.test(l)) continue;
      const m = /^(G53 )?(G90 )?(G[0-3])\b(.*)$/.exec(l); if (!m) continue;
      m[2] = m[3]; m[3] = m[4];
      const w = m[3]; const g = (ax) => { const r = new RegExp("(^|\\s)" + ax + "(-?[\\d.]+)").exec(w); return r ? parseFloat(r[2]) : null; };
      if (!m[1]) { if (g("X") !== null) cur.x = g("X"); if (g("Y") !== null) cur.y = g("Y"); if (g("Z") !== null) cur.z = g("Z"); }
      if (m[2] === "G1" && !/G91/.test(l)) seenG1.push({ x: cur.x, y: cur.y, z: cur.z });
    }
    let si = 0;
    for (const e of expectedG1) {
      let found = false;
      while (si < seenG1.length) { const g = seenG1[si++]; if (Math.abs(g.x - e.x) < 1e-3 && Math.abs(g.y - e.y) < 1e-3 && Math.abs(g.z - e.z) < 1e-3) { found = true; break; } }
      check(id, found, "cutting move missing or out of order: X" + e.x + " Y" + e.y + " Z" + e.z);
      if (!found && process.env.DEBUG_REPLAY) { console.log("expected:", JSON.stringify(e), "si=", si, "seen around:", JSON.stringify(seenG1.slice(Math.max(0, si - 3), si + 3))); break; }
    }
  }
  // feed appears on the first G1 of each section
  const g1s = code.filter(l => /^G1 /.test(l) && !/H1/.test(l));
  check(id, g1s.length === 0 || /F\d/.test(g1s[0]), "first G1 has no feed: " + g1s[0]);
  // probing / positions never assume a positive Z is safe without the configured strategy: Z of initial positioning equals clearance
  for (const sec of s.job.sections) check(id, code.some(l => l === "G0 Z" + sec.initial.z || l === "G90 G0 Z" + sec.initial.z), "clearance Z" + sec.initial.z + " never commanded for " + sec.name);
}

function scenarioChecks(s, res) {
  const id = s.id, L = res.lines.map(l => l.replace(/^N\d+\s*/, ""));
  const idx = (re, from) => L.findIndex((l, i) => i >= (from || 0) && re.test(l));
  switch (id) {
    case "01_spot_drill_64_defaults": {
      check(id, L.filter(l => /^G1 Z-0\.508/.test(l)).length === 64, "64 drill plunges");
      check(id, L.filter(l => /^G1 Z-0\.508 F203$/.test(l)).length >= 1 && !L.some(l => /^G1 Z-0\.508 F\d+/.test(l) && !/F203$/.test(l)), "plunge feed 203");
      check(id, L.some(l => l === "M3 S5000"), "M3 S5000");
      check(id, L.some(l => l === "G4 P12500"), "proportional dwell 12.5s -> G4 P12500 (upstream value preserved)");
      const i54 = idx(/^G54$/), iz = idx(/^(G90 )?G0 Z15\.24$/), ixy = idx(/^G0 X20 Y20$/);
      check(id, i54 > 0 && iz > i54 && ixy > iz, "order G54 -> G0 Z15.24 -> G0 X20 Y20 (got " + i54 + "," + iz + "," + ixy + ")");
      check(id, L.some(l => /^M291 .*S3/.test(l)) && idx(/^M291 .*S3/) < iz, "blocking start confirmation before first motion");
      break; }
    case "02_spot_drill_64_machineZ": {
      const ig = idx(/^G53 G0 Z-2$/), ixy = idx(/^(G90 )?G0 X20 Y20$/), iz = idx(/^G0 Z15\.24$/, ixy);
      check(id, ig >= 0 && ixy > ig && iz > ixy, "G53 Z -> XY -> Z clearance");
      break; }
    case "03_pecking_with_dwell": {
      check(id, L.filter(l => l === "G4 P500").length === 3, "0.5 s cycle dwell -> G4 P500 x3");
      check(id, L.filter(l => /^G1 Z-6 F150$/.test(l) || /^G1 Z-6$/.test(l)).length === 3, "three holes to Z-6");
      break; }
    case "04_contour_radius_arcs": check(id, L.some(l => /^G3 X60 Y10 R10 F1000$/.test(l) || /^G3 X60 Y10 R10$/.test(l)), "CCW arc with R10"); break;
    case "05_contour_ij_arcs": check(id, L.some(l => /^G3 X60 Y10 I0 J10/.test(l) || /^G90 G3 X60 Y10 J10/.test(l) || /^G3 X60 Y10 J10/.test(l)), "CCW arc with IJ: " + L.filter(l => /^G(90 )?G?3 /.test(l)).join(" | ")); break;
    case "06_pocket_same_tool_rpm_change": {
      check(id, L.filter(l => /^M3 S/.test(l)).length === 2 && L.some(l => l === "M3 S14000"), "RPM change -> second M3");
      check(id, !L.some(l => /TOOL CHANGE ROUTINE/.test(l)), "no tool change between same-tool ops");
      const iM3 = idx(/^M3 S14000/); check(id, L[iM3 + 3] === "G4 P5000" || L.slice(iM3, iM3 + 5).some(l => l === "G4 P5000"), "proportional dwell for 2000rpm change clamps to 5 s");
      break; }
    case "07_adaptive_split_rapids": {
      const iu = idx(/^G0 Z8$/); check(id, iu > 0 && /^G0 X10 Y10$/.test(L[iu + 1]), "upward XYZ rapid split Z first then XY");
      const id2 = idx(/^G0 X30 Y30$/); check(id, id2 > 0 && /^G0 Z2$/.test(L[id2 + 1]), "downward XYZ rapid split XY first then Z");
      break; }
    case "08_adaptive_no_split": check(id, L.some(l => /^G0 X10 Y10 Z8$/.test(l)), "combined rapid kept when splitting disabled"); break;
    case "09_toolchange_manual_defaults":
    case "10_toolchange_manual_machineZ": {
      const tc = idx(/TOOL CHANGE ROUTINE BEGINS/);
      check(id, tc > 0, "tool change routine present");
      const seq = L.slice(tc, tc + 14).filter(l => !l.startsWith(";"));
      const order = ["M5", "G4 P10000", "G53 G0 Z-1", "G53 G0 X10 Y10", "M400"];
      let last = -1; for (const o of order) { const k = seq.indexOf(o); check(id, k > last, "tool change order, expected " + o + " after previous (seq: " + seq.join(" | ") + ")"); last = k; }
      const prompt = idx(/^M291 .*Tool change.*S3/, tc); check(id, prompt > tc, "blocking tool change prompt (S3)");
      // after the change: XY at safe Z, then Z clearance, then spindle restarted before cutting
      const after = idx(/TOOL CHANGE ROUTINE ENDS/, tc);
      const mv = L.slice(after).filter(l => /^(G53 )?G0 /.test(l));
      check(id, /^G90 G0 X0 Y-10$|^G0 X0 Y-10$/.test(mv[0]) && /^G0 Z15$/.test(mv[1]), "after tool change: XY at safe Z then Z clearance (" + mv.slice(0, 2).join(" | ") + ")");
      check(id, idx(/^M3 S12000/, after) > after && idx(/^M3 S12000/, after) < idx(/^G1 /, after), "spindle restarted before first cut of T2");
      check(id, L.filter(l => /TOOL CHANGE ROUTINE BEGINS/.test(l)).length === 2, "two tool changes (T1->T2, T2->T3)");
      check(id, L.some(l => l === "M4 S18000"), "CCW tool uses M4");
      if (id.endsWith("machineZ")) { check(id, L.slice(L.lastIndexOf("M5")).some(l => l === "G53 G0 X10 Y10"), "park at end"); }
      break; }
    case "11_toolchange_not_manual": check(id, !L.some(l => /TOOL CHANGE ROUTINE/.test(l)) && L.filter(l => l === "M5").length >= 2 && L.filter(l => /^M3 S/.test(l)).length === 2, "non-manual change: M5 then new M3, no routine"); break;
    case "12_toolchange_with_zprobe": {
      check(id, L.some(l => /^M585 Z60 E3 L0 F300 S1$/.test(l)), "Z probe M585 toward Z min");
      check(id, L.some(l => /^G10 L20 P1 Z3$/.test(l)) && L.some(l => l === "M500"), "G10 L20 P1 Z3 + M500 in Z probe");
      const ip = idx(/Z PROBE ENDS/); check(id, /^G53 G0 Z-1$/.test(L.slice(ip).filter(l => !l.startsWith(";"))[0]), "G53 retract right after probe");
      break; }
    case "13_toolchange_with_cornerprobe_and_home": check(id, L.some(l => l === "G28") && L.some(l => /CORNER PROBE BEGINS/.test(l)) && idx(/^G28$/) < idx(/CORNER PROBE BEGINS/), "G28 then corner probe"); break;
    case "14_g54_then_g55": {
      const i55 = idx(/^G55$/); check(id, i55 > idx(/^G54$/), "G55 after G54");
      check(id, /^G90 G0 Z12$/.test(L[i55 + 1]) || /^G0 Z12$/.test(L[i55 + 1]), "after G55 first move is Z clearance in new WCS: " + L[i55 + 1]);
      check(id, !L.some(l => /TOOL CHANGE ROUTINE/.test(l)), "no tool change on WCS change with same tool");
      break; }
    case "15_g54_then_g55_machineZ": { const i55 = idx(/^G55$/); check(id, L.slice(i55 - 3, i55).some(l => l === "G53 G0 Z-1") || L[i55 + 1] === "G53 G0 Z-1", "G53 retract around WCS change"); break; }
    case "16_setup_wcs0_uses_property": check(id, L.some(l => l === "G55") && !L.some(l => l === "G54"), "setup WCS 0 -> property G55"); break;
    case "18_wcs9_allowed": check(id, L.some(l => l === "G59.3"), "WCS 9 -> G59.3"); break;
    case "19_tn_fusion": check(id, L.some(l => l === "T1") && L.some(l => l === "T2"), "T1 and T2 output"); break;
    case "20_tn_fixed": check(id, L.filter(l => l === "T0").length === 2 && !L.some(l => /^T[12]$/.test(l)), "fixed T0"); break;
    case "21_spindle_dwell_none": check(id, !L.some(l => /^G4 /.test(l)), "no G4 at all"); break;
    case "22_spindle_dwell_fixed": check(id, L.filter(l => l === "G4 P3000").length === 2 && !L.some(l => l === "G4 P12500"), "fixed 3 s dwell twice"); break;
    case "23_quiet_no_confirm_M0_park": {
      check(id, !L.some(l => /^M291 .*S[01]/.test(l)), "no informational M291");
      check(id, !L.some(l => /^M291 .*S3/.test(l)), "no start confirmation");
      check(id, L[L.length - 5] === "M0" || L.slice(-6).includes("M0"), "M0 near end");
      check(id, L.some(l => l === "G53 G0 X0 Y300"), "park XY");
      break; }
    case "24_manual_nc_commands": {
      check(id, L.some(l => /^M291 .*Program stop.*S2$/.test(l)), "COMMAND_STOP -> blocking M291 S2");
      check(id, L.some(l => l === "G4 P2000"), "2 s manual dwell -> G4 P2000");
      check(id, L.some(l => l === "M3 S15000"), "onSpindleSpeed -> M3 S15000");
      check(id, L.some(l => l === "M117 custom"), "pass-through written");
      break; }
    case "26_sequence_numbers": check(id, res.lines.some(l => /^N\d+ G0 Z15$/.test(l) || /^N\d+ G90 G0 Z15$/.test(l)) && res.lines.filter(l => /^N\d+ /.test(l)).length > 20, "sequence numbers present with spaces"); break;
    case "27_backlash_steps": check(id, L.some(l => /^M92 X/.test(l)), "M92 compensation emitted"); break;
    case "29_corner_probe_on_start": check(id, idx(/CORNER PROBE BEGINS/) < idx(/^G0 /) || idx(/CORNER PROBE BEGINS/) < idx(/^G90 G0/), "corner probe before first positioning"); break;
  }
}

// ---------------------------------------------------------------- run
let pass = 0, fail = 0;
const report = [];
for (const s of scenarios) {
  const before = problems.length;
  let res;
  try { res = run(CPS, s.job, s.props); } catch (e) { problems.push(s.id + ": EXCEPTION " + (e.stack || e)); report.push([s.id, "EXCEPTION"]); fail++; continue; }
  fs.writeFileSync(path.join(OUT, s.id + ".gcode"), res.text);
  if (s.example) fs.writeFileSync(path.join(EXAMPLES, s.example), res.text);
  if (s.expectError) {
    check(s.id, res.error && s.expectError.test(res.error), "expected error " + s.expectError + " got: " + res.error);
  } else {
    check(s.id, !res.error, "post reported error: " + res.error);
    if (!res.error) { genericChecks(s, res); scenarioChecks(s, res); }
  }
  const ok = problems.length === before;
  if (ok) pass++; else fail++;
  report.push([s.id, ok ? "PASS" : "FAIL", res.warnings.join("; ")]);
}
for (const r of report) console.log(r[1].padEnd(5), r[0].padEnd(42), r[2] ? "warnings: " + r[2] : "");
console.log("\n" + pass + " passed, " + fail + " failed");
if (problems.length) { console.log("\nPROBLEMS:"); for (const p of problems) console.log(" - " + p); process.exitCode = 1; }
