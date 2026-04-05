"""ServeCommand — ctfx serve"""

from __future__ import annotations

import click
from rich.console import Console

from ctfx.managers.config import ConfigManager

console = Console()


@click.command("serve")
@click.option("--port", default=None, type=int, help="Override configured port")
@click.option("--host", default=None, help="Override configured host")
def cmd_serve(port: int | None, host: str | None) -> None:
    """Start the unified FastAPI server (WebUI + REST API + MCP)."""
    import uvicorn
    from ctfx.server.app import create_app

    cfg = ConfigManager.load()

    bind_host = host or cfg.serve_host
    bind_port = port or cfg.serve_port

    cfg.warn_if_public_bind()
    cfg.basedir.mkdir(parents=True, exist_ok=True)

    app = create_app(
        root_token=cfg.root_token,
        token_version=cfg.token_version,
        auth_config=cfg.auth,
        basedir=cfg.basedir,
        active_competition=cfg.active_competition,
        python_cmd=cfg.terminal.get("python_cmd", "python3"),
    )

    console.print(
        f"[bold cyan]CTFx server[/bold cyan] starting on "
        f"[bold]http://{bind_host}:{bind_port}[/bold]"
    )
    if cfg.active_competition:
        console.print(f"  Active competition: [bold]{cfg.active_competition}[/bold]")
    console.print(f"  API docs:  http://{bind_host}:{bind_port}/api/docs")
    console.print(f"  MCP:       http://{bind_host}:{bind_port}/mcp/")
    console.print(f"  WebUI:     [cyan]ctfx webui[/cyan]  (generates one-time login URL)")

    uvicorn.run(app, host=bind_host, port=bind_port)
