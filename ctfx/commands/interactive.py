"""Interactive REPL."""

from __future__ import annotations

import shlex

import click
from rich.console import Console

console = Console()


@click.command("interactive")
def cmd_interactive() -> None:
    """Open a simple CTFx REPL."""
    from ctfx.cli import main

    console.print("[cyan]CTFx interactive mode[/cyan] ([bold]q[/bold] to quit)")
    while True:
        try:
            raw = input("ctfx> ").strip()
        except EOFError:
            console.print()
            break
        if raw.lower() in {"q", "quit", "exit"}:
            break
        if not raw:
            continue
        try:
            main.main(args=shlex.split(raw), prog_name="ctfx", standalone_mode=False)
        except SystemExit:
            pass
