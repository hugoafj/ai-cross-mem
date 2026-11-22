#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    printf '%s\n' "Error: This uninstaller supports macOS only. On Windows, run uninstall.ps1." >&2
    exit 1
fi

command -v python3 >/dev/null 2>&1 || {
    printf '%s\n' "Error: Python 3 is required to safely uninstall ai-cross-mem." >&2
    exit 1
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/uninstall.py" "$@"
