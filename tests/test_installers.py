import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_windsurf_package_is_self_contained(self):
        package = ROOT / "skills" / "windsurf" / "ai-cross-mem"
        for name in (
            "__init__.py",
            "utils.py",
            "save_memory.py",
            "search_memory.py",
            "update_memory.py",
        ):
            self.assertTrue((package / "scripts" / name).is_file())
        instructions = (package / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(".codeium/windsurf/skills/ai-cross-mem/scripts", instructions)
        hook = json.loads((ROOT / "hooks" / "windsurf" / "hooks.json").read_text())
        self.assertIn("post_write_code", hook["hooks"])
        configured_hook = hook["hooks"]["post_write_code"][0]
        self.assertTrue(configured_hook["show_output"])
        self.assertIn("powershell", configured_hook)
        hook_script = (ROOT / "hooks" / "windsurf" / "check_memory.py").read_text()
        self.assertIn(".codeium", hook_script)
        self.assertNotIn(".claude", hook_script)

    def test_installers_accept_an_explicit_integration_choice(self):
        powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
        shell = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('[ValidateSet("Claude", "Windsurf", "Both")]', powershell)
        self.assertIn('integration="${1:-both}"', shell)
        self.assertIn('claude|windsurf|both', shell)

    def test_windsurf_hook_configuration_preserves_other_hooks(self):
        with tempfile.TemporaryDirectory() as home:
            config_dir = Path(home) / ".codeium" / "windsurf"
            config_dir.mkdir(parents=True)
            config = config_dir / "hooks.json"
            config.write_text(
                json.dumps({"hooks": {"post_write_code": [
                    {"command": "python user_hook.py"}
                ]}}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["USERPROFILE"] = home
            env["HOME"] = home
            subprocess.run(
                [os.environ.get("PYTHON", "python"), str(ROOT / "hooks" / "windsurf" / "configure.py")],
                cwd=ROOT,
                env=env,
                check=True,
            )
            result = json.loads(config.read_text(encoding="utf-8"))
            commands = [
                entry["command"]
                for entry in result["hooks"]["post_write_code"]
            ]
            self.assertIn("python user_hook.py", commands)
            self.assertTrue(any("ai-cross-mem" in command for command in commands))

    def test_windsurf_reminder_hook_emits_once_per_interval(self):
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env["USERPROFILE"] = home
            env["HOME"] = home
            hook = str(ROOT / "hooks" / "windsurf" / "check_memory.py")
            payload = json.dumps({
                "agent_action_name": "post_write_code",
                "tool_info": {"file_path": "README.md"},
            })
            first = subprocess.run(
                [sys.executable, hook], input=payload, text=True, capture_output=True,
                env=env, check=True,
            )
            second = subprocess.run(
                [sys.executable, hook], input=payload, text=True, capture_output=True,
                env=env, check=True,
            )
            self.assertIn("ai-cross-mem", first.stdout)
            self.assertEqual(second.stdout, "")

    def test_macos_installer_has_valid_bash_syntax(self):
        msys_bash = Path(r"C:\msys64\usr\bin\bash.exe")
        bash = str(msys_bash) if os.name == "nt" and msys_bash.exists() else shutil.which("bash")
        if not bash or not Path(bash).exists():
            self.skipTest("Bash is not installed; run this test on macOS")
        for script in ("install.sh", "uninstall.sh"):
            script_path = str(ROOT / script)
            if os.name == "nt" and str(bash).lower().startswith(r"c:\msys64"):
                script_path = subprocess.check_output(
                    [r"C:\msys64\usr\bin\cygpath.exe", "-u", script_path], text=True
                ).strip()
            subprocess.run([str(bash), "-n", script_path], check=True)

    @unittest.skipUnless(platform.system() == "Darwin", "macOS integration test")
    def test_macos_installer_installs_into_isolated_home_idempotently(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            claude = home_path / ".claude"
            claude.mkdir()
            (claude / "AGENTS.md").write_text("# User rules\n", encoding="utf-8")
            (claude / "CLAUDE.md").write_text("# User Claude config\n", encoding="utf-8")
            settings = claude / "settings.json"
            settings.write_text('{"customSetting": true}\n', encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = home
            command = ["bash", str(ROOT / "install.sh")]
            subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)

            skill = claude / "skills" / "ai-cross-mem"
            self.assertTrue((home_path / "Documents" / "ai-cross-mem").is_dir())
            self.assertTrue((skill / "scripts" / "save_memory.py").is_file())
            self.assertTrue((skill / "hooks" / "check_memory.py").is_file())
            self.assertFalse(list(skill.rglob("__pycache__")))
            self.assertFalse(list(skill.rglob("*.pyc")))
            self.assertFalse(list(skill.rglob("__pycache__")))
            self.assertFalse(list(skill.rglob("*.pyc")))
            self.assertIn("User rules", (claude / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("ai-cross-mem", (claude / "AGENTS.md").read_text(encoding="utf-8"))
            installed_settings = json.loads(settings.read_text(encoding="utf-8"))
            self.assertTrue(installed_settings["customSetting"])
            self.assertIn("PostToolUse", installed_settings["hooks"])
            self.assertTrue(list(claude.glob("AGENTS.md.backup-*")))

            subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            self.assertFalse((skill / "ai-cross-mem").exists())
            settings_after_second_run = json.loads(settings.read_text(encoding="utf-8"))
            hook_commands = [
                hook["hooks"][0]["command"]
                for hook in settings_after_second_run["hooks"]["PostToolUse"]
            ]
            self.assertEqual(sum("check_memory.py" in command for command in hook_commands), 1)

    def test_windows_installer_runs_idempotently_in_windows_powershell(self):
        powershell = os.environ.get("WINDIR", r"C:\Windows") + (
            r"\System32\WindowsPowerShell\v1.0\powershell.exe"
        )
        if not Path(powershell).exists():
            self.skipTest("Windows PowerShell 5.1 is unavailable")

        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env["USERPROFILE"] = home
            env["HOME"] = home
            env["LOCALAPPDATA"] = str(Path(home) / "AppData" / "Local")
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "install.ps1"),
            ]
            subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            claude = Path(home) / ".claude"
            skill = claude / "skills" / "ai-cross-mem"
            self.assertTrue((skill / "scripts" / "save_memory.py").is_file())
            self.assertTrue((skill / "hooks" / "check_memory.py").is_file())
            self.assertTrue((Path(home) / "Documents" / "ai-cross-mem").is_dir())
            self.assertTrue(
                (Path(env["LOCALAPPDATA"]) / "ai-cross-mem" / "install-manifest.json").is_file()
            )

            subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            self.assertFalse((skill / "ai-cross-mem").exists())
            self.assertIn("ai-cross-mem", (claude / "AGENTS.md").read_text(encoding="utf-8"))

    def test_windows_windsurf_only_does_not_create_claude_files(self):
        powershell = os.environ.get("WINDIR", r"C:\Windows") + (
            r"\System32\WindowsPowerShell\v1.0\powershell.exe"
        )
        if not Path(powershell).exists():
            self.skipTest("Windows PowerShell 5.1 is unavailable")
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env["USERPROFILE"] = home
            env["HOME"] = home
            env["LOCALAPPDATA"] = str(Path(home) / "AppData" / "Local")
            stale_cache = (
                Path(home) / ".codeium" / "windsurf" / "skills" /
                "ai-cross-mem" / "scripts" / "__pycache__"
            )
            stale_cache.mkdir(parents=True)
            subprocess.run(
                [
                    powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(ROOT / "install.ps1"), "-Integration", "Windsurf",
                ],
                cwd=ROOT, env=env, check=True, capture_output=True, text=True,
            )
            windsurf = Path(home) / ".codeium" / "windsurf"
            self.assertTrue(
                (windsurf / "skills" / "ai-cross-mem" / "scripts" / "save_memory.py").is_file()
            )
            self.assertTrue((windsurf / "hooks.json").is_file())
            self.assertFalse(list((windsurf / "skills" / "ai-cross-mem").rglob("__pycache__")))
            self.assertFalse(list((windsurf / "skills" / "ai-cross-mem").rglob("*.pyc")))
            self.assertFalse((Path(home) / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
