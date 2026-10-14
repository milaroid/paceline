"""Tests for the projection, sampling, burn rate, and runway."""

import unittest

from helpers import NOW
import pace
from shape import Reading, Window

HOUR = 3600
FIVE = 5 * HOUR


class ProjectTest(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("halfway doubles", 30, NOW + FIVE / 2, 60.0),
            ("missing used", None, NOW + HOUR, None),
            ("missing reset", 30, None, None),
            ("first 2% of window", 1, NOW + FIVE - 60, None),
            ("capped", 90, NOW + FIVE - 400, pace.MAX_PROJECTION),
        ]
        for name, used, resets, want in cases:
            with self.subTest(name):
                got = pace.project(used, resets, FIVE, NOW)
                if want is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, want, places=3)


class RecordTest(unittest.TestCase):
    def test_appends_on_change(self):
        self.assertEqual(pace.record([[NOW - 5, 10]], 11, NOW, 600), [[NOW - 5, 10], [NOW, 11]])

    def test_skips_same_value_within_interval(self):
        self.assertEqual(pace.record([[NOW - 5, 10]], 10, NOW, 600), [[NOW - 5, 10]])

    def test_appends_same_value_after_interval(self):
        self.assertEqual(len(pace.record([[NOW - 31, 10]], 10, NOW, 600)), 2)

    def test_drops_old_points(self):
        self.assertEqual(pace.record([[NOW - 900, 5]], 10, NOW, 600), [[NOW, 10]])


class BurnRateTest(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("rising", [[NOW - 300, 50], [NOW, 56]], 0.02),
            ("one point", [[NOW, 50]], None),
            ("short span", [[NOW - 30, 50], [NOW, 56]], None),
            ("flat", [[NOW - 300, 50], [NOW, 50]], None),
            ("old points ignored", [[NOW - 900, 0], [NOW - 120, 50], [NOW, 56]], 0.05),
        ]
        for name, samples, want in cases:
            with self.subTest(name):
                got = pace.burn_rate(samples, NOW, 600)
                if want is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, want)


class RunwayTest(unittest.TestCase):
    def test_shown_when_limit_hits_before_reset(self):
        win = Window("5h", 63, NOW + 2 * HOUR, FIVE)
        secs = pace.runway(win, [[NOW - 300, 55], [NOW, 63]], NOW, 600)
        self.assertAlmostEqual(secs, 37 / (8 / 300))

    def test_hidden_when_projection_under_100(self):
        win = Window("5h", 20, NOW + 2 * HOUR, FIVE)
        self.assertIsNone(pace.runway(win, [[NOW - 300, 10], [NOW, 20]], NOW, 600))

    def test_hidden_when_reset_comes_first(self):
        win = Window("5h", 95, NOW + 60, FIVE)
        self.assertIsNone(pace.runway(win, [[NOW - 300, 94.9], [NOW, 95]], NOW, 600))


class UpdateRunwaysTest(unittest.TestCase):
    def reading(self, used, resets):
        return Reading("claude", "m", None, [Window("5h", used, resets, FIVE)], None, None, None, None)

    def test_keys_by_reset_and_drops_expired(self):
        store = {"runway": {"claude:5h:%d" % int(NOW - 1): [[NOW - 100, 99]]}}
        out, changed = pace.update_runways(store, self.reading(10, NOW + HOUR), NOW, 600)
        self.assertTrue(changed)
        self.assertEqual(list(store["runway"]), ["claude:5h:%d" % int(NOW + HOUR)])
        self.assertIsNone(out["5h"])

    def test_unchanged_store_reports_no_change(self):
        key = "claude:5h:%d" % int(NOW + HOUR)
        store = {"runway": {key: [[NOW - 5, 10]]}}
        _, changed = pace.update_runways(store, self.reading(10, NOW + HOUR), NOW, 600)
        self.assertFalse(changed)

    def test_repairs_bad_store(self):
        store = {"runway": "junk"}
        pace.update_runways(store, self.reading(10, NOW + HOUR), NOW, 600)
        self.assertIsInstance(store["runway"], dict)


if __name__ == "__main__":
    unittest.main()
