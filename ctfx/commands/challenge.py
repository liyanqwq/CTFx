"""ChallengeCommand — ctfx chal / ctfx add"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager, DEFAULT_CATEGORIES
from ctfx.managers.scaffold import ScaffoldManager

console = Console()

STATUS_COLORS = {
    "fetched": "dim",
    "seen": "blue",
    "working": "yellow",
    "hoard": "magenta",
    "solved": "green",
}


def _load_wm() -> tuple[ConfigManager, WorkspaceManager]:
    cfg = ConfigManager.load()
    if not cfg.active_competition:
        console.print("[red]No active competition.[/red] Run [cyan]ctfx use[/cyan] first.")
        raise SystemExit(1)
    wm = WorkspaceManager(cfg.basedir, cfg.active_competition)
    wm.ensure_basedir()
    return cfg, wm


def _chal_table(chals: list[dict], title: str = "Challenges") -> Table:
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Challenge", min_width=18)
    table.add_column("Category", width=12)
    table.add_column("Status", width=10)
    table.add_column("Points", width=7, justify="right")

    for c in chals:
        color = STATUS_COLORS.get(c["status"], "")
        pts = str(c["points"]) if c["points"] is not None else "—"
        table.add_row(
            c["name"],
            c["category"] or "—",
            f"[{color}]{c['status']}[/{color}]" if color else c["status"],
            pts,
        )
    return table


@click.group("chal")
def chal_group() -> None:
    """Manage challenges in the active competition."""


@chal_group.command("list")
@click.argument("query", required=False)
@click.option("--cat", default=None, help="Filter by category")
@click.option("--status", default=None, help="Filter by status")
def chal_list(query: str | None, cat: str | None, status: str | None) -> None:
    """List challenges."""
    _, wm = _load_wm()
    chals = wm.list_challenges()

    if cat:
        chals = [c for c in chals if c["category"].lower() == cat.lower()]
    if status:
        chals = [c for c in chals if c["status"].lower() == status.lower()]
    if query:
        names = [c["name"] for c in chals]
        matched = WorkspaceManager.fuzzy_match(query, names)
        chals = [c for c in chals if c["name"] in matched]

    if not chals:
        filters = " ".join(
            f for f in [
                f"query='{query}'" if query else "",
                f"cat={cat}" if cat else "",
                f"status={status}" if status else "",
            ] if f
        )
        console.print(
            f"[dim]No challenges found[/dim]"
            + (f"[dim] ({filters})[/dim]" if filters else "[dim].[/dim]")
        )
        console.print("Try [cyan]ctfx chal add[/cyan] or [cyan]ctfx fetch[/cyan].")
        return

    console.print(_chal_table(chals))


@chal_group.command("add")
@click.argument("chal")
@click.argument("cat", required=False)
def chal_add(chal: str, cat: str | None) -> None:
    """Add a new challenge and scaffold its directory."""
    cfg, wm = _load_wm()

    if not cat:
        cat = _pick_category()
        if cat is None:
            return

    try:
        chal_dir = wm.create_challenge(cat, chal)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    data = wm.load_ctf_json()
    remote = data.get("challenges", {}).get(f"{cat}/{chal}", {}).get("remote")
    ScaffoldManager.generate(cat, chal_dir, remote=remote)

    console.print(
        f"[green]Created[/green] [bold]{cat}/{chal}[/bold] at {chal_dir}"
    )
    has_exploit = (chal_dir / "solve" / "exploit.py").exists()
    if has_exploit:
        console.print(f"  [dim]scaffold:[/dim] solve/exploit.py")


def _pick_category() -> str | None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Category", style="bold")
    for i, cat in enumerate(DEFAULT_CATEGORIES, 1):
        table.add_row(str(i), cat)
    console.print("\nSelect category:")
    console.print(table)

    while True:
        raw = click.prompt("Enter number (or q to cancel)", default="q")
        if raw.strip().lower() in ("q", "quit", ""):
            console.print("[dim]Cancelled.[/dim]")
            return None
        try:
            idx = int(raw.strip()) - 1
            if 0 <= idx < len(DEFAULT_CATEGORIES):
                return DEFAULT_CATEGORIES[idx]
        except ValueError:
            pass
        console.print(f"[red]Invalid.[/red] Enter 1–{len(DEFAULT_CATEGORIES)} or q.")


@chal_group.command("rm")
@click.argument("chal")
def chal_rm(chal: str) -> None:
    """Remove a challenge directory and metadata entry."""
    _, wm = _load_wm()
    entry = wm.find_challenge(chal)
    if entry is None:
        console.print(f"[red]Challenge '{chal}' not found.[/red]")
        raise SystemExit(1)

    chal_dir = wm.competition_root() / entry["key"]
    console.print(f"[yellow]This will delete:[/yellow] {chal_dir}")
    if not click.confirm("Are you sure?", default=False):
        console.print("[dim]Cancelled.[/dim]")
        return

    wm.remove_challenge(chal)
    console.print(f"[green]Removed[/green] [bold]{chal}[/bold]")


@chal_group.command("info")
@click.argument("chal")
def chal_info(chal: str) -> None:
    """Show challenge detail."""
    _, wm = _load_wm()
    entry = wm.find_challenge(chal)
    if entry is None:
        console.print(f"[red]Challenge '{chal}' not found.[/red]")
        raise SystemExit(1)

    color = STATUS_COLORS.get(entry["status"], "")
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("Name", entry["name"])
    table.add_row("Category", entry["category"] or "—")
    status_str = f"[{color}]{entry['status']}[/{color}]" if color else entry["status"]
    table.add_row("Status", status_str)
    table.add_row("Points", str(entry["points"]) if entry["points"] is not None else "—")
    table.add_row("Remote", entry["remote"] or "—")
    table.add_row("Flag", entry["flag"] or "—")
    table.add_row("Solved at", entry["solved_at"] or "—")
    console.print(table)


@chal_group.command("status")
@click.argument("chal")
@click.argument("status", type=click.Choice(["fetched", "seen", "working", "hoard", "solved"]))
@click.argument("flag", required=False)
def chal_status(chal: str, status: str, flag: str | None) -> None:
    """Update challenge status."""
    _, wm = _load_wm()
    try:
        wm.set_challenge_status(chal, status, flag=flag)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    color = STATUS_COLORS.get(status, "")
    status_str = f"[{color}]{status}[/{color}]" if color else status
    console.print(f"[bold]{chal}[/bold] → {status_str}")
    if flag:
        console.print(f"  flag: [green]{flag}[/green]")


cmd_add = chal_add
