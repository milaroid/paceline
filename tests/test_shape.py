"""Tests for turning the Claude Code payload into the internal reading."""

import json
import os
import tempfile
import unittest

from helpers import claude_payload, subscriber_limits
import shape


class FromClaudeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_subscriber_gets_windows_and_no_cost(self):
        data = claude_payload(rate_limits=subscriber_limits(), cost={"total_cost_usd": 2.5})
        r = shape.from_claude(data, self.dir)
        self.assertEqual([w.label for w in r.windows], ["5h", "7d"])
        self.assertIsNone(r.cost)
        self.assertEqual((r.model, r.effort, r.context), ("Opus 5.5", "high", 41))

    def test_api_key_user_gets_cost(self):
        r = shape.from_claude(claude_payload(cost={"total_cost_usd": 1.24}), self.dir)
        self.assertEqual(r.windows, [])
        self.assertEqual(r.cost, 1.24)

    def test_zero_cost_hidden(self):
        r = shape.from_claude(claude_payload(cost={"total_cost_usd": 0}), self.dir)
        self.assertIsNone(r.cost)

    def test_gateway_spend(self):
        limits = {"spend_limit": {"used_percentage": 63, "resets_at": 1, "used_usd": 314.12,
                                  "limit_usd": 500, "period": "weekly"}}
        r = shape.from_claude(claude_payload(rate_limits=limits, cost={"total_cost_usd": 9}), self.dir)
        self.assertEqual(r.spend.seconds, shape.SEVEN_DAY)
        self.assertEqual(r.spend.limit_usd, 500)
        self.assertIsNone(r.cost)

    def test_unknown_period_defaults_to_monthly(self):
        limits = {"spend_limit": {"used_percentage": 5, "resets_at": 1}}
        r = shape.from_claude(claude_payload(rate_limits=limits), self.dir)
        self.assertEqual(r.spend.seconds, shape.PERIODS["monthly"])

    def test_effort_from_settings_and_fast_mode(self):
        with open(os.path.join(self.dir, "settings.json"), "w", encoding="utf-8") as fh:
            json.dump({"effortLevel": "low",
                       "modelSettings": {"claude-opus-5-5": {"effortLevel": "max"}}}, fh)
        data = claude_payload(fast_mode=True)
        data["model"]["id"] = "claude-opus-5-5[1m]"
        del data["effort"]
        self.assertEqual(shape.from_claude(data, self.dir).effort, "max ⚡")

    def test_empty_payload(self):
        r = shape.from_claude({}, self.dir)
        self.assertEqual((r.model, r.windows, r.context), ("claude", [], None))


if __name__ == "__main__":
    unittest.main()
