# ToolSnap — Fusion 360 add-in

Makes hole and counterbore parameters match the drills and endmills you actually
own. It is the **Tool Snap** tab of the *Tools and Fastener Parameters*
spreadsheet, moved inside Fusion so that "I just bought a 10 mm endmill" is one
dialog, not a spreadsheet round-trip.

```
target diameter  ──►  snap to available tool  ──►  user parameter
(ISO 273 fit, tap      (drill for holes,            (hard value in mm;
 drill, head OD +       endmill for counterbores,    depths & chamfers stay
 clearance)             floor-aware)                 expression-driven)
```

## Commands (Design → Solid tab → TOOL SNAP panel)

| Command | What it does |
|---|---|
| **Snap to Tools** | Dialog with fit (fine / medium / coarse), snap tolerance, and one row per tool-driven parameter: target, floor, **Mode** dropdown (Up / Nearest / Down / Off / Keep), snapped Ø, tool, Δ. OK writes the values into the design's user parameters. |
| **Add Shop Tool** | Type (drill / endmill), diameter (`10`, `0.4375`, or `7/16`), unit, optional name → appended to `data/shop_tools.json`. |
| **Import Parameters** | Creates the full fastener parameter set (nominal Ø, ISO 273 clearance series, tap drills, head geometry, counterbore/countersink expressions) in a fresh design from `data/fastener_parameters.csv`, then optionally snaps. |

Only the 20 "tool-driven" parameters (`mX_clearance_hole`, `mX_pilot_drill`,
`mX_counterbore_OD_round/socket`) are written. Counterbore depths and
countersink chamfer legs keep their Fusion expressions and recompute by
themselves.

## Snap semantics (identical to the spreadsheet)

* **Up** — smallest available tool ≥ max(target − tol, floor)
* **Down** — largest available tool ≤ target + tol that is still ≥ floor; falls back to Up
* **Nearest** — closer of Up / Down to the target; ties go Up
* **Off** — write the target unsnapped (helical-bored counterbores on a CNC)
* **Keep** — don't touch the parameter; a value you set by hand in Change
  Parameters survives re-snapping

## Editing parameters in Fusion

ToolSnap never deletes or recreates a parameter — it sets the expression on
the existing one, exactly like typing in Change Parameters — so sketches and
features referencing `m4_clearance_hole` etc. keep their links and recompute.
Edit the inputs (head ODs, clearances, ISO rows) freely; the next Snap reads
the live values. Hand-edit one of the 20 tool-driven outputs and either set its
row to **Keep** or expect the next Snap to overwrite it. Neither command ever
changes the Favorite flag or comment of a parameter that already exists —
those are only set when ToolSnap creates one. If you rename one of
those 20, rename it in `snap_rules.json` too, or Snap will create the old name
afresh.

Holes snap to **drills**; counterbores snap to **flat endmills** (plunged on a
manual mill). Every row has a **floor** (hard minimum) and most have an ISO
**maximum** that is flagged, not enforced (a slightly oversize hole beats no
hole):

| Row | Floor | ISO maximum (flagged) |
|---|---|---|
| Clearance hole | the ISO 273 series value itself (H tolerance: zero lower deviation) | value + IT grade — fine H12, medium H13, coarse H14, IT per ISO 286 for the hole's size range |
| Tap drill | 6H minor diameter minimum = basic D1 = D − 1.0825 P (ISO 965-1) | 6H minor diameter maximum = D1 + TD1 grade 6 |
| Counterbore | head OD + ISO 273 coarse radial clearance for that fastener | — |

All limits live as parameters (`mX_clearance_hole_fine_max`, `mX_tap_drill_min/max`,
…) with their derivation in the comment, so they are visible and editable in
Change Parameters. Default mode is **Nearest** for drills (the floor stops it
going under) and for counterbores.

**Notes column.** Tap-drill rows show the resulting percent of thread using the
Machinery's Handbook convention `% = (D − drill) / (1.299 × pitch)` — the one
tap-drill charts mean by "75 % thread". With the bundled inventory M4's tap drill lands on #30 (3.264 mm, 81 %); #29
(3.454 mm, 60 %) is above the 6H minor-diameter maximum and would be flagged
`OVER ISO max`. Counterbore rows show the actual radial gap between head and
wall.

## Data files (`ToolSnap/data/`)

* `shop_tools.json` — the inventory. `available: false` keeps a tool listed but
  unused. Seeded from the Drill Library / Endmill Library tabs.
* `snap_rules.json` — which parameters are tool-driven and how. `{m}` expands
  over `sizes`, `{fit}` is the active clearance series; `target` and `floor`
  are ordinary Fusion expressions over user parameters. Add M8 by appending
  `"m8"` to `sizes` and the M8 inputs to the CSV — no Python changes.
* `fastener_parameters.csv` — the ExportedParameters tab in Fusion's own
  parameter CSV format (also importable via Parameters → Import in Fusion).
* `snap_settings.json` — last-used fit / tolerance / per-row modes (auto-written).

Optionally the Snap dialog can also read Fusion's **local CAM tool libraries**
(tool source dropdown): drills and flat end mills found there count as owned.

## Related work

Nothing I could find does this already. The nearest things:

* Autodesk's **ParameterIO** sample and tapnair's **ParamEdit** / **FusionCSVer**
  move user parameters in and out of CSV, but know nothing about tools.
* Fusion's own threaded Hole feature models the thread's *minor* diameter, not a
  real tap-drill size, and offers no override — a long-standing forum complaint.
* The CAM tool library is the other half: ToolSnap can read it (tool source
  dropdown) but keeps its own `shop_tools.json` as the source of truth, because
  "I own it" and "it's in a CAM library" aren't the same thing.

## Install

1. Fusion 360 → Utilities → Add-Ins → **Scripts and Add-Ins** → *Add-Ins* tab → **+**
2. Pick the `ToolSnap` folder (the one containing `ToolSnap.py`).
3. Run (and tick *Run on Startup*). A **TOOL SNAP** panel appears on the Solid tab.

Alternatively, copy or symlink the `ToolSnap` folder into Fusion's add-ins
directory and it shows up in that dialog by itself:

* macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
* Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`

## Checking without Fusion

```bash
python -m pytest tests          # snap logic + the 20 spreadsheet rows as oracle
python snap_report.py           # prints the Tool Snap table from the bundled data
python snap_report.py --fit fine --tol 0.05 --params my_fusion_export.csv
```

`snap_report.py` takes any Fusion parameter CSV export, so you can preview what
a changed inventory does to a design before opening it.

**Verified / not verified.** The snapping logic, rules, inventory, CSV handling
and the 20 spreadsheet rows are covered by tests. The Fusion-side code follows
the official API reference (command inputs, user parameters, CAM tool
libraries) but has not been exercised inside Fusion yet; if a dialog errors,
the message box carries a traceback. The CAM-library tool source is best-effort
(tool diameters are assumed to come back in cm, as the API's own sample
implies).

## Layout

```
ToolSnap/
  ToolSnap.py, ToolSnap.manifest   add-in entry point
  core/      pure Python: snap.py (modes/floor), rules.py, inventory.py,
             paramcsv.py, expr.py (safe expression evaluator for tests/CLI)
  fusion/    Fusion API only: commands, user-parameter I/O, CAM library reader
  data/      inventory, rules, parameter CSV
tests/       pytest; no Fusion needed
snap_report.py
```
