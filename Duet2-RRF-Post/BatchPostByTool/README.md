# Batch Post by Tool (Fusion 360 add-in)

One button in the Manufacture workspace. It takes the operations of the setup **in the order shown in the
browser**, splits them into consecutive runs that share a tool, and posts each run to its own file with the
`Duet2Ethernet_RRF2051` post and its descriptive single-file naming:

```
op_<tool number>_<diameter>_<tool type>_<rpm>RPM.gcode
```

Example setup: `Face (T0)`, `Adaptive (T0)`, `Contour (T0)`, `Drill (T1)`, `Chamfer (T2)` gives three files:
`op_0_6_flat_end_mill_12000RPM.gcode` (Face + Adaptive + Contour in that order), `op_1_...`, `op_2_...`.

- One milling setup in the document: the command runs immediately, no dialog.
- Several setups: a small dialog asks which one.
- A tool used again later (`T0, T1, T0`) gets two files, `op_0_..._run1.gcode` and `op_0_..._run2.gcode`, so
  nothing is overwritten.
- Suppressed operations are skipped. Operations without a valid toolpath are generated first.
- A summary dialog lists the runs and the files written.

## Install

1. Copy the `BatchPostByTool` folder (this folder, the one containing `BatchPostByTool.py`) to
   Fusion's add-ins directory:
   - macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
   - Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
2. Fusion: Utilities > Add-Ins > Scripts and Add-Ins > *Add-Ins* tab > select **BatchPostByTool** > Run
   (tick *Run on Startup*).
3. A **DUET POST** panel appears on the Milling tab of the Manufacture workspace.

The post itself must be installed as usual (`Duet2Ethernet_RRF2051.cps` 2.8 or later in Fusion's personal
posts folder). The add-in reads it from there by default.

## Settings (Batch Post Settings button)

| Setting | Default | Meaning |
| --- | --- | --- |
| Output folder | `~/Downloads` | Where the `.gcode` files go |
| Post file | `<personal posts folder>/Duet2Ethernet_RRF2051.cps` | The `.cps` to post with |
| Open folder when done | off | Opens the output folder in Finder / Explorer after posting |

Stored in `settings.json` next to the add-in.

## What the add-in forces in the post

For every run it passes these post properties through the API, regardless of what the Post Process dialog
remembers: *Descriptive output file name* on, method *Single file*, prefix *op*, and *run number* when the
tool repeats. All other properties (safe Z, tool change position, spindle dwell, ...) come from the post's
defaults as saved in the `.cps` file, **not** from values you set in the Post Process dialog. Edit the
`properties` block at the top of the `.cps` if you want different defaults for batch posting.

Fusion writes each run first under a temporary name (`run01_T0.gcode`, ...); the post copies it to the
descriptive name and a background script removes the temporary file a few seconds later. If a temporary file
is still there after ten seconds, the post's single-file method did not run; check the summary dialog.

## Not verified here

The add-in was written against the documented Fusion API (`CAM.postProcess`, `PostProcessInput`,
`postProperties`, `Setup.allOperations`, `Tool.parameters["tool_number"]`) and the grouping logic is unit
tested (`python3 -m unittest discover BatchPostByTool/tests`), but it has not been run inside Fusion from
this environment. First use: a one-setup document with two tools, check that two files appear and that the
operations in each file are the ones you expect.
