"""Tests for reading Codex quota from local session logs."""

import tempfile
import unittest

from helpers import NOW, codex_line, turn_line, write_log
import codex


class WindowLabelTest(unittest.TestCase):
    def test_cases(self):
        for minutes, want in ((300, "5h"), (10080, "7d"), (43200, "30d"), (4320, "3d"),
                              (90, "90m"), (0, "0m"), (None, "0m")):
            with self.subTest(minutes):
                self.assertEqual(codex.window_label(minutes), want)


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def test_no_sessions(self):
        self.assertIsNone(codex.read(self.home))

    def test_newest_log_with_limits_wins(self):
        write_log(self.home, "2027/01/14", "rollout-2027-01-14T09-00-00-a.jsonl",
                  [turn_line("old-model"), codex_line(10, NOW + 86400)])
        write_log(self.home, "2027/01/15", "rollout-2027-01-15T08-00-00-b.jsonl",
                  [turn_line(), codex_line(42, NOW + 86400), codex_line(43, NOW + 86400)])
        write_log(self.home, "2027/01/15", "rollout-2027-01-15T09-00-00-c.jsonl",
                  ['{"type":"session_meta"}', "not json"])
        r = codex.read(self.home)
        self.assertEqual(r.model, "gpt-6-astra")
        self.assertEqual(r.effort, "medium")
        self.assertEqual([(w.label, w.used) for w in r.windows], [("7d", 43)])
        self.assertIsNotNone(r.as_of)

    def test_model_falls_back_to_config(self):
        write_log(self.home, "2027/01/15", "rollout-x.jsonl", [codex_line(5, NOW + 3600, 300)])
        with open(self.home + "/config.toml", "w", encoding="utf-8") as fh:
            fh.write('model = "gpt-cfg"\nmodel_reasoning_effort = "high"\n')
        r = codex.read(self.home)
        self.assertEqual((r.model, r.effort, r.windows[0].label), ("gpt-cfg", "high", "5h"))

    def test_null_primary_is_skipped(self):
        line = codex_line(5, NOW).replace('"primary": {', '"unused": {').replace('"secondary": null', '"primary": null')
        write_log(self.home, "2027/01/15", "rollout-x.jsonl", [line])
        self.assertIsNone(codex.read(self.home))

    def test_limits_beyond_first_tail_are_found(self):
        filler = ['{"type":"response_item","payload":{"text":"%s"}}' % ("x" * 1000)] * 700
        write_log(self.home, "2027/01/15", "rollout-x.jsonl", [codex_line(7, NOW + 3600)] + filler)
        self.assertEqual(codex.read(self.home).windows[0].used, 7)


class CachedReadTest(unittest.TestCase):
    def test_uses_cache_within_ttl(self):
        home = tempfile.mkdtemp()
        write_log(home, "2027/01/15", "rollout-x.jsonl", [codex_line(5, NOW + 3600)])
        store = {}
        first, changed = codex.cached_read(home, store, NOW)
        self.assertTrue(changed)
        write_log(home, "2027/01/15", "rollout-x.jsonl", [codex_line(50, NOW + 3600)])
        cached, changed = codex.cached_read(home, store, NOW + 1)
        self.assertFalse(changed)
        self.assertEqual(cached, first)
        fresh, _ = codex.cached_read(home, store, NOW + codex.CACHE_TTL + 1)
        self.assertEqual(fresh.windows[0].used, 50)

    def test_other_home_skips_cache(self):
        home = tempfile.mkdtemp()
        write_log(home, "2027/01/15", "rollout-x.jsonl", [codex_line(5, NOW + 3600)])
        store = {}
        codex.cached_read(home, store, NOW)
        reading, changed = codex.cached_read(tempfile.mkdtemp(), store, NOW + 1)
        self.assertIsNone(reading)
        self.assertTrue(changed)

    def test_bad_cache_entry_is_ignored(self):
        home = tempfile.mkdtemp()
        store = {"codex": {"ts": NOW, "home": home, "reading": {"bogus": 1}}}
        reading, changed = codex.cached_read(home, store, NOW)
        self.assertIsNone(reading)
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
