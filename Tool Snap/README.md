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

**Snap to Tools** is the panel's icon; the other commands are in its drop-down.

| Command | What it does |
|---|---|
| **Snap to Tools** | Dialog with fit (fine / medium / coarse), snap tolerance, and one row per tool-driven parameter: target, floor, **Mode** dropdown (Up / Nearest / Down / Off / Keep), snapped Ø, tool, Δ. OK writes the values into the design's user parameters. |
| **Add Shop Tool** | Type (drill / endmill), diameter (`10`, `0.4375`, or `7/16`), unit, optional name → appended to `data/shop_tools.json`. |
| **Shop Tools** | The inventory as a filterable, sortable table. **Filter:** type · system (imperial / metric) · series as a multi-select (Number, Letter, Fractional, Metric, …) · available / retired · Ø min / max · *near Ø* (the 4 closest tools each side of a size) · search · "only tools a hole snaps to". **Display:** units (mm, inches, or both), sort (Ø up / down, name, series-grouped with header rows), human labels (`#29`, `1/16"`, `E`, `5 mm`), a **Step ↑** column with the gap to the next larger available tool of the same type (big steps = holes in the library), a **Used for** column listing the hole parameters that currently pick each tool, and a shown/total count. **Edit:** tick / untick *Available* per tool or mark all shown tools available / retired in one go; Save persists. *Export CSVs on Save* writes `Drill Library.csv` and `Endmill Library.csv` — one per Google Sheet tab, same columns — into a folder you pick. |
| **Add Size** | Pick a size (M1.6 … M20) and the features to set up — clearance hole, tap drill, socket-head counterbore, button-head counterbore, countersink — and the parameters are created from the standards table (`core/standards.py`: ISO 273 + ISO 286 limits, ISO 262 pitch, ISO 965-1 6H band, ISO 4762 / ISO 7380 / DIN 7991 heads). Snap to Tools then shows the size automatically; features without standard head data for a size (e.g. M7 counterbores) are greyed out. Or pick **Endmill class** to add `emN_*` parameters (below). |
| **Import Parameters** | Creates the full fastener parameter set (nominal Ø, ISO 273 clearance series, tap drills, head geometry, counterbore/countersink expressions) in a fresh design from `data/fastener_parameters.csv`, then optionally snaps. |

Only the "tool-driven" parameters (`mX_clearance_hole`, `mX_pilot_drill`,
`mX_counterbore_ID_round/socket`, `emN_dia`) are written. Counterbore depths,
countersink chamfer legs and `mX_countersink_OD` (the countersink's edge
diameter at the surface — sketch that circle; it equals the theoretical head
diameter + 2 × depth clearance and is the same for clearance and tapped
holes) keep their Fusion expressions and recompute by themselves.

Sizes are discovered from the design: every `mX_nominal_dia` present is a
size, and a family whose inputs are absent for a size (say M8 has clearance and
tap-drill parameters but no head data) is simply listed as "not set up" rather
than being an error. `fastener_parameters.csv` (M2–M6, all families) is
generated from the same standards table Add Fastener Size uses, and a test
keeps the two identical.

## Snap semantics (identical to the spreadsheet)

* **Up** — smallest available tool ≥ max(target − tol, floor)
* **Down** — largest available tool ≤ target + tol that is still ≥ floor; falls back to Up
* **Nearest** — closer of Up / Down to the target; ties go Up
* **Off** — write the target unsnapped (helical-bored counterbores on a CNC)
* **Keep** — don't touch the parameter; a value you set by hand in Change
  Parameters survives re-snapping

## Endmill classes (pocket corner radii)

`emN` is to a pocket what `mN` is to a hole: "the endmill I own that is nearest
N mm". Default classes em3, em6, em10, em12; add others with Add Size.

| Parameter | Role |
|---|---|
| `em6_nominal_dia` = 6 mm | the class wanted (input) |
| `em6_dia` | **tool-driven**: nearest available endmill (6 mm, or 1/4" = 6.35 if you don't own one) |
| `em6_radius` = `em6_dia / 2` | expression |
| `em6_corner_radius` = `em6_radius * corner_radius_factor` | expression — use it on internal pocket fillets |
| `corner_radius_factor` = 1.1 | global; 1.0 = exactly the cutter radius, 1.1 leaves 10 % relief so the tool is never fully engaged in a corner |

Buy a 10 mm endmill, add it in Shop Tools, re-run Snap: `em10_dia` moves from
3/8" (9.525) to 10 and every pocket fillet using `em10_corner_radius` follows.

## Editing parameters in Fusion

ToolSnap never deletes or recreates a parameter — it sets the expression on
the existing one, exactly like typing in Change Parameters — so sketches and
features referencing `m4_clearance_hole` etc. keep their links and recompute.
Edit the inputs (head ODs, clearances, ISO rows) freely; the next Snap reads
the live values. Hand-edit one of the 20 tool-driven outputs and either set its
row to **Keep** or expect the next Snap to overwrite it. Neither command ever
changes the Favorite flag or comment of a parameter that already exists —
those are only set when ToolSnap creates one. If you rename one of
those tool-driven parameters, add the old name as `legacy` in
`snap_rules.json` (as done for `mX_counterbore_OD_*` → `mX_counterbore_ID_*`):
a design that still has the old name is written in place, and one that has
both gets the unused old one removed.

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
  unused. Seeded from the Drill Library / Endmill Library tabs; **Shop Tools →
  Export** writes it back out in exactly that two-tab layout.
* `snap_rules.json` — which parameters are tool-driven and how. `{m}` expands
  over the sizes found in the design (the file's `sizes` list is only the CLI
  default), `{fit}` is the active clearance series; `target`, `floor` and
  `ceiling` are ordinary Fusion expressions over user parameters.
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
  core/      pure Python: snap.py (modes/floor/ceiling), rules.py, inventory.py,
             standards.py (fastener data -> parameters), library_view.py
             (Shop Tools filtering/sorting), paramcsv.py, expr.py
  fusion/    Fusion API only: commands, user-parameter I/O, CAM library reader
  resources/ toolbar icon (16/32/64 px + @2x)
  data/      inventory, rules, parameter CSV
tests/       pytest; no Fusion needed
snap_report.py
```
