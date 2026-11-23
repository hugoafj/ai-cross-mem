#!/usr/bin/env python3
"""Record the files ai-cross-mem creates or changes during installation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import uuid


SCHEMA_VERSION = 1


def home_directory():
    if os.name == "nt":
        return Path(os.environ.get("USERPROFILE", str(Path.home())))
    return Path.home()


def state_directory():
    home = home_directory()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
    elif platform.system() == "Darwin":
        root = home / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local" / "state")))
    return root / "ai-cross-mem"


def managed_roots():
    home = home_directory()
    return [
        home / ".claude" / "skills" / "ai-cross-mem",
        home / ".codeium" / "windsurf" / "skills" / "ai-cross-mem",
        home / ".codeium" / "windsurf" / "ai-cross-mem",
        home / ".codeium" / "windsurf" / "hooks.json",
        home / ".claude" / "AGENTS.md",
        home / ".claude" / "CLAUDE.md",
        home / ".claude" / "settings.json",
        home / ".codeium" / "windsurf" / "AGENTS.md",
    ]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_under(root):
    if root.is_file() and not root.is_symlink():
        return [root]
    if not root.is_dir() or root.is_symlink():
        return []
    result = []
    for directory, directories, filenames in os.walk(str(root), followlinks=False):
        directories[:] = [
            name for name in directories if not (Path(directory) / name).is_symlink()
        ]
        for filename in filenames:
            path = Path(directory) / filename
            if path.is_file() and not path.is_symlink():
                result.append(path)
    return result


def snapshot_files(destination):
    destination.mkdir(parents=True)
    result = {}
    settings_path = home_directory() / ".claude" / "settings.json"
    for root in managed_roots():
        if root == settings_path:
            continue
        for path in files_under(root):
            absolute = str(path.resolve())
            backup = destination / uuid.uuid4().hex
            shutil.copy2(str(path), str(backup))
            result[absolute] = {
                "sha256": sha256_file(path),
                "backup": str(backup),
            }
    return result


def load_json(path, default):
    try:
        with path.open(encoding="utf-8-sig") as stream:
            return json.load(stream)
    except FileNotFoundError:
        return default


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(str(temporary), "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(str(temporary), str(path))


def begin_install():
    state_dir = state_directory()
    pending_dir = state_dir / "pending"
    if pending_dir.exists():
        shutil.rmtree(str(pending_dir))
    state_dir.mkdir(parents=True, exist_ok=True)
    before = {
        "files": snapshot_files(pending_dir),
        "hooks": hook_entries(load_json(home_directory() / ".claude" / "settings.json", {})),
    }
    save_json(pending_dir / "before.json", before)


def hook_entries(settings):
    entries = []
    hooks = settings.get("hooks", {}) if isinstance(settings, dict) else {}
    if not isinstance(hooks, dict):
        return entries
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    command = hook["command"]
                    if "ai-cross-mem" in command and "check_memory.py" in command:
                        entries.append({"event": event, "group": group})
                        break
    return entries


def capture_install():
    state_dir = state_directory()
    pending_dir = state_dir / "pending"
    pending_path = pending_dir / "before.json"
    snapshot = load_json(pending_path, None)
    if snapshot is None:
        raise RuntimeError("No install snapshot found; run install_state.py begin first.")
    before = snapshot["files"]

    after_dir = state_dir / "after"
    if after_dir.exists():
        shutil.rmtree(str(after_dir))
    after = snapshot_files(after_dir)
    manifest_path = state_dir / "install-manifest.json"
    manifest = load_json(
        manifest_path,
        {"schema_version": SCHEMA_VERSION, "items": {}, "hooks": []},
    )
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("Unsupported install manifest version.")

    all_paths = set(before) | set(after)
    items = manifest.setdefault("items", {})
    for name in all_paths:
        original = before.get(name)
        current = after.get(name)
        original_hash = original.get("sha256") if original else None
        current_hash = current.get("sha256") if current else None
        if original_hash == current_hash or current is None:
            continue

        previous = items.get(name)
        if previous and original_hash == previous.get("installed_sha256"):
            original_backup = previous.get("original_backup")
        else:
            original_backup = None
            if original:
                backup_dir = state_dir / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / uuid.uuid4().hex
                shutil.copy2(original["backup"], str(backup_path))
                original_backup = str(backup_path)
        items[name] = {
            "installed_sha256": current_hash,
            "original_backup": original_backup,
        }

    settings_path = home_directory() / ".claude" / "settings.json"
    settings_after = load_json(settings_path, {})
    prior_hooks = manifest.setdefault("hooks", [])
    old_entries = snapshot["hooks"]
    for entry in hook_entries(settings_after):
        if entry not in old_entries and entry not in prior_hooks:
            prior_hooks.append(entry)

    save_json(manifest_path, manifest)
    shutil.rmtree(str(pending_dir), ignore_errors=True)
    shutil.rmtree(str(after_dir), ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("begin", "capture"))
    args = parser.parse_args(argv)
    try:
        if args.action == "begin":
            begin_install()
        else:
            capture_install()
    except (OSError, RuntimeError, ValueError) as error:
        print("Could not record ai-cross-mem installation state: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
