import os

import pytest

from core import expr, inventory, paramcsv
from core.snap import Tool


def test_inventory_loads_sheet_libraries(tools):
    drills = [t for t in tools if t.type == "drill"]
    endmills = [t for t in tools if t.type == "endmill" and t.available]
    assert len(drills) == 132 and all(t.available for t in drills)
    assert sorted(t.name for t in endmills) == sorted(
        ["1/8", "3/16", "1/4", "5/16", "3/8", "1/2", "3/4", "1", "5 mm", "6 mm"])


def test_add_tool_inch_and_replace():
    base = [Tool("1/2", "endmill", 12.7)]
    out = inventory.add_tool(base, "7/16", "endmill", 0.4375, "in")
    assert [t.name for t in out] == ["1/2", "7/16"]
    assert out[1].diameter_mm == pytest.approx(11.1125)
    out = inventory.add_tool(out, "7/16", "endmill", 11.1, "mm")   # replaces, same count
    assert len(out) == 2 and out[-1].diameter_mm == 11.1


def test_add_tool_default_name_and_validation():
    out = inventory.add_tool([], "", "drill", 0.25, "in")
    assert out[0].name == '0.25"'
    assert inventory.add_tool([], "", "drill", 10, "mm")[0].name == "10 mm"
    with pytest.raises(ValueError):
        inventory.add_tool([], "x", "lathe", 1)
    with pytest.raises(ValueError):
        inventory.add_tool([], "x", "drill", 0)


def test_set_available_and_roundtrip(tmp_path):
    tools = inventory.add_tool([], "10 mm", "endmill", 10)
    tools = inventory.set_available(tools, "10 mm", "endmill", False)
    path = str(tmp_path / "inv.json")
    inventory.save(path, tools)
    back = inventory.load(path)
    assert back == tools and back[0].available is False


def test_paramcsv_roundtrip(tmp_path):
    rows = paramcsv.load(os.path.join(os.path.dirname(__file__), "..", "ToolSnap", "data",
                                      "fastener_parameters.csv"))
    assert len(rows) == 128
    by = {r.name: r for r in rows}
    assert by["m3_counterbore_depth_socket"].expression == \
        "m3_socket_head_height + counterbore_depth_clearance"
    assert by["m3_clearance_hole"].favorite and not by["m3_nominal_dia"].favorite
    path = str(tmp_path / "p.csv")
    paramcsv.save(path, rows)
    assert paramcsv.load(path) == rows


def test_expression_evaluator():
    p = {"a": 3, "b_2": 0.5}
    assert expr.evaluate("a + 2 * b_2", p) == 4
    assert expr.evaluate("(a - b_2) / 2", p) == 1.25
    assert expr.evaluate("-a + 1 in", p) == (-3 + 1) * 25.4
    with pytest.raises(expr.ExpressionError):
        expr.evaluate("a + zzz", p)
    with pytest.raises(expr.ExpressionError):
        expr.evaluate("__import__('os')", p)


def test_bundled_expressions_all_evaluate(params):
    rows = paramcsv.load(os.path.join(os.path.dirname(__file__), "..", "ToolSnap", "data",
                                      "fastener_parameters.csv"))
    for r in rows:
        if r.expression:
            assert expr.evaluate(r.expression, params) == pytest.approx(r.value, abs=1e-3), r.name


def test_sheet_export_matches_google_sheet_tabs(tools, tmp_path):
    import csv
    written = inventory.export_sheet_csvs(tools, str(tmp_path))
    assert sorted(os.path.basename(p) for p in written.values()) == ["Drill Library.csv", "Endmill Library.csv"]
    drills = list(csv.reader(open(written["drill"], newline="")))
    mills = list(csv.reader(open(written["endmill"], newline="")))
    assert drills[0] == ["Name", "Tool Category", "Imperial/Metric", "Unit", "Value (inch)", "Value (mm)",
                         "Drill Category", "Available"]
    assert mills[0] == ["Name", "Tool Category", "Imperial/Metric", "Unit", "Value (inch)", "Value (mm)", "Available"]
    assert len(drills) == 133 and len(mills) == 226          # header + every tool, like the sheet
    by = {r[0]: r for r in drills[1:]}
    assert by["29"][1:] == ["Drill", "Imperial", "in", "0.1360", "3.4544", "Number", "YES"]
    assert by["5 mm"][1:] == ["Drill", "Metric", "mm", "0.1969", "5.0000", "Metric", "YES"]
    bym = {r[0]: r for r in mills[1:]}
    assert bym["3/8"][1:] == ["Endmill", "Imperial", "in", "0.3750", "9.5250", "YES"]
    assert bym["7/16"][-1] == "NO"
