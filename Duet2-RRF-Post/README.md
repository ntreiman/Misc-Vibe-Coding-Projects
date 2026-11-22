# Duet2Ethernet_RRF2051.cps

Autodesk Fusion 360 milling post-processor for a 3-axis CNC router running a **Duet 2 Ethernet** with
**RepRapFirmware 2.05.1** in CNC mode (`M453`).

It is a fork of Bruce Royce's [UltimateRepRapPost](https://github.com/BruceRoyce/UltimateRepRapPost)
(`UltimateRRPost.cps` R1.5, 2021-03-17, Apache License 2.0). The upstream file and license are kept
unmodified in `upstream/`. The fork fixes the unsafe startup / tool-change motion order reported in
upstream issue #5, removes commands that mean something different on RepRapFirmware (`G28`, `M0`, `M2`,
`G4 P` in seconds, `G60`/`R0` restores), and makes the spindle dwell, tool call and operator messages
configurable. See `CHANGELOG.md` for every change and its reason, and `VALIDATION.md` for what was and
was not verified.

> A passing post-processing test is not a safety certification. Air-cut every new program with the
> spindle off and your hand on the emergency stop before cutting stock.

## Files

| File | Purpose |
| --- | --- |
| `Duet2Ethernet_RRF2051.cps` | The post-processor to install in Fusion 360 |
| `README.md` | This document |
| `CHANGELOG.md` | Differences from upstream and why |
| `VALIDATION.md` | Test report, limitations, review checklist |
| `examples/*.gcode` | Output produced by the test harness (not reposts of real Fusion jobs) |
| `tests/mock-kernel.js`, `tests/run-tests.js` | Node.js mock of the Fusion post kernel and the scenario suite (`node tests/run-tests.js`) |
| `upstream/` | Unmodified upstream `UltimateRRPost.cps` and its Apache 2.0 `LICENSE` |

## Installation

1. Copy `Duet2Ethernet_RRF2051.cps` into your personal post folder. In Fusion: Manufacture workspace,
   **Actions > Post Process**, set the *Post* source to *Personal posts* (the folder opens with the folder
   icon; on Windows it is `%APPDATA%\Autodesk\Fusion 360 CAM\Posts`).
2. Select the post `Duet 2 Ethernet / RRF 2.05.1 CNC (UltimateRepRapPost fork)`.
3. **Set the properties in section "1- Safe Z and Retracts" and "4- Tool Change" before the first use.**
   The post ships with placeholder values of `0` for *Safe machine Z* and the tool change X/Y because it
   cannot know your machine. A warning is printed at post time while *Safe machine Z* is `0`.
4. Output extension is `.gcode`. Upload the file to the Duet with Duet Web Control and run it as a job.

## What the controller must look like

The post was checked against the RepRapFirmware 2.05.1 source and the Duet G-code dictionary. It assumes:

- `M453` CNC mode in `config.g`. In CNC mode `G0` is a true rapid at the `M203` limits and `M3 S`/`M4 S`
  drive spindle slot 0 whether or not a tool is selected. In FFF mode `M3` reports "not supported".
- A spindle configured on slot 0 (`M453 ... P<pins>` / `R<max rpm>`).
- Workplace coordinates enabled (default in RRF 2.x). `G54` to `G59.3` select WCS 1 to 9.
- No `tfree`/`tpre`/`tpost` macros that move the axes, unless you choose a `Tn` output mode on purpose.
- If you use the probe routines: a touch probe on the **E0 endstop input** (`M585 ... E3 L0`, active low).

The post never writes to `config.g`, never changes `M208` limits and never calls homing unless you enable
*Home all axes (G28) after tool change*.

## Prerequisites before pressing start (every job)

The post has no way to know where the machine is when the job starts. The first motion it writes is a
pure Z move, but that move is only safe if these hold:

1. All axes are **homed** (RRF refuses `G0`/`G1` on unhomed axes, but a stale home is worse than none).
2. The **WCS used by the Fusion setup is zeroed** on this stock (`G10 L20 P<n> X0 Y0 Z0` at the origin,
   or via the Duet Web Control CNC panel). The post never sets or saves a WCS origin by itself unless a
   probe routine is enabled.
3. The **first tool is mounted** and the WCS Z zero is valid for its stickout.
4. *Safe machine Z* and the tool change X/Y (both **machine coordinates**, as shown by `M114` machine
   position or when `G53` is in effect) clear the stock, clamps and fixtures with the longest tool.
5. In *Fusion clearance* retract mode, the Fusion **clearance height** of every operation must clear every
   clamp along the XY path from where the tool is to the start point. In Fusion this is the *Heights >
   Clearance Height* of the operation. Raise it if clamps stand above the stock.

The header of every generated file repeats the property values that were used, so you can check them on
the Duet before starting.

## Motion sequence the post produces

### Program start

```
G90
G21
M300                                  ; beep (optional)
M291 P"Homed, WCS zeroed, T1 D6.35 mounted? ..." R"Start job" S3   ; blocking OK/Cancel, Cancel aborts
M3 S5000
G4 P12500                             ; spindle dwell (configurable, see below)
G54                                   ; WCS from the Fusion setup
G0 Z15.24                             ; <-- Z clearance FIRST  (or: G53 G0 Z<safe> in machine mode)
G0 X20 Y20                            ; then XY
G0 Z5.08                              ; operation retract height and the toolpath follow
```

Upstream wrote `G0 X20 Y20` first and `G0 Z15.24` second. That is the crash reported in upstream issue #5
and is the main reason for this fork.

### Retract strategies (property *Retract strategy*)

| Mode | Program start, tool change, WCS change | Between operations with the same tool and WCS |
| --- | --- | --- |
| **Fusion clearance height in active WCS** (default) | `G0 Z<clearance of the operation>` in the active WCS, then `G0 X Y` | `G0 Z<clearance>` only if the tool is below it, then `G0 X Y` |
| **Safe machine Z with G53** | `G53 G0 Z<safe machine Z>`, then `G0 X Y`, then `G0 Z<clearance>` | same as above (Fusion clearance height) |

The default mode invents no numbers: it uses the heights you set in Fusion. Its weakness is that after a
manual tool change (where the machine sits at *Safe machine Z*) the first move after the prompt is an XY
traverse at that height followed by a descent to the Fusion clearance height; and at a WCS change, the
first move is `G0 Z<clearance>` in the **new** WCS, which can be a descent if the second setup's Z zero is
lower. If your setups have different heights or clamps, use the **machine Z** mode and set *Safe machine Z*.

`G53` in RepRapFirmware applies to the current line only and ignores both workplace and tool offsets
(verified in the 2.05.1 source). The post always writes it as `G53 G0 ...` on one line. This is why words
are always space separated: RRF 2.05.1 splits two commands on one line only at a space followed by `G` or
`M`.

### Tool change (property *Manual tool change*, default on)

```
M5
G4 P10000                 ; spindle stop dwell (property, 0 disables)
G53 G0 Z<safe machine Z>  ; Z first, machine coordinates
G53 G0 X<tc X> Y<tc Y>    ; park, machine coordinates
M400
;TOOL T2 ...              ; or "T2" / "T<fixed>" depending on "Tn output"
M300
M291 P"Change to T2 D6 flat end mill. OK when the tool is secured ..." R"Tool change" S3
                          ; blocking. OK continues, Cancel aborts the job
[G28]                     ; only if "Home all axes after tool change" is on. G28 HOMES in RRF.
[Z-probe or corner probe] ; only if "Probe after each tool change" is set. Rewrites the WCS origin.
[G53 G0 Z<safe>]          ; written again if homing or probing moved the machine
M3 S12000 + dwell
G54
G0 X.. Y..                ; XY traverse at safe machine Z
G0 Z<clearance>           ; then down to the Fusion clearance height
```

Upstream parked by switching to WCS 9 (`G59.3`) and moving to its origin, after rewriting WCS 9 with
`G10 L2 P9` at every program start, and returned with `G0 R0 ...`. In RRF 2.05.1 `G60` saves and `R0`
restores **user coordinates in the WCS active at restore time**, which was still WCS 9, so the return
position was shifted by the difference between WCS 9 and the job WCS unless the two happened to coincide.
The fork uses `G53` machine coordinates for the park position and lets the next operation position itself.

With *Manual tool change* off, the post writes `M5`, the tool call (if any), `M3 S` for the new speed and
continues. Use this only if your tool changes are handled outside the program.

### Tool length

RepRapFirmware has no `G43` tool length compensation and the post writes none. After a manual tool change
the WCS Z zero is only valid if one of these happens:

- *Probe after each tool change = Z-Probe plate*: the post parks, moves in XY (at the safe machine Z) to
  `X<inside> Y<inside>` of the active WCS, prompts you to place the plate (you can jog Z with the dialog's
  jog buttons), probes with `M585 Z60 E3 L0 F300 S1` (toward Z minimum until the E0 input goes low), sets
  the active WCS with `G10 L20 P<n> Z<plate thickness>`, saves it with `M500`, lifts, and prompts you to
  remove the plate. If the probe does not trigger, `M585` drives to the `M208` Z minimum.
- You re-zero Z yourself after the prompt (the job is paused at the `M291 S3`; Duet Web Control can jog and
  set Z while the dialog is open, then press OK).
- You use tools with identical stickout (collet stops) and accept the error.

The first tool is never probed unless *Corner probe at program start* is on.

### Program end

```
G0 Z<clearance>   (or G53 G0 Z<safe>)
M5
G4 P10000
[G53 G0 X<tc X> Y<tc Y>]  ; only with End of program position = park
M400
M291 P"Program finished. Spindle off" R"Program end" S1 T10
[M0]              ; only with "End program with M0" (runs stop.g, idles drives, flags axes NOT homed)
; tool motion box comments
```

The file then simply ends, which RRF treats as a normal job completion with the motors still holding.
Upstream ended with `M3 S0`, `M2` (not implemented in 2.05.1), `M5`, `M0`.

## Coordinate systems

- The post honours the **Fusion setup WCS offset**: 1 = `G54`, 2 = `G55`, ... 6 = `G59`, 7 = `G59.1`,
  8 = `G59.2`, 9 = `G59.3`. A setup WCS offset of `0` means "unspecified" and falls back to the post property
  *WCS when the Fusion setup WCS offset is 0* (default `G54`). Mixing `0` with non-zero offsets in one program
  is an error, as upstream.
- The post writes the WCS select before the first move of the program, again after every tool change, and
  whenever the setup offset changes. It never writes `G10 L2` and never redefines an origin unless a probe
  routine is enabled.
- WCS 9 (`G59.3`) is an ordinary WCS in this fork. Upstream reserved it for the tool change position.
- `G53` is used only for *Safe machine Z* and tool change / park positions. `G54` is **not** machine
  coordinates; it has whatever offset you gave it with `G10 L2 P1` / `G10 L20 P1`.

## Spindle

- `M3 S<rpm>` or `M4 S<rpm>` (counter-clockwise tools) is written at program start, after every tool change
  and whenever the RPM or direction changes between operations. `M5` is written before parking for a tool
  change and at program end.
- *Spindle start / speed change dwell*: **Proportional** (upstream behaviour: *catch-up time per 6000 RPM*
  scaled by the RPM change, doubled on a direction change, minimum 5 s), **Fixed** (always *Fixed spindle
  dwell*), or **None**. The user's original file had `G4 P12500` for 5000 RPM at 15 s / 6000 RPM; the default
  reproduces that.
- *Spindle stop dwell*: seconds after `M5` before the park move and at program end (default 10 s, upstream
  waited 10 s at program end). Set to 0 to disable.
- Dwells are always written as `G4 P<milliseconds>` (integer). RRF `G4 P` is milliseconds and `G4 S` is
  seconds; upstream wrote Fusion cycle dwells in seconds under `P`, so a 2 s dwell became 2 ms.

## Operator messages (`M291`)

Always written (safety prompts, blocking):

- Start confirmation (`S3`, OK/Cancel) before any motion. Can be disabled with *Start confirmation prompt*.
- Tool change prompt (`S3`).
- Probe mount / remove prompts (`S3` / `S2`) when a probe routine is enabled.
- Fusion *Manual NC > Stop* and *Optional stop* become `M400` + `M291 ... S2` (OK to continue), because `M0`
  ends the job and `M1` is sleep in RRF.

Optional (`S0`/`S1`, non-blocking, property *Informational messages*): current operation name, spindle
dwell notice, program end. `M300` beeps before prompts can be disabled with *Beep*.

All `M291` lines are kept under RRF 2.x's 160-character limit and quotes are stripped from the text.

## Canned cycles

RepRapFirmware has no `G81`-style cycles. Every Fusion drilling cycle (drilling, chip breaking, deep
drilling, counter boring, reaming, boring, circular pocket milling and the others) is expanded by Fusion into
`G0`/`G1`/`G4` moves, which is what the original post did implicitly. Tapping cycles are rejected with an
error: there is no rigid tapping on this firmware and expansion would rely on spindle reversal timing.

## Other behaviour worth knowing

- **Split combined XY+Z rapids** (default on): a rapid that moves XY and Z together is written as two moves,
  Z first when going up and XY first when going down. Fusion normally produces pure Z and pure XY rapids
  anyway; this guards the exceptions. Cutting moves are never altered.
- **Tn output** (default *None*): `T<n>` is not required for the spindle on RRF 2.05.1. In RRF, `T2` for a
  tool that is not defined with `M563` silently deselects all tools and runs `tfree`/`tpre`/`tpost` macros if
  they exist. Choose *Fusion tool number* or *Fixed tool number* only if your `config.g` defines tools and you
  want them selected.
- **Controller radius compensation** (`G41`/`G42`) is not available on RRF and now raises an error. Use *In
  computer* compensation in the Fusion operation (the default).
- **No coolant / dust collector output.** Upstream had the `M7`/`M8`/`M9` output commented out; the property
  was removed.
- **Arcs**: `G2`/`G3` with `R` (default) or `I`/`J`, XY plane only; other planes and full circles in R mode are
  linearised. Helical moves are allowed.
- **Linear backlash compensation**: upstream's feature is kept unchanged in its two methods but is **off by
  default**. The upstream "flush accumulated compensation" routines were removed (see CHANGELOG).
- **Motion box**: the comment block at the end of the file lists the commanded min/max per axis in the
  active WCS (arc end points only, not arc extents).
- **Inches**: `G20` is written and all coordinates follow Fusion. Enter *Safe machine Z* and the tool change
  position in inches too in that case.

## Descriptive output file name

With the property **Descriptive output file name** checked, the program is written to

```
[prefix_]T<tool number>_<diameter>_<tool type>_<rpm>RPM.gcode
```

in the output folder, with one `T..._..._..._...RPM` block per tool in order of first use. Examples:

- `T1_6_spot_drill_5000RPM.gcode` (one tool, no prefix, the default)
- `T1_6.35_flat_end_mill_5000RPM_T2_6_flat_end_mill_12000RPM.gcode` (two tools)
- `spotdrill_T1_6_spot_drill_5000RPM.gcode` (prefix = operation name)
- `1001_T1_6_spot_drill_5000RPM.gcode` (prefix = program name/number)

*Descriptive file name prefix* chooses the prefix: **None** (default), **Operation name(s)** (the Fusion
operation names in order, de-duplicated) or **Program name/number** (the post dialog field). Names are
lower-cased, with anything other than letters, digits, `.` and `-` turned into `_`. Diameter is in program units (mm or inch) with trailing
zeros removed. Tool type comes from the Fusion tool library (`flat end mill`, `ball end mill`, `spot drill`,
`drill`, `chamfer mill`, ...). RPM is the spindle speed of the first operation that uses the tool.

The Fusion post kernel cannot rename its own output file, so the file named in the post dialog is still
created; it contains one comment line pointing to the real file. Upload the descriptive one to the Duet. If
the descriptive file already exists it is overwritten.

## Properties reference

### 1- Safe Z and Retracts

| Property | Default | Meaning |
| --- | --- | --- |
| Retract strategy | Fusion clearance height in active WCS | See *Retract strategies* above |
| Safe machine Z (G53) | 0 | Machine Z that clears everything. **Set it.** Used by machine mode, manual tool change, park |
| Split combined XY+Z rapids | on | Z-first up / XY-first down |
| End of program position | Retract only | Or park at tool change XY with `G53` |

### 2- Workspace

| Property | Default | Meaning |
| --- | --- | --- |
| WCS when the Fusion setup WCS offset is 0 | G54 | Fallback only |
| Start confirmation prompt | on | Blocking `M291 S3` before motion |

### 3- Spindle

| Property | Default | Meaning |
| --- | --- | --- |
| Spindle start / speed change dwell | Proportional | Proportional / Fixed / None |
| Spindle catch-up time for 6000 RPM (s) | 15 | Proportional mode |
| Fixed spindle dwell (s) | 5 | Fixed mode |
| Spindle stop dwell (s) | 10 | After `M5` before park / at end |

### 4- Tool Change

| Property | Default | Meaning |
| --- | --- | --- |
| Tn output | None | None / Fusion tool number / Fixed tool number |
| Fixed tool number | 0 | With *Fixed* |
| Manual tool change | on | Park with `G53`, blocking prompt |
| Tool change X / Y (G53) | 0 / 0 | Machine coordinates of the park position. **Set them.** |
| Home all axes (G28) after tool change | off | `G28` homes the machine on RRF |

### 5- Probes (after tool change)

| Property | Default | Meaning |
| --- | --- | --- |
| Probe after each tool change | No probe | Z plate / corner probe (both rewrite the WCS origin and `M500`) |
| Z-Probe thickness, Retract after Z-probe, Z-Probe XY position inside origin | 3 / 5 / 5 | Z plate routine |
| Corner probe at program start, placement, length, width, thickness, retract | off / Bottom-Left / 50 / 50 / 5 / 10 | Corner probe routine (upstream logic, unverified on hardware) |

### 6- Operator Messages

| Property | Default | Meaning |
| --- | --- | --- |
| Informational messages | on | Non-blocking `M291 S0/S1` |
| Beep (M300) before prompts | on | |

### 7- Formatting

| Property | Default | Meaning |
| --- | --- | --- |
| Use sequence numbers, start, increment | off / 10 / 5 | `N` words |
| Radius arcs | on | `R` instead of `I`/`J` |
| Write machine / tool list / version | on | Header comments |
| End program with M0 | off | `M0` runs `stop.g`, idles drives, un-homes axes |
| Descriptive output file name | off | Write to `[prefix_]T<n>_<diameter>_<tool type>_<rpm>RPM.gcode`, see below |
| Descriptive file name prefix | None | None / operation name(s) / program name |

### 8- Linear Backlash Compensation

Unchanged upstream feature, off by default. See upstream README in the original repository for the
measurement procedure. Keep it off unless you have measured values and understand that the *Steps* method
rewrites `M92` during the job.

## Testing on the machine

1. Post a one-operation job, open the file, and read the header and the first ten motion lines.
2. With the spindle disconnected or the tool removed, run the job once from the normal start position and
   once from a deliberately low Z (jog the tool to a few millimetres above the stock before starting). The
   first move must be upward in both cases.
3. For multi-tool jobs, watch the first tool change: the machine must stop the spindle, wait, lift, park,
   and show the prompt before you touch anything. Press Cancel once to confirm that the job aborts.
4. Only then cut stock.
