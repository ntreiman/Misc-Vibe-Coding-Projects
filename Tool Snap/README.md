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
| **Snap to Tools** | Dialog with fit (fine / medium / coarse), snap tolerance, and one row per tool-driven parameter: target, floor, **Mode** dropdown (Up / Nearest / Down / Off), snapped Ø, tool, Δ. OK writes the values into the design's user parameters. |
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

Holes snap to **drills**; counterbores snap to **flat endmills** (plunged on a
manual mill). Counterbore **floor** = head OD + ISO 273 coarse radial clearance
for that fastener, so a "Nearest" pick can go smaller than the 1 mm target
clearance but never below the coarse one.

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

## Install

1. Fusion 360 → Utilities → Add-Ins → **Scripts and Add-Ins** → *Add-Ins* tab → **+**
2. Pick the `ToolSnap` folder (the one containing `ToolSnap.py`).
3. Run (and tick *Run on Startup*). A **TOOL SNAP** panel appears on the Solid tab.

## Checking without Fusion

```bash
python -m pytest tests          # snap logic + the 20 spreadsheet rows as oracle
python snap_report.py           # prints the Tool Snap table from the bundled data
python snap_report.py --fit fine --tol 0.05 --params my_fusion_export.csv
```

`snap_report.py` takes any Fusion parameter CSV export, so you can preview what
a changed inventory does to a design before opening it.

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
