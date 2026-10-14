"""User settings from config.json, merged over the defaults."""

from store import load as _load_json

DEFAULTS = {
    "theme": "auto",
    "quotes": False,
    "codex": True,
    "bar_width": 8,
    "countdown_min_load": 50,
    "runway_minutes": 10,
}
LIMITS = {
    "bar_width": (3, 20),
    "countdown_min_load": (0, 100),
    "runway_minutes": (2, 60),
}


def _valid(key, value):
    """True when value has the type of the default for key and lies inside its limits."""
    default = DEFAULTS[key]
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        low, high = LIMITS[key]
        return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    return isinstance(value, type(default))


def merge(raw):
    """The defaults with every valid key of raw applied. Invalid or unknown keys are ignored."""
    cfg = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in raw and _valid(key, raw[key]):
            cfg[key] = raw[key]
    return cfg


def load(path):
    """The merged settings from the config file at path."""
    return merge(_load_json(path))
