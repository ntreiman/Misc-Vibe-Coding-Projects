"""Unit tests for the Fusion-free grouping logic.  Run: python3 -m unittest discover BatchPostByTool/tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batchpost"))
import core  # noqa: E402
import settings  # noqa: E402


def ops(*specs):
    out = []
    for i, spec in enumerate(specs):
        tool, *flags = spec
        out.append(core.OpInfo(name="op%d" % (i + 1), tool_number=tool, suppressed="s" in flags))
    return out


class GroupingTests(unittest.TestCase):
    def test_single_tool_three_ops_one_file(self):
        g = core.group_consecutive(ops((0,), (0,), (0,)))
        self.assertEqual(len(g), 1)
        self.assertEqual([o.name for o in g[0].ops], ["op1", "op2", "op3"])
        self.assertFalse(g[0].tool_repeats)
        self.assertEqual(core.post_property_overrides(g[0])["descriptiveFileNameRun"], 0)

    def test_consecutive_runs_split_in_setup_order(self):
        g = core.group_consecutive(ops((1,), (1,), (2,), (3,), (3,)))
        self.assertEqual([(x.tool_number, len(x.ops)) for x in g], [(1, 2), (2, 1), (3, 2)])
        self.assertEqual([x.index for x in g], [1, 2, 3])

    def test_tool_reused_later_gets_run_numbers(self):
        g = core.group_consecutive(ops((0,), (1,), (0,)))
        self.assertEqual([x.tool_number for x in g], [0, 1, 0])
        self.assertEqual([x.run_of_tool for x in g], [1, 1, 2])
        self.assertEqual([x.tool_repeats for x in g], [True, False, True])
        self.assertEqual(core.post_property_overrides(g[0])["descriptiveFileNameRun"], 1)
        self.assertEqual(core.post_property_overrides(g[2])["descriptiveFileNameRun"], 2)
        self.assertEqual(core.post_property_overrides(g[1])["descriptiveFileNameRun"], 0)

    def test_suppressed_and_toolless_ops_do_not_break_a_run(self):
        g = core.group_consecutive(ops((1,), (1, "s"), (None,), (1,)))
        self.assertEqual(len(g), 1)
        self.assertEqual([o.name for o in g[0].ops], ["op1", "op4"])

    def test_program_names_unique_per_run(self):
        g = core.group_consecutive(ops((0,), (1,), (0,)))
        self.assertEqual([x.program_name for x in g], ["run01_T0", "run02_T1", "run03_T0"])

    def test_forced_post_properties(self):
        g = core.group_consecutive(ops((5,)))
        p = core.post_property_overrides(g[0])
        self.assertTrue(p["descriptiveFileName"])
        self.assertEqual(p["descriptiveFileMethod"], "rename")
        self.assertEqual(p["descriptiveFileNamePrefix"], "op")

    def test_summary(self):
        g = core.group_consecutive(ops((0,), (1,), (0,)))
        self.assertEqual(core.summary_lines(g), ["T0 (run 1 of this tool): op1", "T1: op2", "T0 (run 2 of this tool): op3"])


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        self.assertTrue(settings.resolve_output_folder({}).endswith("Downloads"))
        self.assertEqual(settings.resolve_post_path({}, "/posts"), "/posts/Duet2Ethernet_RRF2051.cps")
        self.assertEqual(settings.resolve_post_path({"post_path": "/x/y.cps"}, "/posts"), "/x/y.cps")


if __name__ == "__main__":
    unittest.main()
