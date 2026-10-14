"""Tests for bars, themes, layout, and the end-to-end build."""

import json
import os
import re
import tempfile
import unittest

import helpers
from helpers import NOW, claude_payload, codex_line, subscriber_limits, turn_line, write_log
import bars
import config
import layout
import paceline
import theme
from shape import Reading, Window

COLOR = re.compile(r"\x1b\[[0-9;]*m")
LINK = re.compile(r"\x1b\]8;;[^\a]*\a")


def plain(text):
    return COLOR.sub("", LINK.sub("", text))


class BarTest(unittest.TestCase):
    def test_mono_glyphs(self):
        self.assertEqual(bars.bar(theme.MONO, 50, "", 75, 8), "████▒▒░░")
        self.assertEqual(bars.bar(theme.MONO, None, "", None, 4), "░░░░")
        self.assertEqual(bars.bar(theme.MONO, 150, "", None, 4), "████")

    def test_color_bar_width(self):
        for pct, proj in ((0, None), (41, None), (63, 105), (100, 100), (None, None)):
            with self.subTest(pct):
                cells = bars.bar(theme.DARK, pct, theme.DARK.blue, proj, 8)
                self.assertEqual(layout.visible_width(cells), 8)


class ThemeTest(unittest.TestCase):
    def test_ladder(self):
        t = theme.DARK
        for pct, want in ((None, t.dim), (10, t.blue), (50, t.green), (70, t.amber), (90, t.red)):
            self.assertEqual(theme.load_color(t, pct), want)

    def test_unknown_name_falls_back(self):
        self.assertIs(theme.get("neon"), theme.DARK)


class DurationTest(unittest.TestCase):
    def test_cases(self):
        for secs, want in ((5, "now"), (2700, "45m"), (22320, "6h12m"), (183600, "2d3h"), (-9, "now")):
            self.assertEqual(layout.duration(secs), want)


def ctx(name="dark", **cfg):
    return layout.Context(theme.get(name), config.merge(dict(cfg, theme=name)), NOW)


def claude(**kw):
    base = dict(agent="claude", model="Opus 5.5", effort="high",
                windows=[Window("5h", 63, NOW + 7200, 18000), Window("7d", 76, NOW + 155520, 604800)],
                context=41, cost=None, spend=None, as_of=None)
    base.update(kw)
    return Reading(**base)


def codex_reading(**kw):
    base = dict(agent="codex", model="gpt-6-astra", effort="medium",
                windows=[Window("7d", 12, NOW + 86400, 604800)],
                context=None, cost=None, spend=None, as_of=NOW - 7200)
    base.update(kw)
    return Reading(**base)


class LayoutTest(unittest.TestCase):
    def render(self, limit, readings=None, c=None, runway=None):
        readings = readings or [claude(), codex_reading()]
        data = {"cwd": "/x/api", "pr": {"number": 6, "review_state": "pending"},
                "prompt_cache": {"caching_observed": True, "warm": True, "hit_ratio": 0.92}}
        git_state = {"branch": "main", "detached": False, "dirty": 3, "ahead": 1, "behind": 0, "worktree": None}
        return layout.render(c or ctx(), data, (readings, {"claude": runway or {}}), git_state, limit)

    def test_full_width(self):
        lines = [plain(x) for x in self.render(None, runway={"5h": 2280})]
        self.assertTrue(lines[0].startswith("» Opus 5.5 high"))
        self.assertIn("63%→105% empty ~38m ↻2h0m", lines[0])
        self.assertIn("ctx", lines[0])
        self.assertIn("· 2h0m ago", lines[1])
        self.assertEqual(lines[2], "api │ ⎇ main ●3 ↑1 │ PR #6 review │ cache 92%")

    def test_fitting_widths(self):
        for limit in (160, 120, 90, 76, 64):
            with self.subTest(limit):
                widest = max(layout.visible_width(x) for x in self.render(limit))
                self.assertLessEqual(widest, limit)

    def test_too_narrow_uses_last_fit(self):
        last = layout.fits(8)[-1]
        c = ctx()
        want = layout.usage_rows(c, [claude(), codex_reading()], {"claude": {}}, last)
        self.assertEqual(self.render(20)[:len(want)], want)

    def test_utf8_output(self):
        import subprocess
        import sys
        script = os.path.join(helpers.ROOT, "paceline", "paceline.py")
        env = dict(os.environ, PYTHONIOENCODING="cp1252", COLUMNS="120",
                   XDG_CONFIG_HOME=tempfile.mkdtemp(), CODEX_HOME=tempfile.mkdtemp(),
                   APPDATA=tempfile.mkdtemp())
        payload = json.dumps(claude_payload(rate_limits=subscriber_limits())).encode()
        out = subprocess.run([sys.executable, script], input=payload, capture_output=True, env=env).stdout
        self.assertIn("»".encode("utf-8"), out)

    def test_narrow_drops_codex_row(self):
        lines = self.render(46)
        self.assertFalse(any("gpt-6" in plain(x) for x in lines))

    def test_worktree_mark(self):
        c = ctx()
        same = {"branch": "b", "detached": False, "dirty": 0, "ahead": 0, "behind": 0, "worktree": "api"}
        other = dict(same, worktree="feature")
        self.assertEqual(plain(layout.identity_line(c, {"cwd": "/x/api"}, same, layout.fits(8)[0])), "api │ ⎇ b")
        self.assertEqual(plain(layout.identity_line(c, {"cwd": "/x/api"}, other, layout.fits(8)[0])), "api │ ⎇ b ⌂feature")

    def test_mono_has_no_color(self):
        lines = self.render(None, c=ctx("mono"))
        self.assertFalse(any(COLOR.search(x) for x in lines))

    def test_reset_window(self):
        reading = codex_reading(windows=[Window("7d", 90, NOW - 1, 604800)])
        lines = [plain(x) for x in self.render(None, readings=[claude(), reading])]
        self.assertIn("7d reset", lines[1])

    def test_cost_and_spend(self):
        from shape import Spend
        spend = Spend(63, NOW + 20 * 86400, 30 * 86400, 314.12, 500)
        api = claude(windows=[], cost=1.24)
        gw = claude(windows=[], spend=spend)
        self.assertIn("│ ~$1.24", plain(self.render(None, readings=[api])[0]))
        self.assertIn("$ ", plain(self.render(None, readings=[gw])[0]))
        self.assertIn("$314/$500", plain(self.render(None, readings=[gw])[0]))


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {"XDG_CONFIG_HOME": os.path.join(self.tmp, "cfg"),
                    "CODEX_HOME": os.path.join(self.tmp, "codex"),
                    "CLAUDE_CONFIG_DIR": os.path.join(self.tmp, "claude"),
                    "COLUMNS": "200"}
        if os.name == "nt":
            self.env["APPDATA"] = os.path.join(self.tmp, "appdata")

    def build(self, data):
        return [plain(x) for x in paceline.build(data, self.env, NOW)]

    def test_subscriber_with_codex(self):
        write_log(self.env["CODEX_HOME"], "2027/01/15", "rollout-a.jsonl",
                  [turn_line(), codex_line(12, NOW + 86400)])
        lines = self.build(claude_payload(rate_limits=subscriber_limits()))
        self.assertEqual(len(lines), 3)
        self.assertIn("5h", lines[0])
        self.assertIn("gpt-6-astra medium", lines[1])
        self.assertEqual(lines[2], "project")

    def test_codex_disabled_and_quotes_enabled(self):
        import paths
        where = paths.resolve(self.env)
        os.makedirs(where.config_dir, exist_ok=True)
        with open(where.config_file, "w", encoding="utf-8") as fh:
            json.dump({"codex": False, "quotes": True}, fh)
        write_log(self.env["CODEX_HOME"], "2027/01/15", "rollout-a.jsonl", [codex_line(12, NOW + 86400)])
        lines = self.build(claude_payload(rate_limits=subscriber_limits()))
        self.assertFalse(any("codex" in x for x in lines))
        self.assertTrue(lines[-1].startswith("To Himself: "))

    def test_runway_appears_after_samples(self):
        data = claude_payload(rate_limits=subscriber_limits(five=55.0))
        paceline.build(data, self.env, NOW - 300)
        data = claude_payload(rate_limits=subscriber_limits(five=63.0))
        line = plain(paceline.build(data, self.env, NOW)[0])
        self.assertIn("empty ~", line)

    def test_width_limit(self):
        self.assertEqual(paceline.width_limit({"COLUMNS": "120"}), 116)
        self.assertEqual(paceline.width_limit({"COLUMNS": "10"}), paceline.MIN_WIDTH)
        self.assertIsNone(paceline.width_limit({}))


class ConfigTest(unittest.TestCase):
    def test_merge(self):
        cfg = config.merge({"theme": "light", "bar_width": 99, "quotes": "yes", "codex": False, "x": 1})
        self.assertEqual(cfg["theme"], "light")
        self.assertEqual(cfg["bar_width"], 8)
        self.assertIs(cfg["quotes"], False)
        self.assertIs(cfg["codex"], False)
        self.assertNotIn("x", cfg)

    def test_bool_is_not_int(self):
        self.assertEqual(config.merge({"bar_width": True})["bar_width"], 8)


if __name__ == "__main__":
    unittest.main()
