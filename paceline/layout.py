"""Row layout: one usage row per agent, the identity line, and the narrow-terminal fits."""

import os
import re
import unicodedata
from collections import namedtuple

import identity
from bars import bar
from pace import project
from shape import Window
from theme import load_color

MARK = "»"
LABEL_MIN = 8
STALE_AFTER = 60
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;[^\a]*\a")

Fit = namedtuple("Fit", "countdown runway arrow bar cache codex")
Context = namedtuple("Context", "theme cfg now")


def fits(width):
    """Fit levels from the fullest to the most compact.

    Detail drops in this order: reset countdowns, the runway, projection arrows,
    bar width, the cache segment, then the Codex row.
    """
    short = min(5, width)
    return (
        Fit(True, True, True, width, True, True),
        Fit(False, True, True, width, True, True),
        Fit(False, False, True, width, True, True),
        Fit(False, False, False, width, True, True),
        Fit(False, False, False, short, True, True),
        Fit(False, False, False, short, False, True),
        Fit(False, False, False, short, False, False),
    )


def visible_width(text):
    """Terminal cells used by text, ignoring escape codes and counting wide glyphs as two."""
    plain = ANSI_RE.sub("", text or "")
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in plain)


def duration(secs):
    """A short duration: now, 45m, 6h12m, or 2d3h."""
    secs = max(0, int(secs))
    if secs < 60:
        return "now"
    days, rem = divmod(secs, 86400)
    hours, mins = rem // 3600, (rem % 3600) // 60
    if days:
        return "%dd%dh" % (days, hours)
    if hours:
        return "%dh%dm" % (hours, mins)
    return "%dm" % mins


def _join(theme, parts):
    sep = "%s │ %s" % (theme.dim, theme.reset)
    return sep.join(p for p in parts if p)


def _percent(theme, value, color):
    if value is None:
        return "%s--%%%s" % (theme.dim, theme.reset)
    return "%s%3.0f%%%s" % (color, value, theme.reset)


def _extras(ctx, win, loads, fit, runway):
    t = ctx.theme
    proj, load = loads
    out = ""
    if proj is not None and fit.arrow:
        out += "%s→%s%s%.0f%%%s" % (t.dim, t.reset, load_color(t, load), proj, t.reset)
    if runway and fit.runway:
        out += " %sempty ~%s%s" % (t.red, duration(runway), t.reset)
    if fit.countdown and _countdown_due(ctx, win, load):
        out += " %s↻%s%s" % (t.dim, duration(float(win.resets_at) - ctx.now), t.reset)
    return out


def _countdown_due(ctx, win, load):
    return bool(win.resets_at) and load is not None and load >= ctx.cfg["countdown_min_load"]


def window_segment(ctx, win, fit, as_of=None, runway=None):
    """A pace-aware bar for one window: label, bar, used percent, projection, runway, countdown.

    as_of is the time of the reading when it is older than now. A window whose
    reset time has passed shows 'reset'.
    """
    t = ctx.theme
    if win.resets_at and float(win.resets_at) <= ctx.now:
        return "%s%s reset%s" % (t.dim, win.label, t.reset)
    proj = project(win.used, win.resets_at, win.seconds, as_of or ctx.now)
    load = proj if proj is not None else win.used
    color = load_color(t, load)
    text = "%s%s%s %s %s" % (t.dim, win.label, t.reset,
                             bar(t, win.used, color, proj, fit.bar), _percent(t, win.used, color))
    return text + _extras(ctx, win, (proj, load), fit, runway)


def context_segment(ctx, pct, fit):
    """The context window bar."""
    t = ctx.theme
    color = load_color(t, pct)
    return "%sctx%s %s %s" % (t.dim, t.reset, bar(t, pct, color, None, fit.bar), _percent(t, pct, color))


def spend_segment(ctx, spend, fit):
    """The projected spend-limit bar with the dollar figures when the gateway sends them."""
    text = window_segment(ctx, Window("$", spend.used, spend.resets_at, spend.seconds), fit)
    if spend.used_usd is not None and spend.limit_usd is not None:
        text += " %s$%.0f/$%.0f%s" % (ctx.theme.dim, spend.used_usd, spend.limit_usd, ctx.theme.reset)
    return text


def _stale(ctx, as_of):
    if not as_of or ctx.now - as_of < STALE_AFTER:
        return None
    return "%s· %s ago%s" % (ctx.theme.dim, duration(ctx.now - as_of), ctx.theme.reset)


def agent_parts(ctx, reading, runways, fit):
    """The segments of one agent row."""
    parts = [window_segment(ctx, w, fit, reading.as_of, (runways or {}).get(w.label))
             for w in reading.windows]
    if reading.agent == "claude":
        parts.append(context_segment(ctx, reading.context, fit))
    if reading.spend:
        parts.append(spend_segment(ctx, reading.spend, fit))
    if reading.cost:
        parts.append("%s~$%s%.2f" % (ctx.theme.dim, ctx.theme.reset, reading.cost))
    parts.append(_stale(ctx, reading.as_of))
    return parts


def _live(ctx, win):
    return win.used is not None and not (win.resets_at and float(win.resets_at) <= ctx.now)


def _loads(ctx, reading):
    wins = list(reading.windows) + ([reading.spend] if reading.spend else [])
    for win in wins:
        if _live(ctx, win):
            proj = project(win.used, win.resets_at, win.seconds, reading.as_of or ctx.now)
            yield proj if proj is not None else win.used


def worst_load(ctx, readings):
    """The highest projected or used load across every live window, or None."""
    loads = [load for reading in readings for load in _loads(ctx, reading)]
    return max(loads) if loads else None


def _label(reading):
    return " ".join(p for p in (reading.model, reading.effort) if p)


def usage_rows(ctx, readings, runways, fit):
    """One row per agent. The first row starts with the mark, colored by the worst load."""
    t = ctx.theme
    shown = [r for r in readings if r and (r.agent == "claude" or fit.codex)]
    width = max([LABEL_MIN] + [visible_width(_label(r)) for r in shown])
    mark = "%s%s%s" % (load_color(t, worst_load(ctx, shown)), MARK, t.reset)
    rows = []
    for i, reading in enumerate(shown):
        label = _label(reading)
        color = t.claude if reading.agent == "claude" else t.codex
        lead = mark if i == 0 else " "
        body = _join(t, agent_parts(ctx, reading, runways.get(reading.agent), fit))
        rows.append("%s %s%s%s%s  %s" % (lead, color, label, t.reset,
                                          " " * (width - visible_width(label)), body))
    return rows


def identity_line(ctx, data, git_state, fit):
    """Folder, git branch, pull request, and cache ratio."""
    t = ctx.theme
    workspace = data.get("workspace") or {}
    cwd = data.get("cwd") or workspace.get("current_dir")
    url = identity.repo_url(workspace, (git_state or {}).get("branch"))
    git_state = _without_folder_worktree(git_state, cwd)
    return _join(t, [
        identity.folder(t, cwd),
        identity.git_segment(t, git_state, url),
        identity.pr_segment(t, data.get("pr")),
        identity.cache_segment(t, data.get("prompt_cache")) if fit.cache else None,
    ])


def _without_folder_worktree(git_state, cwd):
    """git_state without its worktree name when that name equals the folder name."""
    if not git_state or not cwd or git_state.get("worktree") != os.path.basename(os.path.normpath(cwd)):
        return git_state
    return dict(git_state, worktree=None)


def render(ctx, data, agents, git_state, limit):
    """All lines at the fullest fit whose widest line fits in limit cells.

    agents is a (readings, runways) pair.
    """
    readings, runways = agents
    lines = []
    for fit in fits(ctx.cfg["bar_width"]):
        lines = usage_rows(ctx, readings, runways, fit) + [identity_line(ctx, data, git_state, fit)]
        lines = [ln for ln in lines if ln]
        if not limit or max(map(visible_width, lines)) <= limit:
            break
    return lines
