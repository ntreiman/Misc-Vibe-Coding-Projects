# Changelog: Duet2Ethernet_RRF2051.cps vs upstream UltimateRRPost.cps R1.5

Upstream: https://github.com/BruceRoyce/UltimateRepRapPost, `UltimateRRPost.cps`, `$R 1.5 $`, 2021-03-17,
Apache License 2.0. The uploaded copy was byte-identical to upstream `main` on 2026-11-19. The unmodified
file is kept in `upstream/`.

Every RepRapFirmware claim below was checked against the RRF 2.05.1 source tree
(`src/GCodes/GCodes.cpp`, `GCodes2.cpp`, `GCodes3.cpp`, `GCodeBuffer.cpp`, `RepRap.cpp`) and the Duet
G-code dictionary (https://docs.duet3d.com/User_manual/Reference/Gcodes).

## 2.8 (2026-11-22)

- New integer property **Descriptive file name run number** (default 0): > 0 appends `_run<n>` to the
  descriptive file name. Used by the new `BatchPostByTool` Fusion add-in so that a tool used in two separate
  runs of a setup does not overwrite its first file.
- New `BatchPostByTool/` add-in (separate README): posts every consecutive run of same-tool operations of a
  setup to its own `op_<tool>_..._RPM.gcode` through the Fusion API, forcing the descriptive single-file
  naming via `PostProcessInput.postProperties`.

## 2.7 (2026-11-22)

- Single-file method reworked: `onTerminate()` now **copies** the finished output to the descriptive name
  and launches a background script (`/bin/sh` or `cmd.exe`) that deletes the dialog-named file 3 seconds
  later. Fusion validates that the dialog-named file exists after the post ("NC code failed to post" with
  2.6's rename), so it cannot be removed from inside the post. Confirmed working in Fusion 360 on macOS.

## 2.6 (2026-11-22)

- Rename method moved from the end of `onClose()` to `onTerminate()`. In Fusion the kernel writes the primary
  output file after `onClose()` returns, so 2.5 renamed an empty file (0 bytes) and the program stayed in
  the dialog-named file. The reference states the primary output cannot be opened until `onTerminate()`.

## 2.5 (2026-11-22)

- New enum **Descriptive file name method**: Redirect (default, as before) or Rename at end. Rename writes
  the program to the dialog-named file and moves it to the descriptive name with `FileSystem.moveFile()` as
  the last action of `onClose()`, so only one file remains and Fusion stops asking to overwrite the stub.

## 2.4 (2026-11-22)

- **Descriptive output file name** is now on by default.

## 2.3 (2026-11-22)

- Descriptive file name is now `op_<tool number>_<diameter>_<tool type>_<rpm>RPM.gcode` by default
  (literal `op` before every tool number so files sort in tool order; the `T` letter is dropped). New enum
  **Descriptive file name prefix**: op (default), None, Operation name(s), Program name/number. The 2.1
  behaviour (program number first) was confirmed working in Fusion 360
  (`1001_T0_3.175_flat_end_mill_18000RPM.gcode`) before being changed on request.

## 2.1 (2026-11-22)

- New property **Descriptive output file name** (default off). When on, `onOpen()` builds
  `<program>_T<n>_<diameter>_<tool type>_<rpm>RPM[.._T<m>...].gcode` from the tools in order of first use
  and redirects all output there with `redirectToFile()`; `onClose()` ends the redirection. The kernel has no
  way to rename its own output, so the dialog-named file still exists and holds one pointer comment.

## 2.0 (2026-11-19)

### Motion safety

- **Z clearance before XY at program start, tool changes and WCS changes** (`onSection()`). Upstream wrote
  `G0 X Y` then `G0 Z` whenever `insertToolCall` was true, i.e. for the first operation and after every tool
  change, and skipped its "retract if below clearance" check in exactly those cases. This is the crash in
  upstream issue #5 and in the user's `1001.cnc.gcode`. The fork has one positioning routine with two
  strategies (property *Retract strategy*): Fusion clearance height in the active WCS (default, no invented
  numbers) or `G53 G0 Z<Safe machine Z>` (machine coordinates). Both write the Z move first. After a manual
  tool change, where the machine is known to sit at *Safe machine Z*, the XY traverse happens at that height
  and Z descends afterwards.
- **Retract before a WCS change.** Upstream only retracted on a WCS change when `useG28` was on (which
  homes, see below). The fork lifts to the previous operation's clearance height (or `G53` safe Z) before
  selecting the new WCS, then writes Z before XY in the new WCS.
- **End-of-program retract** to the last operation's clearance height or `G53` safe Z. Upstream's
  `writeRetract(Z)` did nothing with `useG28` off.
- **`G28` removed as a retract** (`useG28` property, `writeRetract()`, `onSection()` retract block). In
  RepRapFirmware `G28` **homes**; `G28 G91 Z0` homes Z (`DoHome()` reads only the axis letters). The only
  remaining `G28` is the explicit *Home all axes after tool change* option, off by default and labelled.
- **Manual tool change rebuilt on `G53`.** Upstream: `G60 S0` (save position), `G59.3`, `G1 Z0 F200`,
  `G0 X0`, `G0 Y0`, prompt, `G0 R0 Y0`, `G0 R0 X0`, `G0 R0 Z0`, then the job WCS. In RRF 2.05.1
  `SavePosition()` stores `currentUserPosition` and `G0 R0` restores it as user coordinates of the WCS active
  at that moment (`DoStraightMove()`: `currentUserPosition[axis] = moveArg + rp->moveCoords[axis]`, then the
  workplace offset is applied). WCS 9 was active during the restore, so the tool returned to the saved
  coordinates shifted by (WCS9 - job WCS). The fork writes `M5`, stop dwell, `G53 G0 Z<safe>`,
  `G53 G0 X<tc> Y<tc>`, `M400`, prompt, and lets the next operation position itself.
- **No more `G10 L2 P9` at program start.** Upstream overwrote the WCS 9 origin with the tool change
  position on every post unless *Use WCS9 as tool change home* was on. The fork never writes `G10 L2`.
- **`G1 H1 Z500` flush routines removed** (`bFlushAccumulatedCompensationError()`,
  `bflushAcCompErPerMotionCount()`, properties `emptyAccumulatedCompensationError`, `bCompensationCount`).
  `G1 H1` is an endstop-seeking move (homing style), and the routine then moved to WCS `X0 Y0` and
  **plunged to WCS `Z0`** (`G1 Z0`) with the spindle running. Off by default upstream, but too dangerous to
  leave in a file people copy settings into.
- **Split combined XY+Z rapids** (new property, default on): Z first when going up, XY first when going
  down. Cutting moves untouched.
- **Blocking start confirmation** (`M291 S3`, new property, default on) before the first motion: the
  operator confirms homed, zeroed, tool mounted. Replaces upstream's `M291 S2` "SAFETY FIRST" dialog, which
  had no Cancel.
- **`M0` no longer written by default** (new property *End program with M0*). RRF 2.05.1 `M0` from the job
  file runs `stop.g`, switches drives to idle current and calls `SetAllAxesNotHomed()` through
  `DisableDrives()`. The file now ends normally.
- **`M2` removed.** Not implemented in RRF 2.05.1 (no `case 2` in the M-code switch; reported as unsupported).
  `COMMAND_END` writes nothing.
- **`COMMAND_STOP` / `COMMAND_OPTIONAL_STOP`** (Fusion Manual NC) map to `M400` + blocking `M291 S2`
  instead of `M0` (ends the job) / `M1` (sleep in RRF).

### RRF 2.05.1 compatibility

- **Dwell units.** RRF `G4 P` is milliseconds, `G4 S` seconds (`DoDwell()`). Upstream `onDwell(seconds)`
  wrote `G4 P<seconds>` when *Dwell in seconds* was checked (default), so Fusion cycle dwells and Manual NC
  dwells were 1000x too short, while its own spindle dwell pre-multiplied by 1000. All dwells now go through
  `writeDwellSeconds()` -> `G4 P<integer ms>`. The `dwellInSeconds` property is gone.
- **`onSpindleSpeed()`** wrote a bare `S<rpm>` line (meaningless to RRF) followed by two fixed 15 s dwells.
  It now writes `M3`/`M4 S<rpm>` with the configured dwell.
- **Words are always space separated** (`separateWordsWithSpace` removed). RRF 2.05.1 `DecodeCommand()`
  starts a new command only at a space followed by `G` or `M`; `G90G0X0` would be read as `G90` with junk
  parameters and the move lost. `G53` is cleared at end of line (`SetFinished()`), so `G53 G0 ...` on one
  line is the correct form.
- **`M291` lines limited to 160 characters**, quotes and semicolons stripped from the text, `S0` always
  with a timeout (RRF rejects `S0 T0`).
- **Canned cycles made explicit**: `onCycle()`/`onCyclePoint()` -> `expandCyclePoint()` (what the kernel did
  implicitly when the functions were missing), tapping rejected with an error. `useRigidTapping` removed.
- **`G41`/`G42` radius compensation** now raises an error instead of writing unsupported codes.
- **Tool call made configurable** (`Tn output`: None / Fusion number / Fixed, default None). RRF 2.05.1
  `M3 S` drives spindle slot 0 regardless of the selected tool (`GCodes2.cpp` case 3: `slot = P ? P : 0`).
  `T<n>` for an undefined tool silently deselects all tools (`RepRap::SelectTool()` with `nullptr`) and runs
  `tfree`/`tpre`/`tpost` if present. Upstream always wrote `T<n>`; `useM6` and `preloadTool` (M6 does not
  exist in RRF) were removed.
- **WCS 9 (`G59.3`) is no longer reserved**; the error for setup WCS 9 with manual tool change is gone.
- **`G59.1`-`G59.3` output** goes through one `wcsCode()` helper; the enum ids of *WCS when setup is 0*
  are now `1`-`9` instead of G-code numbers.

### Spindle

- `spindleDwellMode` (Proportional / Fixed / None) added; Proportional keeps upstream's catch-up formula and
  5 s minimum (upstream issue #6 asked for a way to disable it). The spindle direction-change doubling is
  kept. The 15 s chunking with `M450` was dropped (RRF handles long `G4` fine).
- `spindleStopDwellSeconds` added (default 10 s, the value upstream used at program end). Upstream wrote
  `M3 S0` + 10 s + `M5` at the end and `M5` with no wait before the slow `G1 Z0 F200` at tool changes.
- Spindle state is tracked in one object (`spindleState`); upstream's `bTool.lastDir` was only updated when
  `lastRpm != 0`, so a counter-clockwise first tool re-emitted `M4 S` at every operation.

### Operator messages

- `informationalMessages` property: operation name, dwell notice and program end are non-blocking and can be
  switched off. Safety prompts stay.
- `beepOn` kept.

### Output quality

- Motion box: upstream initialised min/max at `[0, 0]` (so 0 was always inside the box), had a `for (i=0;
  i>3; ...)` loop that never ran, and only tracked positions when backlash compensation was on. Now tracked
  for all commanded moves and printed per axis, `[no moves]` if none.
- Backlash compensation: `compFlag = bCompensation.x` stored the function instead of calling it (always
  truthy); fixed. Arcs are linearised when the *Distance* method is on (shifted end points would not close).
  Default `applyBacklashCompensation` changed from `true` to `false` (upstream had it on with all values 0).
- Header: configuration summary and prerequisites block added; `printType` (laser/plasma/3D printer
  extensions, "to be developed") removed; extension is `.gcode`.
- `onPassThrough()` added for Fusion Manual NC pass-through.
- Coolant: upstream's `setCoolant()` had its output commented out; the dead code and `useDustCollector`
  property were removed. `COMMAND_COOLANT_ON/OFF` are ignored.
- Multi-axis code paths (`onRapid5D`, `onLinear5D`, work plane rotation) now error out; upstream kept
  Autodesk's 5-axis scaffolding that this 3-axis post cannot exercise.
- Probe routines kept with the same `M585`/`G10 L20`/`M500` logic, defaults changed to **off**
  (`probeToolOnChange` was `"1"` = Z-probe upstream). The Z-probe prompt now allows jogging, the Z-probe XY
  position is a property, and the post re-retracts with `G53` after any probe or homing.

### Unchanged on purpose

- Arc output (R / IJ, 90 degree split in R mode), number formats, sequence numbers.
- Upstream's `M585` probe direction (`S1` = toward axis minimum, verified in `ProbeTool()`).
- `M300` beep, `M400` waits.
- The error for mixing setup WCS 0 with non-zero setup WCS offsets.
