#!/usr/bin/env python3
"""Update ai-cross-mem from the latest GitHub release."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile


REPOSITORY = "hugoafj/ai-cross-mem"
API_URL = "https://api.github.com/repos/{}/releases/latest".format(REPOSITORY)
USER_AGENT = "ai-cross-mem-updater"
TARGETS = {
    "claude_skill": Path.home() / ".claude" / "skills" / "ai-cross-mem",
    "windsurf_skill": Path.home() / ".codeium" / "windsurf" / "skills" / "ai-cross-mem",
    "claude_hooks": Path.home() / ".claude" / "skills" / "ai-cross-mem" / "hooks",
}


class UpdateError(Exception):
    """An expected update failure with a user-facing message."""


def _request(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if url == API_URL and error.code == 404:
            raise UpdateError("No published GitHub release was found yet.")
        raise UpdateError("GitHub request failed with HTTP {} for {}.".format(error.code, url))
    except (urllib.error.URLError, OSError) as error:
        raise UpdateError("Could not download {}: {}".format(url, error))


def _release_archive():
    try:
        release = json.loads(_request(API_URL).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateError("GitHub returned invalid release metadata: {}".format(error))
    tag = release.get("tag_name")
    if not tag:
        raise UpdateError("The GitHub release does not contain a tag name.")
    archive_url = "https://api.github.com/repos/{}/zipball/{}".format(REPOSITORY, tag)
    return tag, _request(archive_url)


def _extract_archive(archive_bytes, destination):
    archive_path = destination / "release.zip"
    archive_path.write_bytes(archive_bytes)
    extraction = destination / "extracted"
    extraction.mkdir()
    try:
        with zipfile.ZipFile(str(archive_path)) as archive:
            for entry in archive.infolist():
                member = PurePosixPath(entry.filename)
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or "\\" in entry.filename
                    or (member.parts and ":" in member.parts[0])
                ):
                    raise UpdateError("Release archive contains an unsafe path.")
                output = extraction.joinpath(*member.parts)
                if os.path.commonpath((str(extraction.resolve()), str(output.resolve()))) != str(
                    extraction.resolve()
                ):
                    raise UpdateError("Release archive contains an unsafe path.")
            archive.extractall(str(extraction))
    except (OSError, zipfile.BadZipFile) as error:
        raise UpdateError("Could not unpack the GitHub release: {}".format(error))

    candidates = [
        path for path in extraction.iterdir()
        if path.is_dir() and (path / "install.ps1").is_file() and (path / "install.sh").is_file()
    ]
    if len(candidates) != 1:
        raise UpdateError("The release archive does not have the expected installer files.")
    return candidates[0]


def _load_legacy_files(source):
    manifest = source / "legacy-files.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UpdateError("Cannot read legacy-files.json: {}".format(error))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(
        data.get("files"), list
    ):
        raise UpdateError("legacy-files.json must have version 1 and a files list.")

    deletions = []
    seen = set()
    for entry in data["files"]:
        if not isinstance(entry, dict) or set(entry) != {"target", "path"}:
            raise UpdateError("Each legacy file entry must contain only target and path.")
        target_name, relative_name = entry["target"], entry["path"]
        if target_name not in TARGETS or not isinstance(relative_name, str) or "\\" in relative_name:
            raise UpdateError("Legacy file entry has an invalid target or path.")
        relative = PurePosixPath(relative_name)
        if relative.is_absolute() or not relative.parts or any(
            part in ("", ".", "..") for part in relative.parts
        ):
            raise UpdateError("Legacy file path must stay inside its installation directory.")
        target = TARGETS[target_name]
        candidate = target.joinpath(*relative.parts)
        resolved_target = target.resolve()
        resolved_candidate = candidate.resolve()
        if os.path.commonpath((str(resolved_target), str(resolved_candidate))) != str(
            resolved_target
        ):
            raise UpdateError("Legacy file path escapes its installation directory.")
        if candidate.is_symlink():
            raise UpdateError("Refusing to delete a symbolic link: {}".format(candidate))
        if candidate.exists() and not candidate.is_file():
            raise UpdateError("Only individual legacy files can be removed: {}".format(candidate))
        key = str(candidate).casefold()
        if key in seen:
            raise UpdateError("Duplicate legacy file entry: {}".format(candidate))
        seen.add(key)
        deletions.append(candidate)
    return deletions


def _run_installer(source):
    system = platform.system()
    if system == "Windows":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(source / "install.ps1"),
        ]
    elif system == "Darwin":
        command = ["bash", str(source / "install.sh")]
    else:
        raise UpdateError("Updates are supported on Windows and macOS only.")
    try:
        subprocess.run(command, cwd=str(source), check=True)
    except FileNotFoundError as error:
        raise UpdateError("Could not start the platform installer: {}".format(error))
    except subprocess.CalledProcessError as error:
        raise UpdateError("The platform installer failed with exit code {}.".format(error.returncode))


def update(source=None, assume_yes=False):
    temporary = None
    tag = None
    try:
        if source is None:
            temporary = tempfile.TemporaryDirectory(prefix="ai-cross-mem-update-")
            tag, archive_bytes = _release_archive()
            source = _extract_archive(archive_bytes, Path(temporary.name))
        else:
            source = Path(source).expanduser().resolve()
            if not source.is_dir():
                raise UpdateError("Local update source is not a directory: {}".format(source))

        deletions = _load_legacy_files(source)
        existing = [path for path in deletions if path.is_file()]
        if existing and not assume_yes:
            print("The update will remove these deprecated files:")
            for path in existing:
                print("  - {}".format(path))
            answer = input("Continue with the update? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Update cancelled.")
                return False

        _run_installer(source)
        for path in existing:
            path.unlink()
            print("Removed deprecated file: {}".format(path))
        if tag:
            print("Updated ai-cross-mem to release {}.".format(tag))
        else:
            print("Updated ai-cross-mem from local source.")
        return True
    finally:
        if temporary is not None:
            temporary.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update ai-cross-mem on Windows or macOS.")
    parser.add_argument(
        "--source",
        help="Use a local project directory instead of downloading the latest GitHub release.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask for confirmation before deleting files in the release manifest.",
    )
    args = parser.parse_args(argv)
    try:
        update(source=args.source, assume_yes=args.yes)
    except UpdateError as error:
        print("Update failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
