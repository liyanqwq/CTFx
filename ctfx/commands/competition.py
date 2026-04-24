"""CompetitionCommand — ctfx comp / ctfx use / ctfx init"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager

console = Console()


def _comp_table(comps: list[dict], active: str | None, title: str = "Competitions") -> Table:
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("#", width=3, style="dim")
    table.add_column("Dir")
    table.add_column("Name")
    table.add_column("Year", width=6)
    table.add_column("Mode", width=9)
    table.add_column("Platform", width=9)
    table.add_column("Progress", width=10, justify="right")
    for i, comp in enumerate(comps, 1):
        marker = "[bold green]*[/bold green] " if comp["dir"] == active else "  "
        table.add_row(
            str(i),
            f"{marker}{comp['dir']}",
            str(comp["name"]),
            str(comp.get("year") or "—"),
            str(comp.get("mode") or "—"),
            str(comp.get("platform") or "—"),
            f"{comp.get('solved', 0)}/{comp.get('total', 0)}",
        )
    return table


@click.group("comp")
def comp_group() -> None:
    """Manage competitions."""


@comp_group.command("list")
@click.argument("query", required=False)
def comp_list(query: str | None) -> None:
    """List competitions. Optionally filter by keyword."""
    cfg = ConfigManager.load()
    comps = WorkspaceManager.list_competitions(cfg.basedir)

    if query:
        all_names = [c["dir"] for c in comps] + [c["name"] for c in comps]
        matched = set(WorkspaceManager.fuzzy_match(query, all_names))
        comps = [c for c in comps if c["dir"] in matched or c["name"] in matched]

    if not comps:
        console.print("[dim]No competitions found.[/dim]")
        console.print(
            "Create one with [cyan]ctfx comp init[/cyan] "
            "or change basedir with [cyan]ctfx config set basedir <path>[/cyan]."
        )
        return

    console.print(_comp_table(comps, cfg.active_competition))


@comp_group.command("use")
@click.argument("name", required=False)
def cmd_use(name: str | None) -> None:
    """Switch the active competition. Omit NAME for an interactive selector."""
    cfg = ConfigManager.load()
    comps = WorkspaceManager.list_competitions(cfg.basedir)

    if not comps:
        console.print("[red]No competitions found.[/red] Run [cyan]ctfx comp init[/cyan] first.")
        raise SystemExit(1)

    # --- No argument: interactive selector ---
    if not name:
        if len(comps) == 1:
            _switch(cfg, comps[0])
            return
        console.print(_comp_table(comps, cfg.active_competition))
        _interactive_pick(cfg, comps)
        return

    # --- Exact directory name match ---
    match = next((c for c in comps if c["dir"] == name), None)
    if match:
        _switch(cfg, match)
        return

    # --- Exact display-name match ---
    match = next((c for c in comps if c["name"] == name), None)
    if match:
        _switch(cfg, match)
        return

    # --- Keyword / fuzzy search ---
    all_names = [c["dir"] for c in comps] + [c["name"] for c in comps]
    matched_keys = set(WorkspaceManager.fuzzy_match(name, all_names))
    candidates = [c for c in comps if c["dir"] in matched_keys or c["name"] in matched_keys]

    if not candidates:
        console.print(f"[red]No competition matching '{name}'.[/red]")
        console.print("Run [cyan]ctfx comp list[/cyan] to see available competitions.")
        raise SystemExit(1)

    if len(candidates) == 1:
        _switch(cfg, candidates[0])
        return

    # Multiple matches — prompt user
    console.print(_comp_table(candidates, cfg.active_competition, title=f"Matches for '{name}'"))
    _interactive_pick(cfg, candidates)


def _interactive_pick(cfg: ConfigManager, comps: list[dict]) -> None:
    while True:
        raw = click.prompt("Select number (or q to cancel)", default="q")
        stripped = raw.strip().lower()
        if stripped in ("q", "quit", ""):
            console.print("[dim]Cancelled.[/dim]")
            return
        try:
            idx = int(stripped) - 1
            if 0 <= idx < len(comps):
                _switch(cfg, comps[idx])
                return
        except ValueError:
            pass
        console.print(f"[red]Invalid.[/red] Enter 1–{len(comps)} or q.")


def _switch(cfg: ConfigManager, comp: dict) -> None:
    cfg.active_competition = comp["dir"]
    cfg.save()
    console.print(f"[green]Active competition:[/green] [bold]{comp['dir']}[/bold]")


@comp_group.command("init")
@click.option("--name", prompt=True, help="Competition display name")
@click.option("--year", prompt=True, type=int, help="Competition year")
@click.option(
    "--mode",
    default="jeopardy",
    show_default=True,
    type=click.Choice(["jeopardy", "awd"]),
    help="Competition mode",
)
@click.option(
    "--platform",
    default="manual",
    show_default=True,
    type=click.Choice(["ctfd", "rctf", "manual"]),
    help="Platform adapter",
)
@click.option("--url", default=None, help="Platform URL")
@click.option("--flag-format", default=None, help="Flag format (e.g. flag{...})")
@click.option("--team-name", default=None, help="Team display name")
@click.option("--team-token", default=None, help="Team API token")
def cmd_init(
    name: str,
    year: int,
    mode: str,
    platform: str,
    url: str | None,
    flag_format: str | None,
    team_name: str | None,
    team_token: str | None,
) -> None:
    """Initialize a new competition workspace."""
    cfg = ConfigManager.load()
    safe_name = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name.lower()).strip("_")
    comp_dir = f"{safe_name}_{year}"
    wm = WorkspaceManager(cfg.basedir, comp_dir)

    if (cfg.basedir / comp_dir).exists():
        console.print(
            f"[yellow]Directory '{comp_dir}' already exists.[/yellow] "
            "Use [cyan]ctfx use {comp_dir}[/cyan] to switch to it."
        )
        raise SystemExit(1)

    root = wm.init_competition(
        name=name,
        year=year,
        mode=mode,
        platform=platform,
        url=url,
        flag_format=flag_format,
        team_name=team_name,
        team_token=team_token,
        dir_name=comp_dir,
    )
    cfg.active_competition = root.name
    cfg.save()
    console.print(f"[green]Created[/green] [bold]{root.name}[/bold] at {root}")
    console.print(f"  Mode: {mode} | Platform: {platform}")
    if url:
        console.print(f"  URL: {url}")
    console.print(
        "\n[dim]Next:[/dim] [cyan]ctfx fetch[/cyan] (if CTFd) or [cyan]ctfx chal add[/cyan]"
    )


@comp_group.command("info")
def comp_info() -> None:
    """Show active competition metadata."""
    cfg = ConfigManager.load()
    if not cfg.active_competition:
        console.print("[red]No active competition.[/red] Run [cyan]ctfx use[/cyan] first.")
        raise SystemExit(1)
    wm = WorkspaceManager(cfg.basedir, cfg.active_competition)
    try:
        data = wm.load_ctf_json()
    except FileNotFoundError:
        console.print(f"[red]ctf.json not found for {cfg.active_competition}[/red]")
        raise SystemExit(1)

    challenges = wm.list_challenges()
    solved = sum(1 for c in challenges if c["status"] == "solved")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    for key in ("name", "year", "mode", "platform", "url", "flag_format", "team_name"):
        table.add_row(key, str(data.get(key) or "—"))
    table.add_row("directory", cfg.active_competition)
    table.add_row("progress", f"{solved}/{len(challenges)} solved")
    console.print(table)
