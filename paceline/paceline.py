#!/usr/bin/env python3
"""paceline: a Claude Code statusline that shows where your usage limits will land.

Reads the statusLine JSON on stdin and writes one usage row per agent, then the
identity line. Standard library only.
"""

import json
import os
import sys
import time

import codex
import appearance
import config
import git
import layout
import pace
import paths
import quotes
import shape
import store
import theme

WIDTH_MARGIN = 4
MIN_WIDTH = 40


def width_limit(env):
    """Usable cells per line from the COLUMNS value Claude Code sets, or None when unset."""
    try:
        return max(MIN_WIDTH, int(env.get("COLUMNS", "")) - WIDTH_MARGIN)
    except ValueError:
        return None


def _readings(data, where, cfg, state, now):
    """The Claude and Codex readings, the runway map, and whether state changed."""
    claude = shape.from_claude(data, where.claude_dir)
    horizon = cfg["runway_minutes"] * 60
    claude_runways, changed = pace.update_runways(state, claude, now, horizon)
    other = None
    if cfg["codex"]:
        other, fetched = codex.cached_read(where.codex_home, state, now)
        changed = changed or fetched
    return [claude, other], {"claude": claude_runways}, changed


def _theme_name(cfg, where, env, state, now):
    """The palette name and whether state changed. auto follows the profile's Claude Code theme."""
    if cfg["theme"] != "auto":
        return cfg["theme"], False
    looked = []

    def os_light():
        light, changed = appearance.cached_os_is_light(state, now)
        looked.append(changed)
        return light
    name = appearance.palette(appearance.claude_theme(where.claude_dir),
                              lambda: appearance.background_is_light(env, os_light))
    return name, any(looked)


def build(data, env, now):
    """The statusline lines for one stdin JSON payload."""
    where = paths.resolve(env)
    cfg = config.load(where.config_file)
    state = store.load(where.state_file)
    readings, runways, changed = _readings(data, where, cfg, state, now)
    name, looked = _theme_name(cfg, where, env, state, now)
    if changed or looked:
        store.save(where.state_file, state)
    workspace = data.get("workspace") or {}
    cwd = data.get("cwd") or workspace.get("current_dir")
    git_state = git.info(cwd, workspace.get("git_worktree"), where.git_cache, now)
    ctx = layout.Context(theme.get(name), cfg, now)
    limit = width_limit(env)
    lines = layout.render(ctx, data, (readings, runways), git_state, limit)
    quote = _quote(ctx, readings[0], limit) if cfg["quotes"] else None
    return lines + [quote] if quote else lines


def _quote(ctx, claude, limit):
    five = next((w for w in claude.windows if w.label == "5h"), None)
    quote = quotes.line(ctx.theme, five, ctx.now, theme.load_color)
    if quote and limit and layout.visible_width(quote) > limit:
        return None
    return quote


def main():
    """Read stdin, write the lines. Any error prints nothing, so the prompt never breaks.

    Both streams use UTF-8, so the glyphs survive a Windows code page.
    """
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if isinstance(data, dict):
        sys.stdout.write("\n".join(build(data, os.environ, time.time())))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
