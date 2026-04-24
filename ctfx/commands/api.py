"""API console commands for remote CTF platform access."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ctfx.commands.platform import _load_wm
from ctfx.managers.platform.ctfd import CTFdPlatform

console = Console()


def _load_ctfd_platform() -> tuple[CTFdPlatform, dict]:
    _, _, data = _load_wm()
    if data.get("platform") != "ctfd":
        console.print("[red]Active competition platform is not CTFd.[/red]")
        raise SystemExit(1)

    url = data.get("url", "")
    token = data.get("team_token", "")
    cookies = data.get("team_cookies", "")
    if not url or (not token and not cookies):
        console.print("[red]Set url and team_token or team_cookies first.[/red]")
        raise SystemExit(1)

    return CTFdPlatform(url, token=token or None, cookies=cookies or None), data


@click.group("api")
def api_group() -> None:
    """CTFd API console commands."""


@api_group.command("test")
def cmd_api_test() -> None:
    """Test whether the configured CTFd API is reachable."""
    platform, _ = _load_ctfd_platform()
    try:
        challenges = platform.fetch_challenges()
    except Exception as e:
        console.print(f"[red]API test failed:[/red] {e}")
        raise SystemExit(1)

    console.print(
        f"[green]API OK.[/green] {len(challenges)} challenge(s) fetched via "
        f"[bold]{platform.auth_mode()}[/bold] auth."
    )


@api_group.command("status")
def cmd_api_status() -> None:
    """Show a quick status summary for the configured CTFd API."""
    platform, _ = _load_ctfd_platform()
    try:
        status = platform.get_api_status()
    except Exception as e:
        console.print(f"[red]API status failed:[/red] {e}")
        raise SystemExit(1)

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("base_url", status["base_url"])
    table.add_row("auth_mode", status["auth_mode"])
    table.add_row("authenticated", "yes" if status["authenticated"] else "no")
    table.add_row("challenges", str(status["challenge_count"]))
    table.add_row("solved_by_me", str(status["solved_count"]))
    table.add_row("scoreboard_entries", str(status["scoreboard_entries"]))
    console.print(table)


@api_group.command("challenges")
def cmd_api_challenges() -> None:
    """List remote challenges from the configured CTFd instance."""
    platform, _ = _load_ctfd_platform()
    try:
        challenges = platform.fetch_challenges()
    except Exception as e:
        console.print(f"[red]Failed to fetch challenges:[/red] {e}")
        raise SystemExit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", justify="right")
    table.add_column("Category")
    table.add_column("Name")
    table.add_column("Points", justify="right")
    table.add_column("Solved", justify="center")
    for item in challenges:
        table.add_row(
            str(item["platform_id"]),
            item["category"],
            item["display_name"] or item["name"],
            str(item["points"] or ""),
            "yes" if item["solved_by_me"] else "no",
        )
    console.print(table)


@api_group.command("scoreboard")
@click.option("--limit", default=10, show_default=True, type=int, help="Rows to display")
def cmd_api_scoreboard(limit: int) -> None:
    """Show the remote CTFd scoreboard."""
    platform, _ = _load_ctfd_platform()
    try:
        scoreboard = platform.get_scoreboard()
    except Exception as e:
        console.print(f"[red]Failed to fetch scoreboard:[/red] {e}")
        raise SystemExit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Team")
    table.add_column("Score", justify="right")
    for idx, item in enumerate(scoreboard[: max(limit, 0)], 1):
        table.add_row(
            str(idx),
            str(item.get("name") or item.get("account_name") or item.get("team") or "?"),
            str(item.get("score") or item.get("value") or 0),
        )
    console.print(table)


@api_group.command("solves")
@click.argument("challenge_id", type=int)
def cmd_api_solves(challenge_id: int) -> None:
    """Show solves for a remote challenge ID."""
    platform, _ = _load_ctfd_platform()
    try:
        solves = platform.get_challenge_solves(challenge_id)
    except Exception as e:
        console.print(f"[red]Failed to fetch solves:[/red] {e}")
        raise SystemExit(1)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Date")
    table.add_column("Account")
    for item in solves:
        table.add_row(
            str(item.get("date") or item.get("created") or ""),
            str(item.get("name") or item.get("account_name") or item.get("user") or "?"),
        )
    console.print(table)
