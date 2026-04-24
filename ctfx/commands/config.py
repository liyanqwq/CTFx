"""ConfigCommand — ctfx config show / ctfx config <key> <value>"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ctfx.managers.config import ConfigManager

console = Console()

_SETTABLE = {
    "basedir",
    "active_competition",
    "terminal.cli_cmd",
    "terminal.editor_cmd",
    "terminal.wsl_distro",
    "terminal.python_cmd",
    "terminal.explorer_cmd",
    "terminal.file_manager_cmd",
    "serve.host",
    "serve.port",
    "auth.webui_cookie_name",
    "auth.one_time_login_ttl_sec",
    "auth.session_ttl_sec",
    "ai_provider",
    "ai_api_key",
    "ai_openai_base_url",
    "ai_anthropic_base_url",
    "anthropic_api_key",
    "ai_model",
    "ai_endpoint",
}


def _flat(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten nested dict to [(dot.key, value), ...] pairs."""
    rows: list[tuple[str, str]] = []
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            rows.extend(_flat(v, key))
        else:
            rows.append((key, "" if v is None else str(v)))
    return rows


@click.group("config")
def config_group() -> None:
    """View or edit global CTFx configuration."""


@config_group.command("show")
def config_show() -> None:
    """Display the current configuration."""
    cfg = ConfigManager.load()
    rows = _flat(cfg.raw)

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key, val in rows:
        display = "[dim]<redacted>[/dim]" if key == "root_token" else val or "[dim]-[/dim]"
        table.add_row(key, display)

    console.print(table)


config_group.add_command(config_show, name="list")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a config value by dot-notation key."""
    if key not in _SETTABLE:
        console.print(f"[red]'{key}' is not settable via this command.[/red]")
        console.print(
            "Settable keys: " + ", ".join(f"[cyan]{k}[/cyan]" for k in sorted(_SETTABLE))
        )
        raise SystemExit(1)

    cfg = ConfigManager.load()

    parts = key.split(".")
    current = cfg.raw
    for part in parts[:-1]:
        current = current.get(part, {})
    existing = current.get(parts[-1]) if isinstance(current, dict) else None

    coerced: str | int | None
    if value.lower() == "null":
        coerced = None
    elif isinstance(existing, int):
        try:
            coerced = int(value)
        except ValueError:
            console.print(f"[red]'{key}' expects an integer value.[/red]")
            raise SystemExit(1)
    else:
        coerced = value

    cfg.set(*parts, coerced)
    cfg.save()

    display = "[dim]null[/dim]" if coerced is None else str(coerced)
    console.print(f"[green]Set[/green] [bold]{key}[/bold] = {display}")

    if key == "serve.host":
        cfg.warn_if_public_bind()
