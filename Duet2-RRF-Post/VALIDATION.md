# Validation report

Date: 2026-11-22. Post: `Duet2Ethernet_RRF2051.cps` 2.7 (first written 2026-11-19 for 2.0). Firmware reference: RepRapFirmware 2.05.1 source
and the Duet G-code dictionary.

## What was verified

### Source review of upstream

The complete upstream `UltimateRRPost.cps` (2128 lines) was read. The uploaded copy is identical to upstream
`main`. Findings are listed in `CHANGELOG.md`. The two most serious are the XY-before-Z positioning in
`onSection()` (confirmed as the mechanism behind upstream issue #5 and the user's `1001.cnc.gcode`) and the
`G60`/`G0 R0` tool-change return that restores into WCS 9 instead of the job WCS.

### Firmware behaviour confirmed in the RRF 2.05.1 source

| Claim used by the post | Where confirmed |
| --- | --- |
| `G0` is a rapid at `M203` limits in CNC mode, uses `F` in FFF mode | `GCodes.cpp` `LoadExtrusionAndFeedrateFromGCode()` |
| `M3 S`/`M4 S` act on spindle slot 0 (or `P`) regardless of the selected tool | `GCodes2.cpp` case 3 / case 4 |
| `M5` without `P` turns off every spindle | `GCodes2.cpp` case 5 |
| `G28` with axis letters homes those axes, `G28` alone homes all | `GCodes.cpp` `DoHome()` |
| `G53` ignores workplace and tool offsets; cleared at end of line | `GCodes.cpp` `DoStraightMove()`, `GCodeBuffer.cpp` `SetFinished()` |
| Several commands per line split at space + `G`/`M` (outside quotes) | `GCodeBuffer.cpp` `DecodeCommand()` |
| `G54`-`G59.3` select workplaces 1-9 and cancel `G53` | `GCodes2.cpp` case 54-59 |
| `G60 S0` saves user coordinates; `G0 R0` restores them in the current WCS | `GCodes.cpp` `SavePosition()`, `DoStraightMove()` |
| `G10 L20 P<n>` computes the offset from the current user position; `M500` writes all workplaces | `GCodes3.cpp` `GetSetWorkplaceCoordinates()`, `WriteWorkplaceCoordinates()` |
| `G4 P` milliseconds, `G4 S` seconds | `GCodes.cpp` `DoDwell()` |
| `M0` from the file: `stop.g`, heaters off, drives idle, all axes flagged not homed | `GCodes2.cpp` case 0/1, `GCodes.cpp` `DisableDrives()` |
| `M2` not implemented | no `case 2` in the M switch |
| `T<n>` for an undefined tool deselects all tools, runs `tfree`/`tpre`/`tpost` if present | `GCodes.cpp` toolChange states, `RepRap.cpp` `SelectTool()` |
| `M291` modes 0-3, `T` timeout only for 0/1, `X/Y/Z` jog, `S0 T0` rejected, 160-char line limit (dictionary) | `GCodes2.cpp` case 291 |
| `M585 S1` probes toward the axis minimum, needs a selected tool | `GCodes3.cpp` `ProbeTool()` |
| `M300`, `M400`, `M450`, `M453`, `M563`, `M585` exist | `GCodes2.cpp` |

### Post execution on a mock kernel

Autodesk's post executor (`post.exe`) is Windows-only and Fusion itself is not available in this environment,
so a Node.js mock of the post kernel API was written (`tests/mock-kernel.js`). It implements the formatting,
variable/modal, section, tool, cycle expansion and motion callbacks the post uses, from the documented
behaviour of the kernel. **It is not the Autodesk kernel**; number formatting edge cases, cycle expansion
details and the kernel's position model are approximations.

`node tests/run-tests.js` runs 37 scenarios and 37/37 pass (mock calls `onTerminate()` after writing the primary file and records `FileSystem`/`executeNoWait` calls). Each scenario's output is in `tests/output/`
(not committed) and five headline outputs are in `examples/`.

| # | Scenario | What it checks |
| --- | --- | --- |
| 01 | 64-hole spot drill, defaults (mirrors `1001.cnc.gcode`: S5000, Z15.24 clearance, Z5.08 retract, Z-0.508, F203) | `G54` -> `G0 Z15.24` -> `G0 X20 Y20` order, 64 plunges at F203, `G4 P12500`, blocking start prompt before motion |
| 02 | Same job, machine-Z retract | `G53 G0 Z-2` -> `G0 X Y` -> `G0 Z15.24` |
| 03 | Chip-breaking drill with 0.5 s dwell, 3 holes | `G4 P500` x3, pecks to Z-6 |
| 04 / 05 | 2D contour with a 90 degree arc, R mode and IJ mode | `G3 ... R10` / `G3 ... I J` |
| 06 | Two pockets, same tool, RPM change | second `M3 S14000`, no tool change routine, 5 s minimum dwell |
| 07 / 08 | 3D adaptive-style zigzag with combined XYZ rapids, split on/off | Z-first up, XY-first down / combined kept |
| 09 | 4 operations, 3 tools, default (WCS) retract | tool change order `M5`, `G4 P10000`, `G53 G0 Z`, `G53 G0 X Y`, `M400`, `M291 S3`; after change XY at safe Z then Z clearance; `M3` before first cut; `M4` for CCW tool |
| 10 | Same, machine-Z retract, park at end | as 09 plus `G53` park after `M5` |
| 11 | Tool change with manual change off | `M5` + new `M3`, no routine |
| 12 | Tool change with Z-probe plate | `M585 Z60 E3 L0 F300 S1`, `G10 L20 P1 Z3`, `M500`, `G53` retract after probe |
| 13 | Tool change with corner probe and G28 | `G28` then corner probe |
| 14 / 15 | G54 operation then G55 operation, WCS / machine retract | `G55` after `G54`, Z clearance first in new WCS, no tool change |
| 16 | Setup WCS 0 with property G55 | only `G55` written |
| 17 | Setup WCS 0 mixed with G55 | post error |
| 18 | Setup WCS 9 | `G59.3` |
| 19 / 20 | Tn output Fusion / fixed | `T1`,`T2` / `T0` twice |
| 21 / 22 | Spindle dwell none / fixed 3 s | no `G4` at all / `G4 P3000` twice |
| 23 | Messages off, no start prompt, `M0`, park | no `M291 S0/S1/S3`, `M0` at end, `G53 G0 X0 Y300` |
| 24 | Manual NC: comment, Stop, 2 s dwell, spindle speed, pass-through | `M291 S2`, `G4 P2000`, `M3 S15000`, `M117 custom` |
| 25 | Tapping cycle | post error |
| 26 | Sequence numbers | `N` words, spaces kept |
| 27 / 28 | Backlash compensation steps / distance on the zigzag | `M92` emitted / runs |
| 29 | Corner probe at program start | probe before first positioning |
| 30 / 31 / 32 | Descriptive output file name (on by default): one tool, three tools, unchecked | redirected to `op_1_6.35_flat_end_mill_5000RPM.gcode` with the whole program and a one-line pointer in the dialog-named file / `op_1_..._op_2_..._op_3_...gcode` / no redirection |
| 33 / 34 / 35 | Descriptive file name prefix: program name / operation names / none | `1001_1_...` / `2d_contour1_2d_pocket1_2_...` / `1_...` |
| 36 / 37 | Descriptive file name method = Single file, macOS path / Windows path | full program in the main file, existing target removed, `copyFile(1001.gcode -> op_1_...gcode)` from `onTerminate()` after the kernel wrote the file, then `executeNoWait` of the cleanup script; exact `.sh` / `.cmd` script text |

Checks applied to every scenario's output: no `G28` (unless enabled), no `M0` (unless enabled), no
`M1`/`M2`/`M6`, no bare `S` line, no `G10 L2`, no `G60`/`R0`, no `G40`-`G43`, no `G8x`/`G98`/`G99`, no lone
`G53`, every `G4` is `G4 P<integer>`, every `M291` under 160 characters with a valid mode and a timeout for
`S0`, no `F` on rapids, no `undefined`/`NaN`; first motion is Z-only (and `G53 G0 Z` in machine mode); `G90`,
`G21` and the WCS select precede it; `M3`/`M4 S` precedes the first cutting move; `M5` at the end; every
synthetic cutting coordinate appears in order with the right feed on the first `G1`; every operation's
clearance height is commanded.

## What was not verified

- **Execution in Fusion 360 / Autodesk's kernel.** Version 2.0 was posted from Fusion by the user on a
  64-hole chip-breaking spot drill (`1001.gcode`) and produced the expected sequence (`G54`, `G0 Z15.24`,
  `G0 X59.704 Y20.868`, expanded pecks, clean end). The 2.1 file-name redirection was also confirmed in Fusion by the user
  (`1001_T0_3.175_flat_end_mill_18000RPM.gcode`). Otherwise the post was not run
  through `post.exe`. Risk:
  a kernel API difference (for example `getCurrentPosition()` at the first section, `currentSection.
  getForceToolChange`, `cycleType` during expansion) could raise a post error or change a modal output. The
  code paths use the same calls as Autodesk's generic posts and the upstream post, so the risk is low but
  not zero. First real post in Fusion: read the output before running it.
- **Baseline comparison with `1001.cnc.gcode`.** The file was not supplied, and the Fusion CAM operations
  behind it are not available. `examples/spot_drill_64_holes_defaults.gcode` is a **synthetic** 8x8 grid
  built to the same parameters quoted in the handoff (S5000, Z15.24, Z5.08, Z-0.508, F203); it is not a
  repost of the real job.
- **Single-file method in Fusion.** 2.5 (rename in `onClose()`) produced a 0-byte file in Fusion on macOS,
  proving the kernel writes the primary output after `onClose()`. 2.6 (rename in `onTerminate()`) produced
  the correct descriptive file but Fusion reported "NC code failed to post" because the dialog-named file
  was gone. 2.7 copies and removes the stub 3 s later via `executeNoWait`; not yet confirmed in Fusion. The
  redirect method is the verified one.
- **Probe routines on hardware.** `M585` with `E3 L0`, the corner probe geometry and the `G10 L20`/`M500`
  sequence are upstream logic with the same parameters; they were checked for firmware syntax only. If the
  probe does not trigger, `M585` drives to the `M208` Z minimum. Test with a hand on the stop.
- **Backlash compensation.** Kept as upstream, off by default; not evaluated for correctness.
- **Dialog rendering** on PanelDue vs Duet Web Control (PanelDue shows ~50 characters).
- **Inch programs**: logic runs, not tested against a real inch job.

## Remaining risks the post cannot remove

1. The post does not know the machine position, homing state, fixture heights or tool stickout at start.
   The first Z move is safe only under the prerequisites in `README.md`.
2. *Safe machine Z* and the tool change X/Y default to `0`. On a machine where machine `Z0` is the table,
   `G53 G0 Z0` with the machine-Z mode, manual tool change or park enabled would plunge. The post warns at
   post time while the value is `0`, prints it in the header and in the start prompt, but cannot refuse: `0`
   is a valid value on machines homed to `Zmax = 0`.
3. In the default WCS retract mode, Fusion's clearance height must clear clamps along the XY traverse, and
   at a WCS change the first move is `G0 Z<clearance>` in the new WCS.
4. After a manual tool change without probing, WCS Z is wrong by the stickout difference.
5. `Tn` output modes can run `tpre`/`tpost` macros that move the machine.

## Review checklist before the first air cut

- [ ] Header shows the expected *Retract strategy*, *Safe machine Z*, tool change X/Y, Tn mode, probe mode.
- [ ] First four motion lines: `G90`, `G21`, (prompt), `G54`, `G0 Z<clearance>` or `G53 G0 Z<safe>`, then `G0 X Y`.
- [ ] No `G28` anywhere unless you enabled homing on tool change.
- [ ] Every `G4 P` value is in milliseconds and matches what you expect (12500 = 12.5 s).
- [ ] `M3 S<rpm>` precedes the first `G1`; `M5` precedes every `G53` park; the file ends with `M5`, `M400`,
      optional `M291`, comments.
- [ ] For each tool change: `M5`, `G4`, `G53 G0 Z`, `G53 G0 X Y`, `M400`, `M291 ... S3`, then `M3`, WCS, `G0 X Y`, `G0 Z`.
- [ ] `G55`/other WCS appear only where your setups change, and never `G10 L2`.
- [ ] Jog the tool a few millimetres above the stock, start the job with the spindle off: the first move must go up.
