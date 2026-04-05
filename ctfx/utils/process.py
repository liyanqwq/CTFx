"""Process helpers for parsing configured commands safely."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_command(command: str) -> list[str]:
    """Split a configured command string into argv parts."""
    stripped = command.strip()
    if not stripped:
        raise ValueError("Command must not be empty")

    parts = shlex.split(stripped, posix=sys.platform != "win32")
    if sys.platform == "win32":
        parts = [_strip_wrapping_quotes(part) for part in parts]
    return parts


def build_command(command: str, *extra_args: str) -> list[str]:
    """Expand a configured command string and append extra arguments."""
    return [*split_command(command), *(str(arg) for arg in extra_args)]


def popen_configured(
    command: str,
    *extra_args: str,
    new_console: bool = False,
    cwd: str | None = None,
) -> subprocess.Popen:
    """Spawn a configured command without going through shell=True."""
    argv = build_command(command, *extra_args)
    executable = shutil.which(argv[0]) or argv[0]
    argv = [executable, *argv[1:]]

    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        suffix = Path(executable).suffix.lower()
        if suffix in {".bat", ".cmd"}:
            argv = ["cmd", "/c", executable, *argv[1:]]
        if new_console:
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    if cwd is not None:
        kwargs["cwd"] = cwd

    return subprocess.Popen(argv, **kwargs)
