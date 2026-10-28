"""The spreadsheet's Tool Snap tab is the oracle: with the bundled inventory and
parameters, the add-in's rules must reproduce every snapped value it shows."""

import pytest

from core import expr, rules

# Parameter -> (snapped mm, tool label, floor mm) as read off the Tool Snap tab
# (fit = medium, tolerance = 0, drills Up, counterbores Nearest).
SHEET = {
    "m2_clearance_hole": (2.4384, "41", None),
    "m3_clearance_hole": (3.4544, "29", None),
    "m4_clearance_hole": (4.5, "4.5 mm", None),
    "m5_clearance_hole": (5.5, "5.5 mm", None),
    "m6_clearance_hole": (6.6294, "G", None),
    "m2_pilot_drill": (1.6129, "52", None),
    "m3_pilot_drill": (2.5, "2.5 mm", None),
    "m4_pilot_drill": (3.4544, "29", None),
    "m5_pilot_drill": (4.2164, "19", None),
    "m6_pilot_drill": (5.0, "5 mm", None),
    "m2_counterbore_OD_round": (6.0, "6 mm", 4.1),
    "m3_counterbore_OD_round": (7.9375, "5/16", 6.3),
    "m4_counterbore_OD_round": (9.525, "3/8", 8.4),
    "m5_counterbore_OD_round": (12.7, "1/2", 10.3),
    "m6_counterbore_OD_round": (12.7, "1/2", 11.5),
    "m2_counterbore_OD_socket": (6.0, "6 mm", 4.4),
    "m3_counterbore_OD_socket": (7.9375, "5/16", 6.1),
    "m4_counterbore_OD_socket": (9.525, "3/8", 7.8),
    "m5_counterbore_OD_socket": (9.525, "3/8", 9.3),
    "m6_counterbore_OD_socket": (12.7, "1/2", 11.0),
}


# The sheet snapped every drill row Up; the add-in's defaults are now Nearest
# with ISO floors, so force the sheet's modes to compare engines like for like.
SHEET_MODES = {name: "Up" for name in SHEET if "counterbore" not in name}


@pytest.fixture(scope="module")
def snapped(ruleset, tools, params):
    out = rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="medium",
                    mode_overrides=SHEET_MODES)
    return {s.parameter: s for s in out}


def test_every_sheet_row_is_covered(snapped):
    assert set(snapped) == set(SHEET)


@pytest.mark.parametrize("name", sorted(SHEET))
def test_matches_sheet(snapped, name):
    want_mm, want_tool, want_floor = SHEET[name]
    s = snapped[name]
    assert s.result.snapped_mm == pytest.approx(want_mm, abs=1e-4)
    assert s.result.tool_label == want_tool
    # the sheet had floors only on counterbores; drill rows have gained ISO floors since
    if want_floor is not None:
        assert s.result.floor_mm == pytest.approx(want_floor, abs=1e-6)


def test_fine_fit_moves_m3_clearance_to_number_30(ruleset, tools, params):
    out = {s.parameter: s for s in
           rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="fine")}
    assert out["m3_clearance_hole"].result.snapped_mm == pytest.approx(3.2639)
    assert out["m3_clearance_hole"].result.tool_label == "30"


def test_clearance_floor_is_iso_nominal_so_nearest_never_goes_under(ruleset, tools, params):
    # 1/8" (3.175) is closer to 3.2 than #30 (3.264) but below the H12 lower limit
    out = {s.parameter: s for s in
           rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="fine")}
    r = out["m3_clearance_hole"].result
    assert r.floor_mm == 3.2 and r.snapped_mm == pytest.approx(3.2639) and r.tool_label == "30"
    assert r.ceiling_mm == pytest.approx(3.32) and not r.over_ceiling   # H12 over 3-6 mm = +0.12
    assert out["m6_clearance_hole"].result.ceiling_mm == pytest.approx(6.55)  # IT12 over 6-10 = 0.15
    assert out["m2_clearance_hole"].result.ceiling_mm == pytest.approx(2.30)  # IT12 over 1-3 = 0.10


def test_tap_drill_default_stays_inside_6h_minor_band(ruleset, tools, params):
    out = {s.parameter: s for s in
           rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="medium")}
    m4 = out["m4_pilot_drill"].result
    assert m4.floor_mm == pytest.approx(3.242, abs=1e-3) and m4.ceiling_mm == pytest.approx(3.422, abs=1e-3)
    assert m4.tool_label == "30" and out["m4_pilot_drill"].note == "81% thread"
    # #29 would be over the 6H maximum and is flagged when forced
    forced = {s.parameter: s for s in
              rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="medium",
                        mode_overrides={"m4_pilot_drill": "Up"})}
    assert forced["m4_pilot_drill"].result.over_ceiling
    assert forced["m4_pilot_drill"].note == "60% thread, OVER ISO max 3.422"
    for m, lo, hi in (("m2", 1.567, 1.679), ("m3", 2.459, 2.599), ("m5", 4.134, 4.334), ("m6", 4.917, 5.153)):
        r = out[f"{m}_pilot_drill"].result
        assert (r.floor_mm, r.ceiling_mm) == (pytest.approx(lo, abs=1e-3), pytest.approx(hi, abs=1e-3))
        assert r.floor_mm <= r.snapped_mm <= r.ceiling_mm + 1e-9


def test_adding_a_10mm_endmill_changes_m5_socket(ruleset, tools, params):
    from core import inventory
    more = inventory.add_tool(tools, "10 mm", "endmill", 10, "mm")
    out = {s.parameter: s for s in
           rules.run(ruleset, more, lambda e: expr.evaluate(e, params), fit="medium")}
    assert out["m5_counterbore_OD_socket"].result.snapped_mm == 10.0
    assert out["m5_counterbore_OD_socket"].result.tool_label == "10 mm"


def test_mode_override_off(ruleset, tools, params):
    out = {s.parameter: s for s in
           rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="medium",
                     mode_overrides={"m5_counterbore_OD_round": "Off"})}
    assert out["m5_counterbore_OD_round"].result.snapped_mm == 11.5


def test_bad_fit_rejected(ruleset):
    with pytest.raises(ValueError):
        ruleset.expand("sloppy")


def test_notes_thread_percent_and_radial(snapped):
    # Machinery's Handbook convention: % = (D - drill) / (1.299 * pitch)
    assert rules.thread_percent(4.0, 0.7, 3.3) == pytest.approx(77.0, abs=0.5)
    assert snapped["m4_pilot_drill"].note == "60% thread, OVER ISO max 3.422"  # forced Up -> #29
    assert snapped["m5_counterbore_OD_socket"].note == "radial 0.51 mm"
    assert snapped["m2_clearance_hole"].note == ""


def test_non_strict_run_reports_missing_parameters(ruleset, tools, params):
    partial = {k: v for k, v in params.items() if k != "m5_socket_head_OD"}
    out = {s.parameter: s for s in
           rules.run(ruleset, tools, lambda e: expr.evaluate(e, partial), fit="medium", strict=False)}
    bad = out["m5_counterbore_OD_socket"]
    assert bad.result is None and not bad.ok and "m5_socket_head_OD" in bad.error
    assert out["m4_counterbore_OD_socket"].ok
    with pytest.raises(expr.ExpressionError):
        rules.run(ruleset, tools, lambda e: expr.evaluate(e, partial), fit="medium")
