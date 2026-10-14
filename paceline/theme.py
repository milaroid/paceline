"""Color themes: dark, light, and mono."""

from collections import namedtuple

Theme = namedtuple(
    "Theme",
    "name mono reset dim bold italic no_italic track blue green amber red accent claude codex",
)


def fg(r, g, b):
    """A 24-bit foreground color escape."""
    return "\033[38;2;%d;%d;%dm" % (r, g, b)


DARK = Theme(
    "dark", False, "\033[0m", fg(148, 148, 148), "\033[1m", "\033[3m", "\033[23m",
    (58, 68, 86),
    fg(90, 165, 225), fg(80, 200, 130), fg(225, 190, 70), fg(240, 100, 85),
    fg(80, 190, 210), fg(230, 125, 34), fg(170, 170, 170),
)
LIGHT = Theme(
    "light", False, "\033[0m", fg(98, 98, 98), "\033[1m", "\033[3m", "\033[23m",
    (208, 214, 222),
    fg(25, 100, 180), fg(20, 115, 60), fg(150, 90, 0), fg(195, 35, 25),
    fg(0, 110, 140), fg(170, 75, 0), fg(95, 95, 95),
)
MONO = Theme("mono", True, "", "", "", "", "", None, "", "", "", "", "", "", "")
THEMES = {t.name: t for t in (DARK, LIGHT, MONO)}


def get(name):
    """The theme called name, or the dark theme when the name is unknown."""
    return THEMES.get(name, DARK)


def load_color(theme, pct):
    """The load-ladder color for pct: blue under 50, green to 70, amber to 90, red from 90."""
    if pct is None:
        return theme.dim
    if pct >= 90:
        return theme.red
    if pct >= 70:
        return theme.amber
    if pct >= 50:
        return theme.green
    return theme.blue
