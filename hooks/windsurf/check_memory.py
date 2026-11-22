#!/usr/bin/env python3
"""Windsurf Cascade post-response memory reminder hook.

Cascade hook output is surfaced to the user; unlike Claude's systemMessage,
it cannot inject a system instruction into the agent's context.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def state_file():
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    return home / ".codeium" / "windsurf" / "ai-cross-mem" / ".last_check"


def main():
    try:
        json.load(sys.stdin)
        marker = state_file()
        try:
            last_check = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
            if datetime.now() - last_check < timedelta(minutes=15):
                return 0
        except (OSError, ValueError):
            pass
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now().isoformat(), encoding="utf-8")
        print("ai-cross-mem: Consider whether this Cascade response completed a plan, "
              "resolved a difficult problem, or made a decision worth saving.")
    except Exception:
        # A reminder hook must never interrupt a Cascade workflow.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
