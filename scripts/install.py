#!/usr/bin/env python3
"""Install, refresh, and remove the paceline statusline.

Usage: install.py setup | refresh | uninstall

setup copies the paceline package to the config directory and points the
statusLine setting of the active Claude Code profile ($CLAUDE_CONFIG_DIR, else
~/.claude) at it. config.json keeps the previous statusLine block of each
profile, so uninstall can put it back. The package stays installed until the
last profile is uninstalled. refresh copies the package again
only when the plugin's copy differs, and prints nothing.
"""

import hashlib
import json
import os
import shutil
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(PLUGIN_ROOT, "paceline")
APP_DIR = "app"
ENTRY = "paceline.py"
PREVIOUS = "previous_status_lines"

sys.path.insert(0, SOURCE)

import paths as pl_paths


class SetupError(Exception):
    """A problem that stops setup or uninstall, with a message for the user."""


def tree_hash(folder):
    """A SHA-256 over the names and contents of the .py files in folder, or '' when absent."""
    digest = hashlib.sha256()
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".py"))
    except OSError:
        return ""
    for name in names:
        digest.update(name.encode())
        with open(os.path.join(folder, name), "rb") as fh:
            digest.update(fh.read())
    return digest.hexdigest()


def copy_app(source, dest):
    """Copy source to dest through a temporary folder, then swap it in with renames."""
    fresh, old = dest + ".new", dest + ".old"
    for leftover in (fresh, old):
        shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(source, fresh, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if os.path.isdir(dest):
        os.replace(dest, old)
    os.replace(fresh, dest)
    shutil.rmtree(old, ignore_errors=True)


def _read_json(path, missing):
    if not os.path.exists(path):
        return missing
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as err:
        raise SetupError("cannot read %s: %s" % (path, err))
    if not isinstance(data, dict):
        raise SetupError("%s does not hold a JSON object" % path)
    return data


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def status_command(python, entry):
    """The statusLine command: the quoted interpreter and the quoted entry script, with forward slashes."""
    return '"%s" "%s"' % (python.replace("\\", "/"), entry.replace("\\", "/"))


def is_paceline(block):
    """True when a statusLine block runs the installed paceline script."""
    command = (block or {}).get("command") or ""
    return isinstance(command, str) and ("%s/%s" % (APP_DIR, ENTRY)) in command.replace("\\", "/")


def _previous_map(cfg):
    """The profile-to-previous-statusLine map in cfg, created when absent or malformed."""
    if not isinstance(cfg.get(PREVIOUS), dict):
        cfg[PREVIOUS] = {}
    return cfg[PREVIOUS]


def _settings_path(where):
    return os.path.join(where.claude_dir, "settings.json")


def setup(where, python):
    """Copy the package, record the previous statusLine, and point statusLine at paceline."""
    settings_path = _settings_path(where)
    settings = _read_json(settings_path, {})
    cfg = _read_json(where.config_file, {})
    current = settings.get("statusLine")
    previous = _previous_map(cfg)
    if not is_paceline(current):
        previous[settings_path] = current
    dest = os.path.join(where.config_dir, APP_DIR)
    copy_app(SOURCE, dest)
    _write_json(where.config_file, cfg)
    if os.path.exists(settings_path):
        shutil.copy2(settings_path, settings_path + ".bak")
    settings["statusLine"] = {
        "type": "command",
        "command": status_command(python, os.path.join(dest, ENTRY)),
        "refreshInterval": 1,
    }
    _write_json(settings_path, settings)
    return [
        "installed: %s" % dest,
        "statusLine set in %s (previous file saved as settings.json.bak)" % settings_path,
        "restart Claude Code or start a new session to see paceline",
    ]


def refresh(where):
    """Copy the package again when the installed copy differs from the plugin's. Silent."""
    dest = os.path.join(where.config_dir, APP_DIR)
    if os.path.isdir(dest) and tree_hash(dest) != tree_hash(SOURCE):
        copy_app(SOURCE, dest)
    return []


def _restore(settings_path, previous):
    settings = _read_json(settings_path, {})
    if not is_paceline(settings.get("statusLine")):
        return "statusLine in %s does not point at paceline; left unchanged" % settings_path
    if isinstance(previous, dict):
        settings["statusLine"] = previous
        message = "previous statusLine restored in %s" % settings_path
    else:
        settings.pop("statusLine", None)
        message = "statusLine removed from %s" % settings_path
    _write_json(settings_path, settings)
    return message


def uninstall(where):
    """Put back the previous statusLine of the active profile.

    The paceline config directory is removed when no other profile still uses it.
    """
    settings_path = _settings_path(where)
    cfg = _read_json(where.config_file, {})
    previous = _previous_map(cfg)
    messages = [_restore(settings_path, previous.pop(settings_path, None))]
    if previous:
        _write_json(where.config_file, cfg)
        messages.append("kept %s for: %s" % (where.config_dir, ", ".join(sorted(previous))))
    else:
        shutil.rmtree(where.config_dir, ignore_errors=True)
        messages.append("removed %s" % where.config_dir)
    return messages


def run(action, env, python):
    """Run one action and return its messages. Raises SetupError for a bad action or a bad file."""
    where = pl_paths.resolve(env)
    if action == "setup":
        return setup(where, python)
    if action == "refresh":
        return refresh(where)
    if action == "uninstall":
        return uninstall(where)
    raise SetupError("usage: install.py setup | refresh | uninstall")


def main(argv):
    """Command-line entry. refresh never fails loudly; the other actions exit 1 with a message on error."""
    action = argv[1] if len(argv) > 1 else ""
    try:
        for message in run(action, os.environ, sys.executable):
            print(message)
    except (SetupError, OSError) as err:
        if action == "refresh":
            return 0
        print("error: %s" % err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
