import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import update
from _support import run_checked


ROOT = Path(__file__).resolve().parents[1]


def make_update_source(destination, legacy_manifest):
    destination = Path(destination)
    for name in ("config", "hooks", "skills"):
        shutil.copytree(ROOT / name, destination / name)
    for name in ("install.ps1", "install.sh", "install_state.py"):
        shutil.copy2(ROOT / name, destination / name)
    (destination / "legacy-files.json").write_text(
        json.dumps({"version": 1, "files": legacy_manifest}), encoding="utf-8"
    )
    return destination


class UpdateTests(unittest.TestCase):
    def test_update_selection_matches_manifest_integrations(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(
                json.dumps({"items": {
                    "C:/Users/example/.codeium/windsurf/hooks.json": {},
                    "C:/Users/example/.codeium/windsurf/skills/ai-cross-mem/SKILL.md": {},
                }}),
                encoding="utf-8",
            )
            with mock.patch.object(update, "install_manifest_path", return_value=manifest):
                self.assertEqual(update._installed_integrations(), "windsurf")

    def test_legacy_manifest_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "legacy-files.json").write_text(
                json.dumps({
                    "version": 1,
                    "files": [{"target": "claude_skill", "path": "../outside.txt"}],
                }),
                encoding="utf-8",
            )
            with self.assertRaises(update.UpdateError):
                update._load_legacy_files(source)

    @unittest.skipUnless(platform.system() in ("Windows", "Darwin"), "Windows/macOS integration test")
    def test_local_update_reinstalls_and_removes_only_manifest_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            home = base / "home"
            home.mkdir()
            source = make_update_source(
                base / "release",
                [{"target": "claude_skill", "path": "scripts/obsolete.py"}],
            )
            obsolete = home / ".claude" / "skills" / "ai-cross-mem" / "scripts" / "obsolete.py"
            obsolete.parent.mkdir(parents=True)
            obsolete.write_text("deprecated", encoding="utf-8")
            memory = home / "Documents" / "ai-cross-mem" / "demo" / "saved.md"
            memory.parent.mkdir(parents=True)
            memory.write_text("keep this memory", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            env["LOCALAPPDATA"] = str(home / "AppData" / "Local")
            command = [
                sys.executable,
                str(ROOT / "update.py"),
                "--source",
                str(source),
                "--yes",
            ]
            run_checked(command, cwd=ROOT, env=env)

            self.assertFalse(obsolete.exists())
            self.assertTrue(memory.is_file())
            self.assertEqual(memory.read_text(encoding="utf-8"), "keep this memory")
            self.assertTrue(
                (home / ".claude" / "skills" / "ai-cross-mem" / "scripts" / "save_memory.py").is_file()
            )


if __name__ == "__main__":
    unittest.main()
