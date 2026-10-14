"""Filesystem locations that paceline reads and writes."""

import os
from collections import namedtuple

Paths = namedtuple("Paths", "config_dir config_file state_file git_cache codex_home claude_dir")


def config_dir(env=None):
    """The paceline config directory: %APPDATA%\\paceline on Windows, else $XDG_CONFIG_HOME/paceline or ~/.config/paceline."""
    env = os.environ if env is None else env
    if os.name == "nt" and env.get("APPDATA"):
        return os.path.join(env["APPDATA"], "paceline")
    base = env.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "paceline")


def resolve(env=None):
    """All paths paceline uses, built from the environment.

    CODEX_HOME and CLAUDE_CONFIG_DIR override the default ~/.codex and ~/.claude.
    """
    env = os.environ if env is None else env
    home = os.path.expanduser("~")
    cdir = config_dir(env)
    return Paths(
        config_dir=cdir,
        config_file=os.path.join(cdir, "config.json"),
        state_file=os.path.join(cdir, "state.json"),
        git_cache=os.path.join(cdir, "gitcache.json"),
        codex_home=os.path.expanduser(env.get("CODEX_HOME") or os.path.join(home, ".codex")),
        claude_dir=os.path.expanduser(env.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude")),
    )
