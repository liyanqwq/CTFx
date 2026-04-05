"""SetupCommand — ctfx setup (interactive configuration wizard)."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ctfx.managers.config import (
    CONFIG_FILE,
    ConfigManager,
    _atomic_write,
    _default_config,
    _detect_platform,
)

console = Console()


@click.command("setup")
def cmd_setup() -> None:
    """Run the interactive configuration wizard (safe to re-run at any time)."""
    if CONFIG_FILE.exists():
        _reconfigure()
    else:
        # First-run path is handled inside ConfigManager.load()
        ConfigManager.load()


def _reconfigure() -> None:
    """Interactive re-configuration for an existing install."""
    cfg = ConfigManager.load()

    console.print("[bold cyan]CTFx Setup[/bold cyan]  —  reconfiguring existing install\n")
    _show_summary(cfg)
    console.print()

    if not click.confirm("Reconfigure now?", default=False):
        console.print("[dim]No changes made.[/dim]")
        cfg.warn_if_public_bind()
        return

    data = dict(cfg.raw)

    # --- Workspace ---
    console.print("\n[bold]Workspace[/bold]")
    basedir = click.prompt("Base directory", default=str(cfg.basedir))
    data["basedir"] = basedir

    # --- Terminal ---
    console.print("\n[bold]Terminal[/bold]")
    t = dict(cfg.terminal)
    platform = _detect_platform()

    if platform == "windows":
        t["cli_cmd"] = click.prompt("Default shell command", default=t.get("cli_cmd") or "powershell")
        t["wsl_distro"] = click.prompt("WSL distro name", default=t.get("wsl_distro") or "kali-linux")
        python_default = f"wsl -d {t['wsl_distro']} python3"
        t["python_cmd"] = click.prompt("Python command", default=t.get("python_cmd") or python_default)
        t["explorer_cmd"] = click.prompt("File explorer command", default=t.get("explorer_cmd") or "explorer.exe")
    else:
        import os
        t["cli_cmd"] = click.prompt("Default shell command", default=t.get("cli_cmd") or os.environ.get("SHELL", "/bin/bash"))
        t["python_cmd"] = click.prompt("Python command", default=t.get("python_cmd") or "python3")
        t["file_manager_cmd"] = click.prompt(
            "File manager command (leave blank to skip)",
            default=t.get("file_manager_cmd") or "",
        ) or None

    t["editor_cmd"] = click.prompt("Code editor command", default=t.get("editor_cmd") or "code")
    data["terminal"] = t

    # --- Server ---
    console.print("\n[bold]Server[/bold]")
    serve = dict(cfg.raw.get("serve", {}))
    serve["host"] = click.prompt("Bind host", default=serve.get("host", "127.0.0.1"))
    serve["port"] = click.prompt("Bind port", default=serve.get("port", 8694), type=int)
    data["serve"] = serve

    # --- AI ---
    console.print("\n[bold]AI / LLM[/bold]")
    data["ai_model"] = click.prompt("AI model", default=data.get("ai_model") or "claude-sonnet-4-6")
    api_key_display = "(set)" if data.get("anthropic_api_key") else "(not set)"
    new_key = click.prompt(
        f"Anthropic API key {api_key_display} — press Enter to keep",
        default="",
        show_default=False,
    )
    if new_key.strip():
        data["anthropic_api_key"] = new_key.strip()

    # Persist
    from ctfx.managers.config import CONFIG_DIR
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(CONFIG_FILE, data)

    # Create basedir
    from pathlib import Path
    Path(basedir).expanduser().mkdir(parents=True, exist_ok=True)

    # Reload and warn
    cfg2 = ConfigManager.load()
    cfg2.warn_if_public_bind()

    console.print("\n[green]Configuration saved.[/green]")
    console.print(f"  Config file: [dim]{CONFIG_FILE}[/dim]")
    console.print(f"  Basedir:     [bold]{basedir}[/bold]")
    console.print("\n[dim]Next steps:[/dim]")
    console.print("  [cyan]ctfx comp init[/cyan]  — create a competition")
    console.print("  [cyan]ctfx serve[/cyan]       — start the server")
    console.print("  [cyan]ctfx webui[/cyan]        — open the WebUI")


def _show_summary(cfg: ConfigManager) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    table.add_row("Config", str(CONFIG_FILE))
    table.add_row("Basedir", str(cfg.basedir))
    table.add_row("Active competition", cfg.active_competition or "[dim](none)[/dim]")
    table.add_row("Server", f"{cfg.serve_host}:{cfg.serve_port}")
    table.add_row("Editor", cfg.terminal.get("editor_cmd") or "[dim](not set)[/dim]")
    table.add_row("Python command", cfg.terminal.get("python_cmd") or "[dim](not set)[/dim]")
    table.add_row("Token version", str(cfg.token_version))
    console.print(table)
