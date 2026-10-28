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


@pytest.fixture(scope="module")
def snapped(ruleset, tools, params):
    out = rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="medium")
    return {s.parameter: s for s in out}


def test_every_sheet_row_is_covered(snapped):
    assert set(snapped) == set(SHEET)


@pytest.mark.parametrize("name", sorted(SHEET))
def test_matches_sheet(snapped, name):
    want_mm, want_tool, want_floor = SHEET[name]
    s = snapped[name]
    assert s.result.snapped_mm == pytest.approx(want_mm, abs=1e-4)
    assert s.result.tool_label == want_tool
    if want_floor is None:
        assert s.result.floor_mm is None
    else:
        assert s.result.floor_mm == pytest.approx(want_floor, abs=1e-6)


def test_fine_fit_moves_m3_clearance_to_number_30(ruleset, tools, params):
    out = {s.parameter: s for s in
           rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), fit="fine")}
    assert out["m3_clearance_hole"].result.snapped_mm == pytest.approx(3.2639)
    assert out["m3_clearance_hole"].result.tool_label == "30"


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
    assert snapped["m4_pilot_drill"].note == "60% thread"        # #29 is a loose tap drill for M4
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
