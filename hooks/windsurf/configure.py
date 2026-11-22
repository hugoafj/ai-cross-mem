#!/usr/bin/env python3
"""Merge the ai-cross-mem Cascade hook into Windsurf's user hooks file."""

import json
import os
from pathlib import Path
import tempfile


def main():
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    base = home / ".codeium" / "windsurf"
    source = Path(__file__).with_name("hooks.json")
    destination = base / "hooks.json"
    hook = json.loads(source.read_text(encoding="utf-8"))["hooks"]
    try:
        settings = json.loads(destination.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        settings = {}
    if not isinstance(settings, dict):
        raise SystemExit("Windsurf hooks.json must contain a JSON object.")
    events = settings.setdefault("hooks", {})
    if not isinstance(events, dict):
        raise SystemExit("Windsurf hooks.json 'hooks' property must be an object.")
    for event, entries in hook.items():
        current = events.setdefault(event, [])
        if not isinstance(current, list):
            raise SystemExit("Windsurf hook event {} must be a list.".format(event))
        current[:] = [entry for entry in current if "ai-cross-mem" not in entry.get("command", "")]
        current.extend(entries)
    base.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".hooks-", dir=str(base), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(settings, stream, indent=2)
            stream.write("\n")
        os.replace(temp_name, str(destination))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
