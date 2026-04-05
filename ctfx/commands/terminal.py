"""TerminalCommand — ctfx cli / ctfx wsl / ctfx e / ctfx code / ctfx py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager
from ctfx.utils.process import build_command, popen_configured

console = Console()


def _resolve(path_arg: str | None) -> tuple[ConfigManager, Path]:
    cfg = ConfigManager.load()
    if not cfg.active_competition:
        console.print("[red]No active competition.[/red] Run [cyan]ctfx use[/cyan] first.")
        raise SystemExit(1)
    wm = WorkspaceManager(cfg.basedir, cfg.active_competition)
    try:
        target = wm.resolve_path(path_arg)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    if not target.exists():
        console.print(f"[red]Path does not exist:[/red] {target}")
        raise SystemExit(1)
    return cfg, target


@click.command("cli")
@click.argument("path", required=False)
@click.option("--wsl", "use_wsl", is_flag=True, help="Open WSL shell instead of default shell")
def cmd_cli(path: str | None, use_wsl: bool) -> None:
    """Open a terminal in a new window at the resolved path."""
    cfg, target = _resolve(path)
    t = cfg.terminal

    if use_wsl:
        _open_wsl(t, target)
        return

    import shutil
    cli_cmd = t.get("cli_cmd", "powershell" if sys.platform == "win32" else "/bin/bash")

    if sys.platform == "win32":
        if shutil.which("wt"):
            subprocess.Popen(["wt", "-d", str(target)])
        elif "powershell" in cli_cmd.lower():
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command", f"Set-Location '{target}'"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            popen_configured(cli_cmd, new_console=True, cwd=str(target))
    else:
        _open_terminal_unix(cli_cmd, target)

    console.print(f"[dim]Opened terminal at[/dim] {target}")


@click.command("wsl")
@click.argument("path", required=False)
@click.argument("cmd", nargs=-1)
def cmd_wsl(path: str | None, cmd: tuple[str, ...]) -> None:
    """Open a WSL shell or run a command in WSL."""
    cfg, target = _resolve(path)
    _open_wsl(cfg.terminal, target, extra_cmd=list(cmd))


def _open_wsl(terminal: dict, target: Path, extra_cmd: list[str] | None = None) -> None:
    import shutil
    if sys.platform != "win32" and not shutil.which("wsl"):
        console.print(
            "[red]WSL is not available on this system.[/red] "
            "This feature requires Windows Subsystem for Linux."
        )
        raise SystemExit(1)
    distro = terminal.get("wsl_distro") or "kali-linux"
    wsl_path = WorkspaceManager.to_wsl_path(target)
    wsl_cmd = ["wsl", "-d", distro, "--cd", wsl_path]
    if extra_cmd:
        wsl_cmd += ["--", *extra_cmd]

    if sys.platform == "win32":
        if shutil.which("wt"):
            subprocess.Popen(["wt", "wsl", "-d", distro, "--cd", wsl_path])
        else:
            subprocess.Popen(wsl_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.run(wsl_cmd)


def _open_terminal_unix(cli_cmd: str, target: Path) -> None:
    """Open a new terminal window on Linux/macOS."""
    import shutil
    for term, args in [
        ("gnome-terminal", ["--working-directory", str(target)]),
        ("xterm", ["-e", f"cd '{target}' && {cli_cmd}"]),
        ("konsole", ["--workdir", str(target)]),
        ("xfce4-terminal", ["--working-directory", str(target)]),
        ("lxterminal", ["--working-directory", str(target)]),
    ]:
        if shutil.which(term):
            subprocess.Popen([term, *args])
            return
    subprocess.Popen(build_command(cli_cmd), cwd=str(target))


@click.command("explorer")
@click.argument("path", required=False)
def cmd_explorer(path: str | None) -> None:
    """Open file explorer at the resolved path."""
    cfg, target = _resolve(path)
    t = cfg.terminal

    if sys.platform == "win32":
        explorer = t.get("explorer_cmd") or "explorer.exe"
        popen_configured(explorer, str(target))
    else:
        fm = t.get("file_manager_cmd")
        if not fm:
            console.print("[red]No file manager configured.[/red] Run [cyan]ctfx setup[/cyan].")
            raise SystemExit(1)
        popen_configured(fm, str(target))

    console.print(f"[dim]Opened explorer at[/dim] {target}")


@click.command("code")
@click.argument("path", required=False)
def cmd_code(path: str | None) -> None:
    """Open the resolved path in the configured code editor."""
    cfg, target = _resolve(path)
    editor = cfg.terminal.get("editor_cmd") or "code"
    popen_configured(editor, str(target))
    console.print(f"[dim]Opened {editor} at[/dim] {target}")


@click.command("py")
@click.argument("file", required=False)
def cmd_py(file: str | None) -> None:
    """Run Python in the configured environment."""
    cfg = ConfigManager.load()
    python_cmd = cfg.terminal.get("python_cmd") or "python3"

    if file:
        if cfg.active_competition:
            wm = WorkspaceManager(cfg.basedir, cfg.active_competition)
            try:
                target = wm.resolve_path(None) / file
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise SystemExit(1)
            if not target.exists():
                target = Path(file)
        else:
            target = Path(file)
        cmd_parts = build_command(python_cmd, str(target))
    else:
        cmd_parts = build_command(python_cmd)

    subprocess.run(cmd_parts)
