"""One internal shape for every agent reading."""

import json
import os
import re
from collections import namedtuple

FIVE_HOUR = 5 * 3600
SEVEN_DAY = 7 * 86400
PERIODS = {"daily": 86400, "weekly": SEVEN_DAY, "monthly": 30 * 86400}

Window = namedtuple("Window", "label used resets_at seconds")
Spend = namedtuple("Spend", "used resets_at seconds used_usd limit_usd")
Reading = namedtuple("Reading", "agent model effort windows context cost spend as_of")


def _load_settings(claude_dir):
    try:
        with open(os.path.join(claude_dir, "settings.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _settings_effort(claude_dir, model_id):
    """Effort from settings.json in claude_dir: modelSettings.<model>.effortLevel, else effortLevel."""
    cfg = _load_settings(claude_dir)
    base = re.sub(r"\[[^\]]*\]$", "", model_id or "")
    per_model = (cfg.get("modelSettings") or {}).get(base) or {}
    return per_model.get("effortLevel") or cfg.get("effortLevel")


def _claude_effort(data, claude_dir):
    model = data.get("model") or {}
    effort = (data.get("effort") or {}).get("level") or _settings_effort(claude_dir, model.get("id"))
    if data.get("fast_mode"):
        return (effort + " ⚡") if effort else "⚡"
    return effort


def _claude_windows(limits):
    out = []
    for key, label, seconds in (("five_hour", "5h", FIVE_HOUR), ("seven_day", "7d", SEVEN_DAY)):
        obj = limits.get(key)
        if isinstance(obj, dict):
            out.append(Window(label, obj.get("used_percentage"), obj.get("resets_at"), seconds))
    return out


def _claude_spend(limits):
    obj = limits.get("spend_limit")
    if not isinstance(obj, dict) or obj.get("used_percentage") is None:
        return None
    seconds = PERIODS.get(obj.get("period"), PERIODS["monthly"])
    return Spend(obj.get("used_percentage"), obj.get("resets_at"), seconds,
                 obj.get("used_usd"), obj.get("limit_usd"))


def _claude_cost(data, windows, spend):
    """Session cost in USD for API-key users: no rate-limit windows, no spend limit, above zero."""
    if windows or spend:
        return None
    cost = (data.get("cost") or {}).get("total_cost_usd")
    return cost if isinstance(cost, (int, float)) and cost > 0 else None


def from_claude(data, claude_dir):
    """The Claude Code statusLine stdin JSON as a Reading."""
    limits = data.get("rate_limits") or {}
    windows = _claude_windows(limits)
    spend = _claude_spend(limits)
    return Reading(
        agent="claude",
        model=(data.get("model") or {}).get("display_name") or "claude",
        effort=_claude_effort(data, claude_dir),
        windows=windows,
        context=(data.get("context_window") or {}).get("used_percentage"),
        cost=_claude_cost(data, windows, spend),
        spend=spend,
        as_of=None,
    )
