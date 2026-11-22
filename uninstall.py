#!/usr/bin/env python3
"""Safely remove ai-cross-mem files registered by its installer."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys

import install_state


BEGIN_MARKER = "<!-- BEGIN AI-CROSS-MEM MANAGED BLOCK -->"
END_MARKER = "<!-- END AI-CROSS-MEM MANAGED BLOCK -->"
LEGACY_MARKER = "ai-cross-mem: Shared Memory System"
LEGACY_END = "# End of ai-cross-mem"


def log(message):
    print(message)


def file_hash(path):
    return install_state.sha256_file(path)


def allowed_path(path):
    candidate = Path(path).resolve()
    for root in install_state.managed_roots():
        root = root.resolve()
        try:
            if os.path.commonpath((str(root), str(candidate))) == str(root):
                return True
        except ValueError:
            continue
    return False


def remove_managed_text(text):
    if BEGIN_MARKER in text or END_MARKER in text:
        if text.count(BEGIN_MARKER) != 1 or text.count(END_MARKER) != 1:
            return text, False
        start = text.index(BEGIN_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        if end < len(text) and text[end:end + 2] == "\r\n":
            end += 2
        elif end < len(text) and text[end] == "\n":
            end += 1
        return text[:start] + text[end:], True

    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if LEGACY_MARKER in line]
    ends = [i for i, line in enumerate(lines) if LEGACY_END in line]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        return text, False
    return "".join(lines[:starts[0]] + lines[ends[0] + 1:]), True


def restore_or_remove_item(path, item, state_dir):
    path = Path(path)
    if not allowed_path(path):
        log("Skipped path outside ai-cross-mem install locations: {}".format(path))
        return False
    if not path.is_file() or path.is_symlink():
        return False
    if file_hash(path) != item.get("installed_sha256"):
        log("Preserved modified file for manual review: {}".format(path))
        return True
    backup = item.get("original_backup")
    if backup:
        backup_path = Path(backup).resolve()
        backups_root = (state_dir / "backups").resolve()
        if os.path.commonpath((str(backups_root), str(backup_path))) != str(backups_root):
            log("Skipped invalid backup path: {}".format(backup_path))
            return True
        if not backup_path.is_file():
            log("Could not restore missing backup for: {}".format(path))
            return True
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(backup_path), str(path))
        log("Restored pre-install file: {}".format(path))
    else:
        path.unlink()
        log("Removed installed file: {}".format(path))
    return False


def remove_config_file(path, item):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return
    with open(str(path), "r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    installed_hash = item.get("installed_sha256") if item else None
    if installed_hash and file_hash(path) == installed_hash:
        backup = item.get("original_backup")
        if backup:
            backup_path = Path(backup).resolve()
            backups_root = (install_state.state_directory() / "backups").resolve()
            if os.path.commonpath((str(backups_root), str(backup_path))) != str(backups_root):
                log("Skipped invalid configuration backup: {}".format(backup_path))
                return
            if not backup_path.is_file():
                log("Could not restore missing configuration backup: {}".format(backup_path))
                return
            shutil.copy2(backup, str(path))
            log("Restored pre-install configuration: {}".format(path))
        else:
            path.unlink()
            log("Removed configuration created by ai-cross-mem: {}".format(path))
        return

    cleaned, removed = remove_managed_text(text)
    if not removed:
        log("Preserved configuration; no unique ai-cross-mem block found: {}".format(path))
        return
    if not cleaned.strip() and item and item.get("original_backup") is None:
        path.unlink()
        log("Removed now-empty configuration created by ai-cross-mem: {}".format(path))
    else:
        with open(str(path), "w", encoding="utf-8", newline="") as stream:
            stream.write(cleaned)
        log("Removed only the ai-cross-mem section from: {}".format(path))


def remove_untracked_legacy_config(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return
    with open(str(path), "r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    cleaned, removed = remove_managed_text(text)
    if removed:
        with open(str(path), "w", encoding="utf-8", newline="") as stream:
            stream.write(cleaned)
        log("Removed recognizable legacy ai-cross-mem section from: {}".format(path))


def strip_empty_directories(root):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        return
    for directory, subdirectories, _ in os.walk(str(root), topdown=False):
        current = Path(directory)
        try:
            current.rmdir()
        except OSError:
            pass


def source_files(project_root):
    result = {}
    mappings = (
        (project_root / "skills" / "claude" / "ai-cross-mem",
         install_state.home_directory() / ".claude" / "skills" / "ai-cross-mem"),
        (project_root / "skills" / "windsurf" / "ai-cross-mem",
         install_state.home_directory() / ".codeium" / "windsurf" / "skills" / "ai-cross-mem"),
    )
    for source_root, target_root in mappings:
        if source_root.is_dir():
            for source in source_root.rglob("*"):
                if source.is_file() and not source.is_symlink():
                    result[target_root / source.relative_to(source_root)] = source
    hook = project_root / "hooks" / "scripts" / "check_memory.py"
    if hook.is_file():
        result[
            install_state.home_directory() / ".claude" / "skills" / "ai-cross-mem" /
            "hooks" / "check_memory.py"
        ] = hook
    return result


def remove_legacy_skill_files(project_root):
    for target, source in source_files(project_root).items():
        if target.is_file() and not target.is_symlink():
            if file_hash(target) == file_hash(source):
                target.unlink()
                log("Removed recognized ai-cross-mem file: {}".format(target))
            else:
                log("Preserved untracked or modified file: {}".format(target))


def remove_hooks(settings_path, recorded_hooks, allow_legacy=False):
    settings_path = Path(settings_path)
    if not settings_path.is_file() or settings_path.is_symlink():
        return
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        log("Preserved unreadable Claude settings file {}: {}".format(settings_path, error))
        return
    if not isinstance(settings, dict):
        log("Preserved Claude settings file with unexpected structure: {}".format(settings_path))
        return

    hooks = settings.get("hooks")
    removed_count = 0
    recorded_commands = set()
    for record in recorded_hooks:
        group = record.get("group", {})
        group_hooks = group.get("hooks", []) if isinstance(group, dict) else []
        for hook in group_hooks:
            if (
                isinstance(hook, dict)
                and isinstance(hook.get("command"), str)
                and "ai-cross-mem" in hook["command"]
                and "check_memory.py" in hook["command"]
            ):
                recorded_commands.add(hook["command"])
    if isinstance(hooks, dict):
        for event, groups in list(hooks.items()):
            if not isinstance(groups, list):
                continue
            new_groups = []
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                    new_groups.append(group)
                    continue
                new_hook_list = []
                for hook in group["hooks"]:
                    command = hook.get("command", "") if isinstance(hook, dict) else ""
                    legacy_match = "ai-cross-mem" in command and "check_memory.py" in command
                    if command in recorded_commands:
                        removed_count += 1
                    elif allow_legacy and legacy_match:
                        removed_count += 1
                    else:
                        new_hook_list.append(hook)
                if new_hook_list:
                    changed_group = dict(group)
                    changed_group["hooks"] = new_hook_list
                    new_groups.append(changed_group)
            if new_groups:
                hooks[event] = new_groups
            else:
                hooks.pop(event, None)
        if not hooks:
            settings.pop("hooks", None)

    if removed_count:
        if settings:
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        else:
            settings_path.unlink()
        log("Removed {} ai-cross-mem hook(s) from {}".format(removed_count, settings_path))


def memory_directory():
    return install_state.home_directory() / "Documents" / "ai-cross-mem"


def uninstall(delete_memories=False):
    system = platform.system()
    if system not in ("Windows", "Darwin"):
        raise RuntimeError("Uninstallation is supported on Windows and macOS only.")

    project_root = Path(__file__).resolve().parent
    state_dir = install_state.state_directory()
    manifest_path = state_dir / "install-manifest.json"
    manifest = {}
    has_manifest = manifest_path.is_file()
    if has_manifest:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("Cannot read install manifest: {}".format(error))
        if manifest.get("schema_version") != install_state.SCHEMA_VERSION:
            raise RuntimeError("Unsupported install manifest version; refusing to remove files.")
    else:
        log("No install manifest found; using conservative legacy cleanup.")

    items = manifest.get("items", {})
    settings = install_state.home_directory() / ".claude" / "settings.json"
    remove_hooks(settings, manifest.get("hooks", []), allow_legacy=not has_manifest)

    config_paths = [
        install_state.home_directory() / ".claude" / "AGENTS.md",
        install_state.home_directory() / ".claude" / "CLAUDE.md",
        install_state.home_directory() / ".codeium" / "windsurf" / "AGENTS.md",
    ]
    settings_resolved = str(settings.resolve()).casefold()
    config_resolved = {str(path.resolve()).casefold() for path in config_paths}
    processed_config = set()
    for name, item in list(items.items()):
        path = Path(name)
        if str(path.resolve()).casefold() in config_resolved:
            processed_config.add(str(path.resolve()).casefold())
            remove_config_file(path, item)
        elif str(path.resolve()).casefold() != settings_resolved:
            restore_or_remove_item(path, item, state_dir)

    for path in config_paths:
        if str(path.resolve()).casefold() not in processed_config:
            remove_untracked_legacy_config(path)

    if not has_manifest:
        remove_legacy_skill_files(project_root)

    for root in install_state.managed_roots()[:2]:
        strip_empty_directories(root)

    memories = memory_directory()
    if delete_memories and memories.exists():
        if not memories.is_dir() or memories.is_symlink():
            raise RuntimeError("Refusing to delete a non-directory memory path: {}".format(memories))
        answer = input(
            "Type DELETE to permanently remove all saved memories at {}: ".format(memories)
        ).strip()
        if answer == "DELETE":
            shutil.rmtree(str(memories))
            log("Deleted saved memories.")
        else:
            log("Memory deletion cancelled; saved memories were kept.")
    else:
        log("Saved memories were kept at: {}".format(memories))

    if has_manifest:
        for child in (state_dir / "pending", state_dir / "after", state_dir / "backups"):
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(str(child))
        try:
            manifest_path.unlink()
            state_dir.rmdir()
        except OSError:
            log("Some install-state files were preserved for manual review at: {}".format(state_dir))
    log("ai-cross-mem uninstall finished.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safely uninstall ai-cross-mem.")
    parser.add_argument(
        "--delete-memories",
        action="store_true",
        help="Ask for an additional explicit confirmation before deleting saved memories.",
    )
    args = parser.parse_args(argv)
    try:
        uninstall(delete_memories=args.delete_memories)
    except (OSError, RuntimeError, ValueError) as error:
        print("Uninstall failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
