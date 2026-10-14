"""Codex quota read offline from the newest local Codex session logs."""

import calendar
import json
import os
import re
import time
from itertools import islice

from shape import Reading, Window

TAIL_BYTES = 512 * 1024
MAX_TAIL_BYTES = 4 * 1024 * 1024
FILES_TO_CHECK = 3
CACHE_TTL = 10


def window_label(minutes):
    """A short name for a window width in minutes: 5h, 7d, 30d, 72h, or 45m."""
    if minutes and minutes % 1440 == 0:
        return "%dd" % (minutes // 1440)
    if minutes and minutes % 60 == 0:
        return "%dh" % (minutes // 60)
    return "%dm" % (minutes or 0)


def _desc(path, want_dirs):
    try:
        names = os.listdir(path)
    except OSError:
        return []
    keep = [n for n in names if os.path.isdir(os.path.join(path, n)) == want_dirs]
    return sorted(keep, reverse=True)


def _walk(path, depth):
    """Session log paths under path, newest first, descending year, month, and day folders."""
    if depth == 0:
        for name in _desc(path, False):
            if name.endswith(".jsonl"):
                yield os.path.join(path, name)
        return
    for name in _desc(path, True):
        yield from _walk(os.path.join(path, name), depth - 1)


def newest_logs(codex_home, limit=FILES_TO_CHECK):
    """Up to limit newest session log paths under codex_home/sessions."""
    return list(islice(_walk(os.path.join(codex_home, "sessions"), 3), limit))


def _tail_lines(path, size):
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            start = max(0, fh.tell() - size)
            fh.seek(start)
            text = fh.read().decode("utf-8", "ignore")
    except OSError:
        return [], False
    lines = text.splitlines()
    return (lines[1:] if start else lines), start == 0


def _epoch(stamp):
    try:
        return float(calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")))
    except (TypeError, ValueError):
        return None


def _limits_event(obj):
    payload = obj.get("payload") or {}
    limits = payload.get("rate_limits") if payload.get("type") == "token_count" else None
    if isinstance(limits, dict) and isinstance(limits.get("primary"), dict):
        return limits
    return None


def _event(line):
    if '"rate_limits"' not in line and '"turn_context"' not in line:
        return None
    try:
        return json.loads(line)
    except ValueError:
        return None


def _turn(obj):
    ctx = obj.get("payload") or {}
    return ctx.get("model"), ctx.get("effort") or ctx.get("reasoning_effort")


def parse_lines(lines):
    """(rate_limits, epoch, model, effort) from the newest matching events in lines.

    rate_limits is None when no token_count event with a primary window is present.
    """
    limits = stamp = model = effort = None
    for obj in filter(None, map(_event, reversed(lines))):
        if limits is None and _limits_event(obj):
            limits, stamp = _limits_event(obj), _epoch(obj.get("timestamp"))
        elif model is None and obj.get("type") == "turn_context":
            model, effort = _turn(obj)
        if limits is not None and model is not None:
            break
    return limits, stamp, model, effort


def windows_from(limits):
    """The primary and secondary windows of a Codex rate_limits object."""
    out = []
    for key in ("primary", "secondary"):
        win = limits.get(key)
        if isinstance(win, dict) and win.get("used_percent") is not None:
            minutes = win.get("window_minutes") or 0
            out.append(Window(window_label(minutes), win.get("used_percent"),
                              win.get("resets_at"), minutes * 60))
    return out


def _config_value(codex_home, key):
    try:
        with open(os.path.join(codex_home, "config.toml"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    hit = re.search(r'^\s*%s\s*=\s*"([^"]+)"' % re.escape(key), text, re.M)
    return hit.group(1) if hit else None


def _scan(path):
    size = TAIL_BYTES
    while True:
        lines, whole = _tail_lines(path, size)
        found = parse_lines(lines)
        if found[0] is not None or whole or size >= MAX_TAIL_BYTES:
            return found
        size *= 4


def read(codex_home):
    """The newest Codex quota reading from local logs, or None when no log holds one."""
    for path in newest_logs(codex_home):
        limits, stamp, model, effort = _scan(path)
        if limits is None:
            continue
        return Reading(
            agent="codex",
            model=model or _config_value(codex_home, "model") or "codex",
            effort=effort or _config_value(codex_home, "model_reasoning_effort"),
            windows=windows_from(limits),
            context=None, cost=None, spend=None, as_of=stamp,
        )
    return None


def _to_json(reading):
    if reading is None:
        return None
    return dict(reading._asdict(), windows=[list(w) for w in reading.windows])


def _from_json(obj):
    if not isinstance(obj, dict):
        return None
    try:
        return Reading(**dict(obj, windows=[Window(*w) for w in obj.get("windows") or []]))
    except TypeError:
        return None


def cached_read(codex_home, store, now):
    """read() cached in store["codex"] for CACHE_TTL seconds per codex_home. Returns (reading, changed)."""
    entry = store.get("codex")
    if _fresh(entry, codex_home, now):
        return _from_json(entry.get("reading")), False
    reading = read(codex_home)
    store["codex"] = {"ts": now, "home": codex_home, "reading": _to_json(reading)}
    return reading, True


def _fresh(entry, codex_home, now):
    if not isinstance(entry, dict) or entry.get("home") != codex_home:
        return False
    stamp = entry.get("ts")
    return isinstance(stamp, (int, float)) and 0 <= now - stamp < CACHE_TTL
