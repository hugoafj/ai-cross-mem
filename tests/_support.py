import subprocess


def run_checked(command, **kwargs):
    """Run a command and surface its output when it fails.

    ``subprocess.run(..., check=True, capture_output=True)`` raises
    ``CalledProcessError`` whose message hides the captured stdout/stderr, which
    makes CI failures opaque. This helper captures both streams and re-raises an
    ``AssertionError`` that includes them, so the real error is always visible.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    result = subprocess.run(command, **kwargs)
    if result.returncode != 0:
        rendered = " ".join(str(part) for part in command)
        raise AssertionError(
            f"command failed with exit code {result.returncode}: {rendered}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    return result
