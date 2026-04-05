"""AWDManager — SSH/SCP operations via paramiko."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import paramiko
    _HAS_PARAMIKO = True
except ImportError:
    _HAS_PARAMIKO = False


def _require_paramiko() -> None:
    if not _HAS_PARAMIKO:
        raise RuntimeError(
            "paramiko is not installed. Run: pip install paramiko"
        )


class AWDSession:
    """Thin wrapper around a paramiko SSH connection for AWD operations."""

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        key_path: Path | None = None,
        password: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        _require_paramiko()
        self.host = host
        self.port = port
        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        self._client.set_missing_host_key_policy(paramiko.RejectPolicy())
        connect_kwargs: dict = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": timeout,
        }
        if key_path:
            connect_kwargs["key_filename"] = str(key_path)
        elif password:
            connect_kwargs["password"] = password
        self._client.connect(**connect_kwargs)

    def run(self, command: str, timeout: float = 30.0) -> tuple[str, str, int]:
        """Run a command. Returns (stdout, stderr, exit_code)."""
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace"), exit_code

    def put(self, local: Path, remote: str) -> None:
        """Upload a local file to remote path."""
        with self._client.open_sftp() as sftp:
            sftp.put(str(local), remote)

    def get(self, remote: str, local: Path) -> None:
        """Download a remote file to local path."""
        local.parent.mkdir(parents=True, exist_ok=True)
        with self._client.open_sftp() as sftp:
            sftp.get(remote, str(local))

    def interactive_shell(self, path: str | None = None) -> None:
        """Open an interactive shell, optionally cd-ing to path first.

        Note: interactive mode requires a Unix-compatible stdin (Linux/macOS or WSL).
        On Windows, use `ctfx wsl` or a dedicated SSH client instead.
        """
        if sys.platform == "win32":
            raise RuntimeError(
                "Interactive SSH shell is not supported on native Windows. "
                "Use 'ctfx wsl' or connect via Windows Terminal / PuTTY."
            )
        import select as _select
        chan = self._client.invoke_shell()
        if path:
            chan.send(f"cd {path}\n")
        chan.setblocking(False)
        while True:
            r, _, _ = _select.select([chan, sys.stdin], [], [], 0.1)
            if chan in r:
                data = chan.recv(1024)
                if not data:
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            if sys.stdin in r:
                data = sys.stdin.read(1)
                if not data:
                    break
                chan.send(data)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AWDSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
