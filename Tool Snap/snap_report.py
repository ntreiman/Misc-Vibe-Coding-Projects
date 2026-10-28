#!/usr/bin/env python3
"""Print the Tool Snap table without Fusion - handy for checking the inventory
or rules before opening a design, and for diffing against the spreadsheet.

    python snap_report.py                      # bundled data, medium fit
    python snap_report.py --fit fine --tol 0.05
    python snap_report.py --params my_export.csv --tools my_tools.json
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "ToolSnap"))

from core import expr, inventory, paramcsv, rules  # noqa: E402

DATA = os.path.join(HERE, "ToolSnap", "data")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", default=os.path.join(DATA, "fastener_parameters.csv"),
                    help="Fusion parameter CSV export")
    ap.add_argument("--tools", default=os.path.join(DATA, "shop_tools.json"))
    ap.add_argument("--rules", default=os.path.join(DATA, "snap_rules.json"))
    ap.add_argument("--fit", default=None, help="fine | medium | coarse")
    ap.add_argument("--tol", type=float, default=None, help="snap tolerance in mm")
    args = ap.parse_args(argv)

    ruleset = rules.load(args.rules)
    fit = args.fit or ruleset.defaults.get("fit", "medium")
    tol = args.tol if args.tol is not None else float(ruleset.defaults.get("tolerance_mm", 0))
    tools = inventory.load(args.tools)
    params = paramcsv.values(paramcsv.load(args.params))

    rows = rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit, tol)
    print(f"fit={fit}  tolerance={tol} mm  tools={sum(t.available for t in tools)} available")
    hdr = f"{'Parameter':28} {'Tool':8} {'Mode':8} {'Target':>8} {'Floor':>7} {'Snapped':>8} {'Delta':>8}  {'Tool(s)':10} Note"
    print(hdr)
    print("-" * len(hdr))
    bad = 0
    for s in rows:
        r = s.result
        floor = f"{r.floor_mm:7.3f}" if r.floor_mm is not None else f"{'':7}"
        snapped = f"{r.snapped_mm:8.4f}" if r.ok else f"{'NONE':>8}"
        delta = f"{r.delta_mm:+8.4f}" if r.ok else f"{'':8}"
        bad += not r.ok
        print(f"{s.parameter:28} {s.rule.tool:8} {r.mode:8} {r.target_mm:8.3f} {floor} {snapped} {delta}  {r.tool_label:10} {s.note}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
