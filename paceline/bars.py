"""Usage bars with eighth-cell steps and a projected shade."""

import re

FILLED = "█"
EIGHTHS = " ▏▎▍▌▋▊▉"
PROJECTED_MIX = 0.45
MONO_USED, MONO_PROJECTED, MONO_TRACK = "█", "▒", "░"


def _clamp(pct):
    return max(0.0, min(100.0, float(pct)))


def _rgb(color, fallback):
    """The (r, g, b) of a 24-bit foreground escape, or fallback when it has none."""
    hit = re.search(r"38;2;(\d+);(\d+);(\d+)", color or "")
    return tuple(int(v) for v in hit.groups()) if hit else fallback


def _fg(rgb):
    return "\033[38;2;%d;%d;%dm" % rgb


def _bg(rgb):
    return "\033[48;2;%d;%d;%dm" % rgb


def _mix(a, b, weight):
    """Color a blended over color b with the given weight."""
    return tuple(round(x * weight + y * (1 - weight)) for x, y in zip(a, b))


def _cell(index, used_e, proj_e, rgb, track):
    """One color cell: used fill, projected shade, or track.

    A partial used cell draws its eighth block over the color that follows it,
    so the bar shows no gap of terminal background.
    """
    used = max(0, min(8, used_e - index * 8))
    proj = max(0, min(8, proj_e - index * 8))
    shade = _mix(rgb, track, PROJECTED_MIX)
    if used == 8:
        return _fg(rgb) + FILLED
    if used:
        behind = shade if proj > used else track
        return "%s%s%s\033[49m" % (_fg(rgb), _bg(behind), EIGHTHS[used])
    return _fg(shade if proj >= 4 else track) + FILLED


def _mono(pct, proj, width):
    """A bar drawn with glyphs only: full cells used, shaded cells projected, light cells track."""
    used = int(round(_clamp(pct) / 100 * width))
    ahead = int(round(_clamp(proj) / 100 * width)) if proj is not None else used
    ahead = max(used, ahead)
    return MONO_USED * used + MONO_PROJECTED * (ahead - used) + MONO_TRACK * (width - ahead)


def bar(theme, pct, color, proj=None, width=8):
    """A width-cell bar for pct in color, with cells up to proj in a dimmer shade.

    pct None draws an empty track. The mono theme draws glyphs and no color.
    """
    if theme.mono:
        return _mono(0 if pct is None else pct, proj, width)
    if pct is None:
        return _fg(theme.track) + FILLED * width + theme.reset
    rgb = _rgb(color, theme.track)
    used_e = int(round(_clamp(pct) / 100 * width * 8))
    proj_e = int(round(_clamp(proj) / 100 * width * 8)) if proj is not None else used_e
    cells = "".join(_cell(i, used_e, proj_e, rgb, theme.track) for i in range(width))
    return cells + theme.reset
