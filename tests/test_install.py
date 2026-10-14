"""Tests for setup, refresh, and uninstall."""

import json
import os
import tempfile
import unittest

import helpers
import install
import paths


class InstallTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.env = {"XDG_CONFIG_HOME": os.path.join(tmp, "cfg"),
                    "CLAUDE_CONFIG_DIR": os.path.join(tmp, "claude")}
        if os.name == "nt":
            self.env["APPDATA"] = os.path.join(tmp, "appdata")
        self.where = paths.resolve(self.env)
        self.settings = os.path.join(self.where.claude_dir, "settings.json")
        os.makedirs(self.where.claude_dir)

    def write_settings(self, data):
        with open(self.settings, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def read_settings(self):
        with open(self.settings, encoding="utf-8") as fh:
            return json.load(fh)

    def test_setup_and_uninstall_restore_previous(self):
        previous = {"type": "command", "command": "bash ~/old.sh"}
        self.write_settings({"model": "opus", "statusLine": previous})
        install.run("setup", self.env, "/usr/bin/python3")
        settings = self.read_settings()
        self.assertTrue(install.is_paceline(settings["statusLine"]))
        self.assertEqual(settings["model"], "opus")
        self.assertTrue(os.path.isfile(os.path.join(self.where.config_dir, "app", "paceline.py")))
        install.run("setup", self.env, "/usr/bin/python3")
        install.run("uninstall", self.env, "/usr/bin/python3")
        self.assertEqual(self.read_settings()["statusLine"], previous)
        self.assertFalse(os.path.exists(self.where.config_dir))

    def test_uninstall_without_previous_removes_key(self):
        install.run("setup", self.env, "/usr/bin/python3")
        install.run("uninstall", self.env, "/usr/bin/python3")
        self.assertNotIn("statusLine", self.read_settings())

    def test_uninstall_leaves_foreign_statusline(self):
        foreign = {"type": "command", "command": "other"}
        self.write_settings({"statusLine": foreign})
        install.run("uninstall", self.env, "/usr/bin/python3")
        self.assertEqual(self.read_settings()["statusLine"], foreign)

    def test_refresh_copies_only_on_change(self):
        self.assertEqual(install.run("refresh", self.env, "py"), [])
        self.assertFalse(os.path.exists(self.where.config_dir))
        install.run("setup", self.env, "/usr/bin/python3")
        target = os.path.join(self.where.config_dir, "app", "pace.py")
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("\n")
        install.run("refresh", self.env, "py")
        self.assertEqual(install.tree_hash(os.path.dirname(target)), install.tree_hash(install.SOURCE))

    def test_two_profiles(self):
        piko = dict(self.env, CLAUDE_CONFIG_DIR=os.path.join(os.path.dirname(self.where.claude_dir), "piko"))
        piko_settings = os.path.join(piko["CLAUDE_CONFIG_DIR"], "settings.json")
        os.makedirs(piko["CLAUDE_CONFIG_DIR"])
        with open(piko_settings, "w", encoding="utf-8") as fh:
            json.dump({"statusLine": {"type": "command", "command": "piko-old"}}, fh)
        self.write_settings({"statusLine": {"type": "command", "command": "claude-old"}})
        install.run("setup", self.env, "py")
        install.run("setup", piko, "py")
        install.run("uninstall", self.env, "py")
        self.assertEqual(self.read_settings()["statusLine"]["command"], "claude-old")
        self.assertTrue(os.path.isdir(os.path.join(self.where.config_dir, "app")))
        install.run("uninstall", piko, "py")
        with open(piko_settings, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["statusLine"]["command"], "piko-old")
        self.assertFalse(os.path.exists(self.where.config_dir))

    def test_bad_settings_stop_setup(self):
        with open(self.settings, "w", encoding="utf-8") as fh:
            fh.write("{bad")
        with self.assertRaises(install.SetupError):
            install.run("setup", self.env, "/usr/bin/python3")
        self.assertFalse(os.path.exists(self.where.config_dir))

    def test_unknown_action(self):
        with self.assertRaises(install.SetupError):
            install.run("dance", self.env, "py")

    def test_command_uses_forward_slashes(self):
        cmd = install.status_command("C:\\Python\\python.exe", "C:\\Users\\a\\app\\paceline.py")
        self.assertEqual(cmd, '"C:/Python/python.exe" "C:/Users/a/app/paceline.py"')
        self.assertTrue(install.is_paceline({"command": cmd}))


if __name__ == "__main__":
    unittest.main()
