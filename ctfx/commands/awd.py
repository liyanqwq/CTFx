"""AWDCommand — ctfx awd ssh / scp / cmd (AWD mode only)"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager

console = Console()


def _load_awd() -> tuple[ConfigManager, WorkspaceManager, dict]:
    cfg = ConfigManager.load()
    if not cfg.active_competition:
        console.print("[red]No active competition.[/red] Run [cyan]ctfx use[/cyan] first.")
        raise SystemExit(1)
    wm = WorkspaceManager(cfg.basedir, cfg.active_competition)
    try:
        data = wm.load_ctf_json()
    except FileNotFoundError:
        console.print("[red]ctf.json not found.[/red]")
        raise SystemExit(1)
    if data.get("mode") != "awd":
        console.print(
            "[red]AWD commands are only available in AWD mode.[/red] "
            "Set [cyan]\"mode\": \"awd\"[/cyan] in ctf.json."
        )
        raise SystemExit(1)
    return cfg, wm, data


def _resolve_host(wm: WorkspaceManager, service: str, team: str | None) -> tuple[str, str]:
    """Return (username, ip) for the target team/host."""
    try:
        hosts = wm.load_hostlist(service)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    if not hosts:
        console.print(
            f"[red]No hosts found for service '{service}'.[/red] "
            f"Create [cyan]{service}/hostlist.txt[/cyan] in the competition directory."
        )
        raise SystemExit(1)

    if team:
        match = next((h for h in hosts if h[0].lower() == team.lower()), None)
        if not match:
            available = ", ".join(h[0] for h in hosts)
            console.print(
                f"[red]Team '{team}' not found.[/red] Available: {available}"
            )
            raise SystemExit(1)
        return "root", match[1]

    if len(hosts) == 1:
        return "root", hosts[0][1]

    from rich.table import Table
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("#", width=3, style="dim")
    table.add_column("Team")
    table.add_column("IP")
    for i, (t, ip) in enumerate(hosts, 1):
        table.add_row(str(i), t, ip)
    console.print(table)

    while True:
        raw = click.prompt("Select host number (or q to cancel)", default="q")
        if raw.strip().lower() in ("q", "quit", ""):
            raise SystemExit(0)
        try:
            idx = int(raw.strip()) - 1
            if 0 <= idx < len(hosts):
                return "root", hosts[idx][1]
        except ValueError:
            pass
        console.print(f"[red]Invalid.[/red] Enter 1–{len(hosts)} or q.")


@click.group("awd")
def awd_group() -> None:
    """AWD mode commands (SSH, SCP, remote exec)."""


@awd_group.command("ssh")
@click.argument("service")
@click.option("--team", default=None, help="Team name to SSH into")
@click.option("--port", default=22, type=int, show_default=True)
@click.option("--user", default="root", show_default=True)
def awd_ssh(service: str, team: str | None, port: int, user: str) -> None:
    """Open an interactive SSH shell into a service host."""
    _, wm, _ = _load_awd()
    _, ip = _resolve_host(wm, service, team)
    try:
        key_path = wm.get_service_key_path(service)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    console.print(
        f"Connecting to [bold]{ip}:{port}[/bold] "
        + (f"(key: {key_path.name})" if key_path else "(password auth)")
    )

    try:
        from ctfx.managers.awd import AWDSession
        with AWDSession(ip, port=port, username=user, key_path=key_path) as sess:
            sess.interactive_shell()
    except Exception as e:
        console.print(f"[red]SSH failed:[/red] {e}")
        raise SystemExit(1)


@awd_group.command("scp")
@click.argument("service")
@click.argument("src")
@click.argument("dst")
@click.option("--team", default=None, help="Target team name")
@click.option("--port", default=22, type=int, show_default=True)
@click.option("--user", default="root", show_default=True)
def awd_scp(service: str, src: str, dst: str, team: str | None, port: int, user: str) -> None:
    """SCP file transfer. Prefix remote paths with ':' (e.g. :/tmp/file)."""
    _, wm, _ = _load_awd()
    _, ip = _resolve_host(wm, service, team)
    try:
        key_path = wm.get_service_key_path(service)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    try:
        from ctfx.managers.awd import AWDSession
        with AWDSession(ip, port=port, username=user, key_path=key_path) as sess:
            if src.startswith(":"):
                remote = src[1:]
                local = Path(dst)
                console.print(f"[dim]Downloading[/dim] {ip}:{remote} → {local}")
                sess.get(remote, local)
                console.print(f"[green]Done.[/green] Saved to {local}")
            elif dst.startswith(":"):
                local = Path(src)
                remote = dst[1:]
                if not local.exists():
                    console.print(f"[red]Local file not found:[/red] {local}")
                    raise SystemExit(1)
                console.print(f"[dim]Uploading[/dim] {local} → {ip}:{remote}")
                sess.put(local, remote)
                console.print(f"[green]Done.[/green]")
            else:
                console.print("[red]Prefix the remote path with ':' (e.g. :/tmp/file).[/red]")
                raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]SCP failed:[/red] {e}")
        raise SystemExit(1)


@awd_group.command("cmd")
@click.argument("service")
@click.argument("command", nargs=-1, required=True)
@click.option("--team", default=None, help="Run on a specific team's host")
@click.option("--all-teams", "all_teams", is_flag=True, help="Run on all hosts in hostlist")
@click.option("--port", default=22, type=int, show_default=True)
@click.option("--user", default="root", show_default=True)
@click.option("--timeout", "cmd_timeout", default=30.0, type=float, show_default=True)
def awd_cmd(
    service: str,
    command: tuple[str, ...],
    team: str | None,
    all_teams: bool,
    port: int,
    user: str,
    cmd_timeout: float,
) -> None:
    """Run a remote command on service host(s) via SSH."""
    _, wm, _ = _load_awd()
    cmd_str = " ".join(command)
    try:
        key_path = wm.get_service_key_path(service)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    if all_teams:
        hosts = wm.load_hostlist(service)
        if not hosts:
            console.print(f"[red]No hosts found for service '{service}'.[/red]")
            raise SystemExit(1)
        targets = [(t, ip) for t, ip in hosts]
    else:
        _, ip = _resolve_host(wm, service, team)
        targets = [(team or ip, ip)]

    from ctfx.managers.awd import AWDSession

    for team_name, ip in targets:
        console.print(f"\n[bold cyan]{team_name}[/bold cyan] ({ip})")
        try:
            with AWDSession(ip, port=port, username=user, key_path=key_path) as sess:
                stdout, stderr, code = sess.run(cmd_str, timeout=cmd_timeout)
            if stdout.strip():
                console.print(stdout.rstrip())
            if stderr.strip():
                console.print(f"[dim]{stderr.rstrip()}[/dim]")
            if code != 0:
                console.print(f"[yellow]exit {code}[/yellow]")
        except Exception as e:
            console.print(f"  [red]Failed:[/red] {e}")
