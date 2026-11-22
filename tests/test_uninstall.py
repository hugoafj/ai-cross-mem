import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

import uninstall


ROOT = Path(__file__).resolve().parents[1]
BEGIN_MARKER = "<!-- BEGIN AI-CROSS-MEM MANAGED BLOCK -->"


class UninstallerTests(unittest.TestCase):
    def test_uninstaller_preserves_user_data_and_removes_only_registered_changes(self):
        system = platform.system()
        if system not in ("Windows", "Darwin"):
            self.skipTest("Windows/macOS integration test")

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            claude = home / ".claude"
            claude.mkdir()
            agents = claude / "AGENTS.md"
            agents.write_text("# User's existing Claude rules\n", encoding="utf-8")
            claude_md = claude / "CLAUDE.md"
            claude_md.write_text("# User Claude config\n", encoding="utf-8")
            preexisting_skill_file = (
                claude / "skills" / "ai-cross-mem" / "scripts" / "utils.py"
            )
            preexisting_skill_file.parent.mkdir(parents=True)
            preexisting_skill_file.write_text("pre-install custom content", encoding="utf-8")
            settings = claude / "settings.json"
            other_hook = {
                "hooks": [
                    {"type": "command", "command": "python other_tool.py"}
                ]
            }
            settings.write_text(
                json.dumps({"customSetting": "keep", "hooks": {"PostToolUse": [other_hook]}}),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            if system == "Windows":
                env["LOCALAPPDATA"] = str(home / "AppData" / "Local")
                powershell = os.environ.get("WINDIR", r"C:\Windows") + (
                    r"\System32\WindowsPowerShell\v1.0\powershell.exe"
                )
                install = [
                    powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "install.ps1"),
                ]
                uninstall = [
                    powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "uninstall.ps1"),
                ]
            else:
                install = ["bash", str(ROOT / "install.sh")]
                uninstall = ["bash", str(ROOT / "uninstall.sh")]

            subprocess.run(install, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            skill = claude / "skills" / "ai-cross-mem"
            personal_file = skill / "my-notes.md"
            personal_file.write_text("keep this custom file", encoding="utf-8")
            modified_app_file = skill / "scripts" / "search_memory.py"
            modified_app_file.write_text("user-edited app file", encoding="utf-8")
            agents.write_text(
                agents.read_text(encoding="utf-8") + "\n# My newer unrelated rule\n",
                encoding="utf-8",
            )
            memories = home / "Documents" / "ai-cross-mem" / "demo" / "saved.md"
            memories.parent.mkdir(parents=True)
            memories.write_text("keep this memory", encoding="utf-8")

            subprocess.run(uninstall, cwd=ROOT, env=env, check=True, capture_output=True, text=True)

            self.assertFalse((skill / "scripts" / "save_memory.py").exists())
            self.assertTrue(personal_file.is_file())
            self.assertEqual(personal_file.read_text(encoding="utf-8"), "keep this custom file")
            self.assertEqual(
                modified_app_file.read_text(encoding="utf-8"), "user-edited app file"
            )
            self.assertEqual(
                preexisting_skill_file.read_text(encoding="utf-8"),
                "pre-install custom content",
            )
            self.assertIn("User's existing Claude rules", agents.read_text(encoding="utf-8"))
            self.assertIn("My newer unrelated rule", agents.read_text(encoding="utf-8"))
            self.assertNotIn(BEGIN_MARKER, agents.read_text(encoding="utf-8"))
            self.assertEqual(claude_md.read_text(encoding="utf-8"), "# User Claude config\n")
            self.assertEqual(memories.read_text(encoding="utf-8"), "keep this memory")

            after_settings = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(after_settings["customSetting"], "keep")
            self.assertEqual(after_settings["hooks"]["PostToolUse"], [other_hook])

    def test_manifest_does_not_remove_a_preexisting_ai_cross_mem_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            hook = {
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "~/.claude/skills/ai-cross-mem/hooks/check_memory.py"',
                    }
                ]
            }
            settings.write_text(
                json.dumps({"hooks": {"PostToolUse": [hook]}}), encoding="utf-8"
            )

            uninstall.remove_hooks(settings, [], allow_legacy=False)

            result = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(result["hooks"]["PostToolUse"], [hook])

    def test_removing_recorded_hook_preserves_other_hooks_in_the_same_group(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            app_hook = {
                "type": "command",
                "command": 'python "~/.claude/skills/ai-cross-mem/hooks/check_memory.py"',
            }
            other_hook = {"type": "command", "command": "python other_tool.py"}
            group = {"hooks": [app_hook, other_hook]}
            settings.write_text(
                json.dumps({"hooks": {"PostToolUse": [group]}}), encoding="utf-8"
            )

            uninstall.remove_hooks(
                settings,
                [{"event": "PostToolUse", "group": group}],
            )

            result = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(
                result["hooks"]["PostToolUse"][0]["hooks"], [other_hook]
            )

    @unittest.skipUnless(platform.system() in ("Windows", "Darwin"), "Windows/macOS integration test")
    def test_uninstaller_removes_global_files_created_by_installer_but_keeps_memories(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            if platform.system() == "Windows":
                env["LOCALAPPDATA"] = str(home / "AppData" / "Local")
                powershell = os.environ.get("WINDIR", r"C:\Windows") + (
                    r"\System32\WindowsPowerShell\v1.0\powershell.exe"
                )
                install = [
                    powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "install.ps1"),
                ]
                uninstall_command = [
                    powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "uninstall.ps1"),
                ]
            else:
                install = ["bash", str(ROOT / "install.sh")]
                uninstall_command = ["bash", str(ROOT / "uninstall.sh")]

            subprocess.run(install, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            claude = home / ".claude"
            self.assertTrue((claude / "AGENTS.md").is_file())
            self.assertTrue((claude / "CLAUDE.md").is_file())
            memories = home / "Documents" / "ai-cross-mem"
            memories.mkdir(parents=True, exist_ok=True)
            memory = memories / "must-survive.md"
            memory.write_text("keep me", encoding="utf-8")

            subprocess.run(
                uninstall_command, cwd=ROOT, env=env, check=True, capture_output=True, text=True
            )

            self.assertFalse((claude / "AGENTS.md").exists())
            self.assertFalse((claude / "CLAUDE.md").exists())
            self.assertFalse((claude / "settings.json").exists())
            self.assertTrue(memory.is_file())
            self.assertEqual(memory.read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
