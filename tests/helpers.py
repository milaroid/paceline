"""Shared test setup: import paths and fixture builders."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "paceline"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

NOW = 1_800_000_000.0


def claude_payload(**extra):
    """A Claude Code statusLine payload with a model, context, and the given extra keys."""
    data = {
        "cwd": "/nonexistent/project",
        "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
        "context_window": {"used_percentage": 41},
        "effort": {"level": "high"},
    }
    data.update(extra)
    return data


def subscriber_limits(five=63.0, week=76.0):
    """rate_limits for a subscriber 3 hours into the 5-hour window and 5.2 days into the week."""
    return {
        "five_hour": {"used_percentage": five, "resets_at": NOW + 2 * 3600},
        "seven_day": {"used_percentage": week, "resets_at": NOW + int(1.8 * 86400)},
    }


def codex_line(used, resets_at, minutes=10080, stamp="2027-01-15T08:00:00.000Z"):
    """One token_count line in the Codex session log format."""
    return json.dumps({
        "timestamp": stamp, "type": "event_msg",
        "payload": {"type": "token_count", "info": {},
                    "rate_limits": {"limit_id": "codex",
                                    "primary": {"used_percent": used, "window_minutes": minutes,
                                                "resets_at": resets_at},
                                    "secondary": None}},
    })


def turn_line(model="gpt-6-astra", effort="medium"):
    """One turn_context line in the Codex session log format."""
    return json.dumps({"timestamp": "2027-01-15T07:59:00.000Z", "type": "turn_context",
                       "payload": {"model": model, "effort": effort}})


def write_log(codex_home, day, name, lines):
    """Write a session log under codex_home/sessions/<day>/<name>."""
    folder = os.path.join(codex_home, "sessions", *day.split("/"))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
