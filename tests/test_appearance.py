"""Tests for the auto theme and the palette contrast."""

import json
import os
import re
import tempfile
import unittest

from helpers import NOW
import appearance
import theme


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


class ClaudeThemeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_plain_value(self):
        write(os.path.join(self.dir, "settings.json"), {"theme": "light-daltonized"})
        self.assertEqual(appearance.claude_theme(self.dir), "light-daltonized")

    def test_custom_theme_uses_its_base(self):
        write(os.path.join(self.dir, "settings.json"), {"theme": "custom:paper"})
        write(os.path.join(self.dir, "themes", "paper.json"), {"base": "light-ansi"})
        self.assertEqual(appearance.claude_theme(self.dir), "light-ansi")

    def test_custom_theme_without_file_is_dark(self):
        write(os.path.join(self.dir, "settings.json"), {"theme": "custom:gone"})
        self.assertEqual(appearance.claude_theme(self.dir), "dark")

    def test_missing(self):
        self.assertIsNone(appearance.claude_theme(self.dir))


class PaletteTest(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("light", False, "light"), ("light-ansi", False, "light"), ("dark-daltonized", True, "dark"),
            ("auto", True, "light"), ("auto", False, "dark"), (None, True, "light"), ("weird", False, "dark"),
        ]
        for value, light, want in cases:
            with self.subTest(value=value, light=light):
                self.assertEqual(appearance.palette(value, lambda: light), want)


class BackgroundTest(unittest.TestCase):
    def test_cases(self):
        cases = [
            ({"COLORFGBG": "0;15"}, False, True),
            ({"COLORFGBG": "15;0"}, True, False),
            ({"COLORFGBG": "default;default", "TERM_PROGRAM": "Apple_Terminal"}, True, True),
            ({"TERM_PROGRAM": "Apple_Terminal"}, False, False),
            ({"TERM_PROGRAM": "ghostty"}, True, False),
            ({}, True, False),
        ]
        for env, os_light, want in cases:
            with self.subTest(env=env):
                self.assertEqual(appearance.background_is_light(env, lambda: os_light), want)

    def test_os_cache(self):
        store = {"appearance": {"ts": NOW, "light": True}}
        self.assertEqual(appearance.cached_os_is_light(store, NOW + 1), (True, False))


def luminance(rgb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = map(channel, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ContrastTest(unittest.TestCase):
    BACKGROUNDS = {
        "dark": [(0, 0, 0), (30, 30, 30), (40, 42, 54)],
        "light": [(255, 255, 255), (245, 245, 245), (253, 246, 227)],
    }

    def test_text_colors_reach_4_5(self):
        for name, backgrounds in self.BACKGROUNDS.items():
            palette = theme.get(name)
            for field in ("dim", "blue", "green", "amber", "red", "accent", "claude", "codex"):
                rgb = tuple(int(v) for v in re.search(r"38;2;(\d+);(\d+);(\d+)", getattr(palette, field)).groups())
                for bg in backgrounds:
                    with self.subTest(theme=name, field=field, bg=bg):
                        self.assertGreaterEqual(contrast(rgb, bg), 4.5)


if __name__ == "__main__":
    unittest.main()
