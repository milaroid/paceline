"""The palette for the auto theme: the profile's Claude Code theme, then hints about the terminal background."""

import json
import os
import subprocess
import sys

OS_FOLLOWERS = ("Apple_Terminal",)

OS_TTL = 30


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def claude_theme(claude_dir):
    """The Claude Code theme of the profile, with a custom theme resolved to its base preset."""
    value = _read_json(os.path.join(claude_dir, "settings.json")).get("theme")
    if not isinstance(value, str):
        return None
    if value.startswith("custom:"):
        slug = value.split(":", 1)[1]
        base = _read_json(os.path.join(claude_dir, "themes", slug + ".json")).get("base")
        return base if isinstance(base, str) else "dark"
    return value


def _mac_light():
    try:
        out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                             capture_output=True, text=True, timeout=1.0)
    except (OSError, subprocess.SubprocessError):
        return None
    return "dark" not in out.stdout.lower()


def colorfgbg_is_light(env):
    """True or False from a COLORFGBG value such as '15;0', or None when it is absent or unclear."""
    try:
        bg = int((env.get("COLORFGBG") or "").split(";")[-1])
    except ValueError:
        return None
    return bg in (7, 15)


def os_is_light():
    """True for a light macOS appearance, False for dark, None on other platforms."""
    return _mac_light() if sys.platform == "darwin" else None


def cached_os_is_light(store, now):
    """os_is_light() cached in store["appearance"] for OS_TTL seconds. Returns (value, changed)."""
    entry = store.get("appearance")
    if isinstance(entry, dict) and isinstance(entry.get("ts"), (int, float)) \
            and 0 <= now - entry["ts"] < OS_TTL:
        return entry.get("light"), False
    light = os_is_light()
    store["appearance"] = {"ts": now, "light": light}
    return light, True


def palette(claude_value, fallback_light):
    """The paceline palette for a Claude Code theme value.

    Light presets map to light and dark presets to dark. auto, an unknown value,
    or no value calls fallback_light, which returns True for a light background.
    """
    for name in ("light", "dark"):
        if claude_value and claude_value.startswith(name):
            return name
    return "light" if fallback_light() else "dark"


def background_is_light(env, os_light):
    """The best guess at a light terminal background when Claude Code's theme is auto.

    COLORFGBG wins when the terminal sets it. Apple Terminal follows the OS
    appearance, so os_light() answers there. Any other terminal counts as dark.
    """
    hint = colorfgbg_is_light(env)
    if hint is not None:
        return hint
    if env.get("TERM_PROGRAM") in OS_FOLLOWERS:
        return bool(os_light())
    return False
