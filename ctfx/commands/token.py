"""TokenCommand — ctfx token update / ctfx token show"""

from __future__ import annotations

import click
from rich.console import Console

from ctfx.managers.config import ConfigManager

console = Console()


@click.group("token")
def token_group() -> None:
    """Manage auth tokens."""


@token_group.command("show")
def token_show() -> None:
    """Display the current root token."""
    cfg = ConfigManager.load()
    console.print(f"[yellow]{cfg.root_token}[/yellow]")
    console.print(f"[dim]Token version: {cfg.token_version}[/dim]")


@token_group.command("update")
@click.option("--print", "do_print", is_flag=True, help="Only emit the new token (for scripting)")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def token_update(do_print: bool, yes: bool) -> None:
    """Rotate the root token (invalidates all existing sessions and MCP configs)."""
    cfg = ConfigManager.load()

    if not do_print:
        console.print(
            "[yellow]Warning:[/yellow] rotating the token will invalidate all existing "
            "API/MCP bearer tokens and WebUI login sessions."
        )
        if not yes and not click.confirm("Rotate root token now?", default=False):
            console.print("[dim]Cancelled.[/dim]")
            return

    new_token = cfg.rotate_token()

    if do_print:
        # Scripting-friendly output: only the token
        click.echo(new_token)
        return

    console.print("[green]Root token rotated.[/green]")
    console.print(f"[bold yellow]{new_token}[/bold yellow]")
    console.print("[dim]Save this token — it will not be shown again.[/dim]")
    console.print(
        "\n[dim]If you exported MCP client config, regenerate it:[/dim] "
        "[cyan]ctfx mcp --out <path>[/cyan]"
    )
