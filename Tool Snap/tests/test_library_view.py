import pytest

from core import library_view as lv
from core.snap import Tool

T = [Tool("29", "drill", 3.4544, True, "Number"), Tool("30", "drill", 3.2639, True, "Number"),
     Tool("1/8", "drill", 3.175, True, "Fractional"), Tool("E", "drill", 6.35, True, "Letter"),
     Tool("3.5 mm", "drill", 3.5, False, "Metric"),
     Tool("3/8", "endmill", 9.525, True, "Imperial"), Tool("1/2", "endmill", 12.7, True, "Imperial"),
     Tool("7/16", "endmill", 11.1125, False, "Imperial"), Tool("10 mm", "endmill", 10.0, True, "Metric")]
AV = {(t.type, t.name): t.available for t in T}


def rows(c, used=None):
    return [r.tool.name for r in lv.build(T, AV, used or {}, c)]


def test_default_sort_is_diameter_ascending_across_types():
    assert rows(lv.Criteria()) == ["1/8", "30", "29", "3.5 mm", "E", "3/8", "10 mm", "7/16", "1/2"]


def test_type_system_and_series_filters():
    assert rows(lv.Criteria(tool_type="endmill")) == ["3/8", "10 mm", "7/16", "1/2"]
    assert rows(lv.Criteria(system="metric")) == ["3.5 mm", "10 mm"]
    assert rows(lv.Criteria(system="imperial", tool_type="drill")) == ["1/8", "30", "29", "E"]
    assert rows(lv.Criteria(series={"Letter", "Fractional"})) == ["1/8", "E"]


def test_availability_range_search_and_used_only():
    assert rows(lv.Criteria(availability="retired")) == ["3.5 mm", "7/16"]
    assert rows(lv.Criteria(dmin_mm=3.3, dmax_mm=6.5)) == ["29", "3.5 mm", "E"]
    assert rows(lv.Criteria(search="#2")) == ["29"]                  # matches the label
    assert rows(lv.Criteria(search="letter")) == ["E"]               # matches the series
    assert rows(lv.Criteria(used_only=True), used={("drill", "29"): ["M3 clearance"]}) == ["29"]


def test_near_shows_closest_on_each_side():
    assert rows(lv.Criteria(near_mm=3.4, near_count=1)) == ["30", "29"]
    assert rows(lv.Criteria(near_mm=3.4, near_count=2, tool_type="drill")) == ["1/8", "30", "29", "3.5 mm"]


def test_sorts():
    assert rows(lv.Criteria(sort="dia_desc"))[:2] == ["1/2", "7/16"]
    assert rows(lv.Criteria(sort="name", tool_type="drill")) == ["29", "30", "1/8", "3.5 mm", "E"]
    by_series = lv.build(T, AV, {}, lv.Criteria(sort="series", tool_type="drill"))
    assert [lv.group_title(r) for r in by_series] == ["Fractional drills", "Letter drills",
                                                      "Metric drills", "Number drills", "Number drills"]


def test_step_up_uses_available_tools_only():
    r = {x.tool.name: x for x in lv.build(T, AV, {}, lv.Criteria())}
    assert r["3/8"].step_up_mm == pytest.approx(0.475) and r["3/8"].next_up.name == "10 mm"
    assert r["10 mm"].step_up_mm == pytest.approx(2.7) and r["10 mm"].next_up.name == "1/2"   # 7/16 is retired
    assert r["1/2"].step_up_mm is None
    av = dict(AV); av[("endmill", "7/16")] = True
    r2 = {x.tool.name: x for x in lv.build(T, av, {}, lv.Criteria())}
    assert r2["10 mm"].next_up.name == "7/16"


def test_units_helpers_and_summary():
    assert lv.fmt(25.4, "in") == "1.0000" and lv.fmt(3.4544, "mm") == "3.454"
    assert lv.to_mm(0.5, "in") == pytest.approx(12.7) and lv.to_mm(None, "in") is None
    assert lv.summary(lv.build(T, AV, {}, lv.Criteria()), T, AV) == "Showing 9 of 9 tools (7 available, 2 retired)."
