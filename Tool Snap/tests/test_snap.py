import pytest

from core.snap import Tool, snap

EM = [Tool("1/4", "endmill", 6.35), Tool("5/16", "endmill", 7.9375),
      Tool("3/8", "endmill", 9.525), Tool("1/2", "endmill", 12.7),
      Tool("7/16", "endmill", 11.1125, available=False),
      Tool("29", "drill", 3.4544)]


def test_up_picks_smallest_tool_at_or_above_target():
    r = snap(7.5, EM, "endmill", "Up")
    assert (r.snapped_mm, r.tools, r.delta_mm) == (7.9375, ["5/16"], 0.4375)


def test_exact_match_has_zero_delta():
    assert snap(6.35, EM, "endmill", "Up").delta_mm == 0


def test_down_respects_floor_and_falls_back_to_up():
    assert snap(10.5, EM, "endmill", "Down", floor_mm=9.3).snapped_mm == 9.525
    # 3/8 is below the floor, so Down has nothing and falls back to 1/2
    assert snap(11.5, EM, "endmill", "Down", floor_mm=10.3).snapped_mm == 12.7


def test_nearest_ties_go_up():
    tools = [Tool("a", "endmill", 9.0), Tool("b", "endmill", 11.0)]
    assert snap(10.0, tools, "endmill", "Nearest").snapped_mm == 11.0


def test_nearest_prefers_closer_side():
    assert snap(9.6, EM, "endmill", "Nearest").snapped_mm == 9.525
    assert snap(9.0, EM, "endmill", "Nearest").snapped_mm == 9.525


def test_unavailable_tools_are_ignored():
    assert snap(11.0, EM, "endmill", "Up").snapped_mm == 12.7


def test_tool_type_filter():
    r = snap(3.4, EM, "endmill", "Up")
    assert r.snapped_mm == 6.35  # the #29 drill is not an endmill


def test_tolerance_lets_slightly_small_tool_serve():
    assert snap(3.2, [Tool("1/8", "endmill", 3.175)], "endmill", "Up").snapped_mm is None
    assert snap(3.2, [Tool("1/8", "endmill", 3.175)], "endmill", "Up", tolerance_mm=0.05).snapped_mm == 3.175


def test_off_passes_target_through():
    r = snap(10.5, EM, "endmill", "Off", floor_mm=9.3)
    assert (r.snapped_mm, r.tool_label, r.delta_mm) == (10.5, "(not snapped)", 0)


def test_no_tool_large_enough():
    r = snap(30.0, EM, "endmill", "Up")
    assert not r.ok and r.tool_label == "no tool" and r.delta_mm is None


def test_unknown_mode():
    with pytest.raises(ValueError):
        snap(1, EM, "endmill", "Sideways")


def test_keep_leaves_parameter_alone():
    r = snap(10.5, EM, "endmill", "Keep", floor_mm=9.3)
    assert r.kept and not r.ok and r.tool_label == "(kept as is)" and r.delta_mm is None
