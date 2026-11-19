# Example output

These files were produced by `tests/run-tests.js` on the mock kernel in `tests/mock-kernel.js`, **not** by
Fusion 360. They show the sequencing the post produces; coordinates are synthetic.

- `spot_drill_64_holes_defaults.gcode`: 8 x 8 spot-drill grid with the parameters quoted from the user's
  `1001.cnc.gcode` (S5000, clearance Z15.24, retract Z5.08, depth Z-0.508, F203), default properties. This is a
  stand-in for the original job, which was not available to repost. Compare its first motion lines with the
  original:

  | Original (upstream post) | This post |
  | --- | --- |
  | `M5` / `T1` / `M3 S5000` / `G4 P12500` / `G54` / **`G0 X59.704 Y20.868`** / `G0 Z15.24` / `G0 Z5.08` / `G1 Z-0.508 F203` | `M291 ... S3` / `M3 S5000` / `G4 P12500` / `G54` / **`G0 Z15.24`** / `G0 X20 Y20` / `G0 Z5.08` / `G1 Z-0.508 F203` |

- `spot_drill_64_holes_machineZ_retract.gcode`: same job with *Retract strategy = Safe machine Z (G53)* and
  `Safe machine Z = -2` (an arbitrary test value, not a recommendation).
- `multi_tool_manual_toolchange_wcs_retract.gcode`: spot drill (T1), contour and pocket (T2), engrave (T3,
  counter-clockwise), default retract mode, manual tool changes with `Safe machine Z = -1`, park at X10 Y10.
- `multi_tool_manual_toolchange_machineZ_retract.gcode`: same with machine-Z retract and park at end.
- `g54_then_g55_wcs_change.gcode`: one tool, contour in G54 then facing in G55.
