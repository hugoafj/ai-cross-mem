#!/usr/bin/env bash
set -euo pipefail

say() { printf '%s\n' "$*"; }
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

copy_skill() {
    local source="$1" destination="$2" relative target
    mkdir -p "$destination"
    while IFS= read -r -d '' relative; do
        relative="${relative#./}"
        target="$destination/$relative"
        mkdir -p "$(dirname "$target")"
        cp -p "$source/$relative" "$target"
    done < <(
        cd "$source"
        find . -type d -name '__pycache__' -prune -o \
            -type f ! -name '*.pyc' ! -name '*.pyo' ! -name '*.pyd' -print0
    )
    find "$destination" -type d -name '__pycache__' -empty -delete
}

[[ "$(uname -s)" == "Darwin" ]] || fail "This installer supports macOS only. On Windows, run install.ps1."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is required. Install it from https://www.python.org/downloads/"
integration="${1:-both}"
case "$integration" in
    claude|windsurf|both) ;;
    *) fail "Usage: $0 [claude|windsurf|both]" ;;
esac

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
home_dir="${HOME:?HOME is not set}"
memory_dir="$home_dir/Documents/ai-cross-mem"
claude_dir="$home_dir/.claude"
claude_skill="$claude_dir/skills/ai-cross-mem"
windsurf_dir="$home_dir/.codeium/windsurf"
windsurf_skill="$windsurf_dir/skills/ai-cross-mem"

if [[ "$integration" == "claude" || "$integration" == "both" ]]; then
    [[ -d "$project_root/skills/claude/ai-cross-mem" ]] || fail "Claude skill files are missing from $project_root."
fi
if [[ "$integration" == "windsurf" || "$integration" == "both" ]]; then
    [[ -d "$project_root/skills/windsurf/ai-cross-mem" ]] || fail "Windsurf skill files are missing from $project_root."
fi
python3 "$project_root/install_state.py" begin || fail "Could not record pre-install state."

say "Installing ai-cross-mem for macOS..."
mkdir -p "$memory_dir"
if [[ "$integration" == "claude" || "$integration" == "both" ]]; then
    mkdir -p "$claude_dir/skills" "$claude_skill"
    copy_skill "$project_root/skills/claude/ai-cross-mem" "$claude_skill"
fi

append_config() {
    local source="$1" destination="$2" marker="$3"
    [[ -f "$source" ]] || fail "Configuration source is missing: $source"
    if [[ -f "$destination" ]] && grep -Fq "$marker" "$destination"; then
        say "Already configured: $destination"
        return
    fi
    mkdir -p "$(dirname "$destination")"
    if [[ -f "$destination" ]]; then
        cp "$destination" "$destination.backup-$(date +%Y%m%d-%H%M%S)"
        printf '\n\n<!-- BEGIN AI-CROSS-MEM MANAGED BLOCK -->\n' >> "$destination"
        cat "$source" >> "$destination"
        printf '\n<!-- END AI-CROSS-MEM MANAGED BLOCK -->\n' >> "$destination"
    else
        {
            printf '<!-- BEGIN AI-CROSS-MEM MANAGED BLOCK -->\n'
            cat "$source"
            printf '\n<!-- END AI-CROSS-MEM MANAGED BLOCK -->\n'
        } > "$destination"
    fi
    say "Configured: $destination"
}

if [[ "$integration" == "claude" || "$integration" == "both" ]]; then
    append_config "$project_root/config/claude/AGENTS.md" "$claude_dir/AGENTS.md" "ai-cross-mem: Shared Memory System"
    append_config "$project_root/config/claude/CLAUDE.md" "$claude_dir/CLAUDE.md" "ai-cross-mem: Shared Memory System"
fi

if [[ "$integration" == "windsurf" || "$integration" == "both" ]]; then
    mkdir -p "$windsurf_dir"
    [[ -d "$project_root/skills/windsurf/ai-cross-mem" ]] || fail "Windsurf skill files are missing."
    mkdir -p "$windsurf_skill"
    copy_skill "$project_root/skills/windsurf/ai-cross-mem" "$windsurf_skill"
    append_config "$project_root/config/windsurf/AGENTS.md" "$windsurf_dir/AGENTS.md" "ai-cross-mem: Shared Memory System"
    mkdir -p "$windsurf_dir/ai-cross-mem"
    cp "$project_root/hooks/windsurf/check_memory.py" "$windsurf_dir/ai-cross-mem/"
    python3 "$project_root/hooks/windsurf/configure.py" || fail "Could not configure Windsurf hook."
else
    say "Windsurf not detected; skipping its installation."
fi

if [[ "$integration" == "claude" || "$integration" == "both" ]]; then
hook_source="$project_root/hooks/scripts/check_memory.py"
[[ -f "$hook_source" ]] || fail "Hook script is missing: $hook_source"
hook_dir="$claude_skill/hooks"
mkdir -p "$hook_dir"
cp "$hook_source" "$hook_dir/check_memory.py"

settings="$claude_dir/settings.json"
hook_config="$project_root/hooks/claude/hooks.json"
if [[ -f "$settings" ]]; then
    cp "$settings" "$settings.backup-$(date +%Y%m%d-%H%M%S)"
fi
python3 - "$settings" "$hook_config" <<'PY'
import json
import os
import sys
import tempfile

settings_path, hook_path = sys.argv[1:]
try:
    with open(settings_path, encoding="utf-8") as stream:
        settings = json.load(stream)
except FileNotFoundError:
    settings = {}
except (json.JSONDecodeError, OSError) as error:
    raise SystemExit("Cannot read Claude settings.json: {}".format(error))
with open(hook_path, encoding="utf-8") as stream:
    configured = json.load(stream)["hooks"]
hooks = settings.setdefault("hooks", {})
for event, entries in configured.items():
    existing = hooks.setdefault(event, [])
    if not isinstance(existing, list):
        raise SystemExit("Claude settings hooks.{} must be a list.".format(event))
    for entry in entries:
        command = entry.get("hooks", [{}])[0].get("command", "")
        if not any(command in item.get("hooks", [{}])[0].get("command", "")
                   for item in existing if isinstance(item, dict)):
            existing.append(entry)
directory = os.path.dirname(settings_path)
os.makedirs(directory, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=directory, text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(settings, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, settings_path)
except Exception:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
PY
fi

say "Installed memories directory: $memory_dir"
say "Selected integration(s): $integration"
python3 "$project_root/install_state.py" capture || fail "Installed, but could not save the ownership manifest."
say "Installation complete. Start a new Claude Code session to use ai-cross-mem."
