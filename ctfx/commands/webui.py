"""WebUICommand — ctfx webui / ctfx web / ctfx ui"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import webbrowser

import click
from rich.console import Console

from ctfx.managers.config import ConfigManager

console = Console()


def _make_ticket(root_token: str, token_version: int, ttl_sec: int) -> str:
    """Generate a signed one-time ticket."""
    nonce = secrets.token_hex(16)
    expires = int(time.time()) + ttl_sec
    payload = f"{nonce}.{expires}.{token_version}"
    sig = hmac.new(root_token.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


@click.command("webui")
def cmd_webui() -> None:
    """Open the WebUI in the default browser using a one-time login URL."""
    cfg = ConfigManager.load()
    host = cfg.serve_host
    port = cfg.serve_port
    ttl = cfg.auth.get("one_time_login_ttl_sec", 60)

    ticket = _make_ticket(cfg.root_token, cfg.token_version, ttl)
    url = f"http://{host}:{port}/auth/webui/one-time-login?ticket={ticket}&next=/"

    console.print(f"Opening WebUI at [cyan]http://{host}:{port}/[/cyan]")
    console.print(f"[dim]One-time login ticket valid for {ttl}s[/dim]")
    webbrowser.open(url)
