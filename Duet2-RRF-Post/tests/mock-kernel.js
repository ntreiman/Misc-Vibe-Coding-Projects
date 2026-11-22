/*
  Minimal mock of the Autodesk Fusion 360 post-processor kernel API, sufficient to execute
  Duet2Ethernet_RRF2051.cps against synthetic toolpaths. It is NOT the Autodesk kernel:
  number formatting, cycle expansion and position tracking are approximations written from
  the documented behaviour of the kernel. Use it for control-flow and sequencing checks only.
*/
"use strict";
const vm = require("vm");
const fs = require("fs");

function Vector(x, y, z) { this.x = x; this.y = y; this.z = z; }
Vector.prototype.length = function () { return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z); };
Vector.diff = (a, b) => new Vector(a.x - b.x, a.y - b.y, a.z - b.z);

class Range { constructor(min, max) { this.min = min; this.max = max; }
  getMinimum() { return this.min; } getMaximum() { return this.max; }
  expandToRange(r) { this.min = Math.min(this.min, r.min); this.max = Math.max(this.max, r.max); } }

function makeTool(t) {
  return Object.assign({ number: 1, diameter: 6, cornerRadius: 0, taperAngle: 0, spindleRPM: 10000, clockwise: true,
    lengthOffset: 1, coolant: 0, comment: "", type: 1, numberOfFlutes: 2 }, t);
}

function run(cpsPath, job, propertyOverrides, opts) {
  opts = opts || {};
  const out = [];
  const redirected = []; // {path, lines}
  let target = out;
  const warnings = [];
  let errorMsg = null;
  let wordSeparator = " ";
  const unit = job.unit === "IN" ? 1 : 0; // IN=1, MM=0 (matches Fusion constants)
  const MM = 0, IN = 1;

  // ----- formats / variables / modals -----
  function createFormat(spec) {
    const decimals = spec.decimals === undefined ? 6 : spec.decimals;
    const scale = spec.scale || 1;
    const fmt = {
      format(v) {
        if (typeof v !== "number" || isNaN(v)) return (spec.prefix || "") + v;
        let s = (v * scale).toFixed(decimals);
        if (!spec.forceDecimal && decimals > 0) s = s.replace(/\.?0+$/, "");
        if (s === "-0") s = "0";
        return (spec.prefix || "") + s;
      },
      areDifferent(a, b) { return fmt.format(a) !== fmt.format(b); }
    };
    return fmt;
  }
  function createVariable(spec, format) {
    let current, first = true, enabled = true;
    return {
      format(v) {
        if (!enabled) return "";
        const s = format.format(v);
        if (!first && !spec.force && current === s) return "";
        first = false; current = s;
        if (spec.onchange) spec.onchange();
        return (spec.prefix || "") + s;
      },
      reset() { first = true; current = undefined; },
      getCurrent() { return current === undefined ? undefined : parseFloat(current); },
      enable() { enabled = true; }, disable() { enabled = false; }
    };
  }
  function createReferenceVariable(spec, format) {
    return { format(v, ref) { const s = format.format(v); if (ref !== undefined && format.format(ref) === s && !spec.force) return ""; return (spec.prefix || "") + s; }, reset() {} };
  }
  function createModal(spec, format) {
    let current;
    return {
      format(v) { const s = format.format(v); if (!spec.force && current === s) return ""; current = s; if (spec.onchange) spec.onchange(); return s; },
      reset() { current = undefined; }
    };
  }
  function formatWords(args) {
    const words = [];
    const flat = [];
    const isList = (w) => Array.isArray(w) || (w && typeof w === "object" && typeof w.length === "number" && !(w instanceof String));
    (function walk(a) { for (const w of Array.from(a)) { if (isList(w)) walk(w); else if (w !== undefined && w !== null && w !== "") flat.push(String(w)); } })(args);
    return flat.join(wordSeparator);
  }
  function writeln(s) { target.push(String(s)); }
  function writeWords() { const t = formatWords(arguments); if (t) target.push(t); }
  function writeWords2(n, args) { const t = formatWords(args); if (t) target.push(n + wordSeparator + t); }
  const outputPath = opts.outputPath || "/out/" + (job.programName || "1001") + ".gcode";
  const fsOps = [];
  const FileSystem = {
    isFile(p) { return !!(opts.existingFiles || []).includes(p); },
    remove(p) { fsOps.push(["remove", p]); },
    moveFile(a, b) { fsOps.push(["move", a, b]); },
    getFolderPath(p) { return p.replace(/[\\/][^\\/]*$/, ""); },
    getFilename(p) { return p.replace(/^.*[\\/]/, ""); },
    getCombinedPath(a, b) { return a.replace(/[\\/]$/, "") + "/" + b; },
    replaceExtension(p, e) { return p.replace(/\.[^.\\/]*$/, "") + "." + e; }
  };

  // ----- job model -----
  const sections = job.sections.map((s, i) => {
    const tool = makeTool(s.tool);
    const params = Object.assign({ "operation-comment": s.name || ("Op " + (i + 1)) }, s.params || {});
    if (s.cycle) params["operation:cycleType"] = s.cycle.type;
    const zs = [];
    for (const m of s.moves) if (m.z !== undefined) zs.push(m.z);
    if (s.cycle) for (const p of s.cycle.points) zs.push(p.z);
    return {
      id: i, workOffset: s.workOffset === undefined ? 1 : s.workOffset,
      workPlane: { forward: new Vector(0, 0, 1) },
      getId() { return i; }, getTool() { return tool; },
      getInitialPosition() { return new Vector(s.initial.x, s.initial.y, s.initial.z); },
      getGlobalZRange() { return new Range(Math.min(...zs), Math.max(...zs)); },
      isMultiAxis() { return false; }, getForceToolChange() { return !!s.forceToolChange; },
      hasParameter(k) { return k in params; }, getParameter(k) { return params[k]; },
      isOptimizedForMachine() { return false; },
      _src: s
    };
  });

  let currentIndex = -1;
  let pos = new Vector(0, 0, 0);
  let nextRecordIsMotion = true;
  let cycleCtx = null;
  const toolsByNumber = {};
  for (const sec of sections) toolsByNumber[sec.getTool().number] = sec.getTool();

  const COMMANDS = ["COMMAND_STOP", "COMMAND_OPTIONAL_STOP", "COMMAND_END", "COMMAND_SPINDLE_CLOCKWISE", "COMMAND_SPINDLE_COUNTERCLOCKWISE",
    "COMMAND_STOP_SPINDLE", "COMMAND_START_SPINDLE", "COMMAND_COOLANT_ON", "COMMAND_COOLANT_OFF", "COMMAND_LOCK_MULTI_AXIS", "COMMAND_UNLOCK_MULTI_AXIS",
    "COMMAND_BREAK_CONTROL", "COMMAND_TOOL_MEASURE", "COMMAND_LOAD_TOOL"];

  const sandbox = {
    console, Math, Number, String, Array, Object, Date, parseInt, parseFloat, isNaN, RegExp,
    MM, IN, DEG: 180 / Math.PI, PLANE_XY: 0, PLANE_ZX: 1, PLANE_YZ: 2,
    RADIUS_COMPENSATION_OFF: 0, RADIUS_COMPENSATION_LEFT: 1, RADIUS_COMPENSATION_RIGHT: 2,
    CAPABILITY_MILLING: 1, unit, Vector,
    programName: job.programName || "1001", programComment: job.programComment || "",
    machineConfiguration: { getVendor() { return job.vendor || ""; }, getModel() { return job.model || ""; }, getDescription() { return ""; },
      isMultiAxisConfiguration() { return false; }, isHeadConfiguration() { return false; }, isMachineCoordinate() { return false; } },
    radiusCompensation: 0,
    setCodePage() {}, spatial(v) { return v; }, toRad(d) { return d * Math.PI / 180; }, toDeg(r) { return r * 180 / Math.PI; },
    localize(s) { return s; }, subst(s) { return s; }, conditional(c, v) { return c ? v : ""; },
    error(m) { errorMsg = errorMsg || m; target.push("!!! ERROR: " + m); }, warning(m) { warnings.push(m); },
    writeln, write(s) { target.push(String(s)); }, writeWords, writeWords2, formatWords,
    FileSystem, getOutputPath() { return outputPath; },
    redirectToFile(p) { const r = { path: p, lines: [] }; redirected.push(r); target = r.lines; },
    closeRedirection() { target = out; }, isRedirecting() { return target !== out; },
    setWordSeparator(s) { wordSeparator = s; },
    filterText(t, allowed) { let r = ""; for (const ch of String(t)) r += allowed.indexOf(ch) >= 0 ? ch : " "; return r; },
    createFormat, createVariable, createReferenceVariable, createModal,
    getNumberOfSections() { return sections.length; }, getSection(i) { return sections[i]; },
    isFirstSection() { return currentIndex === 0; }, isLastSection() { return currentIndex === sections.length - 1; },
    getPreviousSection() { return sections[currentIndex - 1]; }, getNextSection() { return sections[currentIndex + 1]; },
    getCurrentSectionId() { return currentIndex; },
    getFramePosition(v) { return v; }, getCurrentPosition() { return pos; }, setCurrentPosition(v) { pos = v; },
    getToolTable() { const nums = Object.keys(toolsByNumber).map(Number).sort((a, b) => a - b); return { getNumberOfTools() { return nums.length; }, getTool(i) { return toolsByNumber[nums[i]]; } }; },
    is3D() { return true; }, getToolTypeName() { return "flat end mill"; },
    isSameDirection(a, b) { return Math.abs(a.x - b.x) < 1e-9 && Math.abs(a.y - b.y) < 1e-9 && Math.abs(a.z - b.z) < 1e-9; },
    setRotation() {}, getNextRecord() { return { isMotion() { return nextRecordIsMotion; } }; },
    getCommandStringId(c) { return COMMANDS[c]; },
    onUnsupportedCommand(c) { out.push("!!! UNSUPPORTED COMMAND " + c); }, onUnsupportedCoolant() {},
    hasParameter(k) { return sections[currentIndex].hasParameter(k); }, getParameter(k) { return sections[currentIndex].getParameter(k); },
    // circular helpers are set per call
    isFullCircle() { return sandbox._arc.full; }, getCircularPlane() { return 0; }, getCircularRadius() { return sandbox._arc.r; },
    getCircularSweep() { return sandbox._arc.sweep; }, isHelical() { return sandbox._arc.helical; },
    linearize() { const a = sandbox._arc; const n = 8; for (let i = 1; i <= n; i++) { const ang = a.a0 + (a.a1 - a.a0) * i / n; const x = a.cx + a.r * Math.cos(ang), y = a.cy + a.r * Math.sin(ang); const z = a.z0 + (a.z1 - a.z0) * i / n; sandbox.onLinear(x, y, z, a.feed); pos = new Vector(x, y, z); } a.linearized = true; },
    expandCyclePoint(x, y, z) {
      const c = cycleCtx; // Fusion-style expansion of a drilling/chip-breaking cycle
      const retract = c.retract, clearance = c.clearance, bottom = z;
      if (pos.x !== x || pos.y !== y) { sandbox.onRapid(x, y, pos.z); pos = new Vector(x, y, pos.z); }
      if (pos.z !== retract) { sandbox.onRapid(x, y, retract); pos = new Vector(x, y, retract); }
      if (c.type === "chip-breaking" || c.type === "deep-drilling") {
        let depth = retract; const inc = c.incrementalDepth || 1;
        while (depth > bottom + 1e-9) {
          depth = Math.max(bottom, depth - inc);
          sandbox.onLinear(x, y, depth, c.feedrate); pos = new Vector(x, y, depth);
          if (depth > bottom + 1e-9) {
            const up = c.type === "deep-drilling" ? retract : Math.min(retract, depth + (c.chipBreakDistance || 0.5));
            sandbox.onRapid(x, y, up); pos = new Vector(x, y, up);
            if (c.type === "deep-drilling") { sandbox.onRapid(x, y, depth + 0.5); pos = new Vector(x, y, depth + 0.5); }
          }
        }
      } else {
        sandbox.onLinear(x, y, bottom, c.feedrate); pos = new Vector(x, y, bottom);
      }
      if (c.dwell) sandbox.onDwell(c.dwell);
      sandbox.onRapid(x, y, retract); pos = new Vector(x, y, retract);
    }
  };
  for (let i = 0; i < COMMANDS.length; i++) sandbox[COMMANDS[i]] = i;
  vm.createContext(sandbox);
  const src = fs.readFileSync(cpsPath, "utf8");
  vm.runInContext(src, sandbox, { filename: cpsPath });
  if (typeof sandbox.properties !== "object") throw new Error("post did not define properties");
  Object.assign(sandbox.properties, propertyOverrides || {});

  // ----- drive the post -----
  sandbox.onOpen();
  for (let i = 0; i < sections.length && !errorMsg; i++) {
    currentIndex = i;
    const sec = sections[i];
    sandbox.currentSection = sec;
    sandbox.tool = sec.getTool();
    sandbox.onSection();
    if (errorMsg) break;
    pos = sec.getInitialPosition(); // kernel: post is responsible for moving to the initial position
    const s = sec._src;
    if (s.cycle) {
      cycleCtx = Object.assign({ clearance: s.initial.z }, s.cycle);
      sandbox.cycleType = s.cycle.type; sandbox.cycle = cycleCtx;
      sandbox.onCycle();
      for (const p of s.cycle.points) { if (errorMsg) break; sandbox.onCyclePoint(p.x, p.y, p.z); }
      sandbox.onCycleEnd();
      // kernel retracts to clearance at cycle end via a rapid record
      if (!errorMsg) { sandbox.onRapid(pos.x, pos.y, cycleCtx.clearance); pos = new Vector(pos.x, pos.y, cycleCtx.clearance); }
      sandbox.cycleType = undefined; sandbox.cycle = undefined; cycleCtx = null;
    }
    const moves = s.moves || [];
    let lastFeed = 0;
    for (let m = 0; m < moves.length && !errorMsg; m++) {
      const mv = moves[m];
      if (mv.feed !== undefined) lastFeed = mv.feed;
      nextRecordIsMotion = m + 1 < moves.length;
      const x = mv.x === undefined ? pos.x : mv.x, y = mv.y === undefined ? pos.y : mv.y, z = mv.z === undefined ? pos.z : mv.z;
      if (mv.type === "rapid") sandbox.onRapid(x, y, z);
      else if (mv.type === "linear") sandbox.onLinear(x, y, z, lastFeed);
      else if (mv.type === "arc") {
        const a0 = Math.atan2(pos.y - mv.cy, pos.x - mv.cx), r = Math.hypot(pos.x - mv.cx, pos.y - mv.cy);
        let a1 = Math.atan2(y - mv.cy, x - mv.cx);
        let sweep = mv.clockwise ? (a0 - a1) : (a1 - a0); while (sweep <= 1e-9) sweep += 2 * Math.PI; while (sweep > 2 * Math.PI) sweep -= 2 * Math.PI;
        const full = Math.abs(pos.x - x) < 1e-9 && Math.abs(pos.y - y) < 1e-9;
        sandbox._arc = { full, r, sweep: full ? 2 * Math.PI : sweep, helical: Math.abs(z - pos.z) > 1e-9, cx: mv.cx, cy: mv.cy, a0, a1: mv.clockwise ? a0 - sweep : a0 + sweep, z0: pos.z, z1: z, feed: lastFeed };
        sandbox.onCircular(mv.clockwise, mv.cx, mv.cy, z, x, y, z, lastFeed);
      }
      else if (mv.type === "dwell") sandbox.onDwell(mv.seconds);
      else if (mv.type === "spindle") sandbox.onSpindleSpeed(mv.rpm);
      else if (mv.type === "command") sandbox.onCommand(sandbox[mv.command]);
      else if (mv.type === "comment") sandbox.onComment(mv.text);
      else if (mv.type === "passthrough") sandbox.onPassThrough(mv.text);
      if (mv.type === "rapid" || mv.type === "linear" || mv.type === "arc") pos = new Vector(x, y, z);
    }
    sandbox.onSectionEnd();
  }
  if (!errorMsg) sandbox.onClose();
  // kernel writes and closes the primary output file, then calls onTerminate()
  fsOps.push(["kernel-wrote", outputPath]);
  if (typeof sandbox.onTerminate === "function") sandbox.onTerminate();
  if (redirected.length) {
    // the main file only holds the pointer comment; the program is in the redirected file
    return { text: redirected[0].lines.join("\n") + "\n", lines: redirected[0].lines, mainFileLines: out, redirectedPath: redirected[0].path, warnings, error: errorMsg, properties: sandbox.properties, fsOps };
  }
  return { text: out.join("\n") + "\n", lines: out, warnings, error: errorMsg, properties: sandbox.properties, fsOps };
}

module.exports = { run, makeTool };
