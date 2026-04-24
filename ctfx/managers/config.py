"""ConfigManager — global config read/write and first-run initialization."""

from __future__ import annotations

import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any

import click

try:
    import json
except ImportError:
    pass

import json as _json

SCHEMA_VERSION = "0.2.6"
DEFAULT_PORT = 8694
DEFAULT_HOST = "127.0.0.1"
CONFIG_DIR = Path("~/.config/ctfx").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.json"


def _detect_platform() -> str:
    return "windows" if sys.platform == "win32" else "linux"


def _default_config(basedir: str) -> dict[str, Any]:
    platform = _detect_platform()
    terminal: dict[str, Any]
    if platform == "windows":
        terminal = {
            "cli_cmd": "powershell",
            "editor_cmd": "code",
            "wsl_distro": "kali-linux",
            "python_cmd": "wsl -d kali-linux python3",
            "explorer_cmd": "explorer.exe",
            "file_manager_cmd": None,
        }
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        terminal = {
            "cli_cmd": shell,
            "editor_cmd": "code",
            "wsl_distro": None,
            "python_cmd": "python3",
            "explorer_cmd": None,
            "file_manager_cmd": _detect_file_manager(),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "basedir": basedir,
        "root_token": secrets.token_hex(32),
        "token_version": 1,
        "active_competition": None,
        "terminal": terminal,
        "serve": {
            "port": DEFAULT_PORT,
            "host": DEFAULT_HOST,
        },
        "auth": {
            "webui_cookie_name": "ctfx_auth",
            "one_time_login_ttl_sec": 60,
            "session_ttl_sec": 2592000,
        },
        "ai_provider": "openai",
        "ai_model": "gpt-5.4",
        "ai_api_key": None,
        "ai_openai_base_url": "https://api.openai.com/v1",
        "ai_anthropic_base_url": "https://api.anthropic.com",
        "anthropic_api_key": None,
        "ai_endpoint": None,
    }


def _detect_file_manager() -> str | None:
    for fm in ("nautilus", "thunar", "dolphin", "nemo"):
        if _which(fm):
            return fm
    return None


def _which(cmd: str) -> str | None:
    import shutil
    return shutil.which(cmd)


class ConfigManager:
    """Manages ~/.config/ctfx/config.json."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def load(cls) -> "ConfigManager":
        """Load config from disk.  Runs first-run init wizard if absent."""
        if CONFIG_FILE.exists():
            raw = _json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            raw = _migrate(raw)
            instance = cls(raw)
            try:
                instance.basedir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return instance
        return cls._first_run()

    @classmethod
    def _first_run(cls) -> "ConfigManager":
        click.echo("Welcome to CTFx! Let's set up your workspace.\n")
        basedir = click.prompt(
            "Base directory for CTF workspaces",
            default="~/ctf",
        )
        basedir = str(Path(basedir).expanduser())

        data = _default_config(basedir)

        if _detect_platform() == "windows":
            wsl = click.prompt(
                "WSL distro name",
                default=data["terminal"]["wsl_distro"],
            )
            data["terminal"]["wsl_distro"] = wsl
            data["terminal"]["python_cmd"] = f"wsl -d {wsl} python3"

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        Path(basedir).expanduser().mkdir(parents=True, exist_ok=True)
        _atomic_write(CONFIG_FILE, data)

        token = data["root_token"]
        click.echo(f"\nConfig written to {CONFIG_FILE}")
        click.secho(
            f"\nRoot token (save this - it won't be shown again):\n  {token}\n",
            fg="yellow",
            bold=True,
        )
        return cls(data)

    def save(self) -> None:
        """Atomically write config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write(CONFIG_FILE, self._data)

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    def get(self, *keys: str, default: Any = None) -> Any:
        """Nested get: cfg.get('terminal', 'cli_cmd')"""
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    def set(self, *keys_and_value: Any) -> None:
        """Nested set: cfg.set('terminal', 'cli_cmd', 'bash')"""
        *keys, value = keys_and_value
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value

    @property
    def active_competition(self) -> str | None:
        return self._data.get("active_competition")

    @active_competition.setter
    def active_competition(self, name: str) -> None:
        self._data["active_competition"] = name

    @property
    def basedir(self) -> Path:
        return Path(self._data["basedir"]).expanduser()

    @property
    def root_token(self) -> str:
        return self._data["root_token"]

    @property
    def token_version(self) -> int:
        return self._data.get("token_version", 1)

    @property
    def serve_host(self) -> str:
        return self._data.get("serve", {}).get("host", DEFAULT_HOST)

    @property
    def serve_port(self) -> int:
        return self._data.get("serve", {}).get("port", DEFAULT_PORT)

    @property
    def terminal(self) -> dict[str, Any]:
        return self._data.get("terminal", {})

    @property
    def auth(self) -> dict[str, Any]:
        return self._data.get("auth", {})

    def rotate_token(self) -> str:
        """Generate new root_token, increment token_version, save. Returns new token."""
        new_token = secrets.token_hex(32)
        self._data["root_token"] = new_token
        self._data["token_version"] = self.token_version + 1
        self.save()
        return new_token

    def warn_if_public_bind(self) -> None:
        host = self.serve_host
        if host not in ("127.0.0.1", "::1", "localhost"):
            click.secho(
                f"Warning: server will bind to {host} - WebUI/API/MCP reachable from outside "
                "the local machine.",
                fg="yellow",
                err=True,
            )


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Back-fill fields added in newer schema versions."""
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("token_version", 1)
    data.setdefault("auth", {
        "webui_cookie_name": "ctfx_auth",
        "one_time_login_ttl_sec": 60,
        "session_ttl_sec": 2592000,
    })
    data.setdefault("ai_provider", "openai")
    data.setdefault("ai_model", "gpt-5.4")
    data.setdefault("ai_api_key", None)
    data.setdefault("ai_openai_base_url", "https://api.openai.com/v1")
    data.setdefault("ai_anthropic_base_url", "https://api.anthropic.com")
    data.setdefault("anthropic_api_key", None)
    data.setdefault("ai_endpoint", None)
    data["schema_version"] = SCHEMA_VERSION
    return data


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically via a temp file + rename."""
    dir_ = path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
