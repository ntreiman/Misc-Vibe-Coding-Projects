import os

import pytest

from core import expr, inventory, paramcsv, rules, standards

CSV = os.path.join(os.path.dirname(__file__), "..", "ToolSnap", "data", "fastener_parameters.csv")


def test_bundled_csv_is_generated_from_the_standards_table():
    gen = standards.param_rows(["m2", "m3", "m4", "m5", "m6"])
    assert gen == paramcsv.load(CSV)


def test_size_keys_and_labels():
    assert standards.size_label("m2_5") == "M2.5" and standards.size_label("m10") == "M10"
    assert standards.size_key("M2.5") == "m2_5" and standards.size_key("8") == "m8"
    assert standards.sizes_in(["m8_nominal_dia", "m2_5_nominal_dia", "x_nominal_dia", "m3_pitch"]) == ["m2_5", "m8"]
    assert standards.new_sizes_available(["m2", "m3"])[:2] == ["m1_6", "m2_5"]


def test_families_follow_available_head_data():
    assert standards.families_for("m8") == list(standards.FAMILIES)
    assert standards.families_for("m7") == ["clearance", "tap"]          # no ISO 4762 / 7380 / DIN 7991 size
    assert standards.families_for("m14") == ["clearance", "tap", "counterbore_socket", "countersink"]


def test_m8_parameters_are_consistent_with_the_standards():
    rows = {r.name: r for r in standards.param_rows(["m8"])}
    assert rows["m8_clearance_hole_fine"].value == 8.4 and rows["m8_clearance_hole_coarse"].value == 10.0
    assert rows["m8_clearance_hole_medium_max"].value == pytest.approx(9.22)      # H13: IT13 over 6-10 mm = 0.22
    assert rows["m8_clearance_hole_coarse_max"].value == pytest.approx(10.36)     # 10.0 is in the 6-10 range
    assert rows["m8_tap_drill_min"].value == pytest.approx(6.647, abs=1e-3)
    assert rows["m8_tap_drill_max"].value == pytest.approx(6.912, abs=1e-3)       # published 6H limit
    assert rows["m8_socket_head_OD"].value == 13 and rows["m8_counterbore_ID_socket"].value == 15
    assert rows["m8_counterbore_depth_socket"].value == pytest.approx(8.3)
    values = {n: r.value for n, r in rows.items()}
    for r in rows.values():
        if r.expression:
            assert expr.evaluate(r.expression, values) == pytest.approx(r.value, abs=1e-3), r.name


def test_m12_6h_limits():
    rows = {r.name: r for r in standards.param_rows(["m12"], ["tap"])}
    assert rows["m12_tap_drill_min"].value == pytest.approx(10.106, abs=1e-3)
    assert rows["m12_tap_drill_max"].value == pytest.approx(10.441, abs=1e-3)
    assert "m12_socket_head_OD" not in rows


def test_identifiers_ignore_units_and_numbers():
    assert standards.identifiers("m3_socket_head_OD + 2 * counterbore_radial_clearance + 0.5 mm") == \
        ["m3_socket_head_OD", "counterbore_radial_clearance"]


def test_new_size_snaps_and_missing_family_is_skipped(ruleset, tools):
    # an M8 design with clearance + tap only: counterbore rules are skipped, not errors
    rows = standards.param_rows(["m3", "m8"], ["clearance", "tap"])
    params = paramcsv.values(rows)
    out = rules.run(ruleset, tools, lambda e: expr.evaluate(e, params), "medium", strict=False,
                    sizes=standards.sizes_in(params), has_param=params.__contains__)
    by = {s.parameter: s for s in out}
    assert by["m8_clearance_hole"].ok and by["m8_clearance_hole"].result.tool_label == "9 mm" or \
        by["m8_clearance_hole"].result.snapped_mm >= 9.0
    assert by["m8_pilot_drill"].ok and 6.647 <= by["m8_pilot_drill"].result.snapped_mm <= 6.912 + 1e-9
    assert by["m8_counterbore_ID_socket"].skipped and "m8_socket_head_OD" in by["m8_counterbore_ID_socket"].error
    assert not any(s.result is None and not s.skipped for s in out)


def test_short_names_and_tool_labels():
    assert rules.short_name("m4_counterbore_ID_socket") == "M4 cbore socket"
    assert rules.short_name("m2_5_pilot_drill") == "M2.5 tap drill"
    assert rules.short_name("m3_clearance_hole") == "M3 clearance"
    from core.snap import Tool
    assert inventory.label(Tool("29", "drill", 3.4544, category="Number")) == "#29"
    assert inventory.label(Tool("1/16", "drill", 1.5875, category="Fractional")) == '1/16"'
    assert inventory.label(Tool("E", "drill", 6.35, category="Letter")) == "E"
    assert inventory.label(Tool("5 mm", "endmill", 5.0, category="Metric")) == "5 mm"
