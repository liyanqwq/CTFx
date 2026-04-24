"""AI commands: prompt generation, config export, and connectivity checks."""

from __future__ import annotations

import json
import re
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ctfx.managers.ai import (
    get_api_key_source,
    get_base_url,
    get_model,
    get_provider,
    test_connection,
)
from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager

console = Console()

_EXTRA_INFO_HEADER = "## Extra Info"
_EXTRA_INFO_DEFAULT = (
    "<!-- preserved across regenerations; "
    "add manual notes, known context, team strategy here -->"
)


def _load_active() -> tuple[ConfigManager, WorkspaceManager, dict]:
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
    return cfg, wm, data


def _extract_extra_info(existing_text: str) -> str:
    """Extract the ## Extra Info section from an existing prompt.md."""
    match = re.search(
        rf"^{re.escape(_EXTRA_INFO_HEADER)}\s*\n(.*)",
        existing_text,
        re.MULTILINE | re.DOTALL,
    )
    if match:
        return match.group(1).rstrip()
    return _EXTRA_INFO_DEFAULT


_MCP_SECTION = """\
## MCP Tools

When connected via MCP (Cursor, Claude Desktop, or any MCP-capable client), use these tools:

| Tool | Description |
|------|-------------|
| `list_competitions` | List all competitions in the workspace |
| `get_competition` | Get active (or specified) competition metadata |
| `list_challenges` | List challenges - filter by `category` or `status` |
| `get_challenge` | Get full detail for a specific challenge by name |
| `add_challenge` | Create a new challenge directory with scaffold |
| `set_challenge_status` | Update status: `fetched` -> `seen` -> `working` -> `solved` |
| `get_prompt` | Read this prompt.md file |
| `submit_flag` | Submit a flag to the platform (or record locally) |
| `run_exploit` | Run `solve/exploit.py` via the configured Python command |
| `list_awd_exploits` | List AWD exploit files for a service *(AWD mode only)* |
| `list_awd_patches` | List AWD patch files for a service *(AWD mode only)* |
| `get_config` | Read CTFx global configuration |
| `set_config` | Write a CTFx config value by dot-notation key |"""

_CLI_SECTION = """\
## CLI Reference

Run these from your shell (prefix with `ctfx`):

```
# Competition management
ctfx use <dir>                   Switch active competition
ctfx comp list                   List all competitions
ctfx comp init                   Create a new competition
ctfx comp info                   Show active competition metadata

# Challenge management
ctfx chal list [--cat CAT] [--status STATUS]
ctfx chal add <name> [cat]       Add challenge (interactive category picker if cat omitted)
ctfx chal status <name> <status> [flag]
ctfx chal info <name>
ctfx chal rm <name>

# Platform integration
ctfx fetch [--cat CAT]           Fetch challenges from CTFd
ctfx submit <flag> [--chal NAME] Submit flag to platform
ctfx import <url>                LLM-assisted challenge import from URL

# Terminal helpers (path relative to competition root)
ctfx cli [path]                  Open terminal at path
ctfx wsl [path]                  Open WSL shell at path
ctfx code [path]                 Open VS Code at path
ctfx e [path]                    Open file explorer at path
ctfx py [file]                   Run Python (or open REPL)

# Server
ctfx serve [--port PORT]         Start WebUI + API + MCP server
ctfx webui                       Open WebUI in browser (one-time login)
ctfx mcp [--out PATH]            Generate MCP client config

# Other
ctfx ai [--print]                Regenerate this prompt.md
ctfx ai_test                     Test the configured AI connection
ctfx token update                Rotate root token
ctfx config show                 Show full config
ctfx config set <key> <value>    Edit config by dot-notation key
ctfx i                           Interactive REPL (no ctfx prefix needed)
```"""


def _build_prompt(data: dict, challenges: list[dict], extra_info: str) -> str:
    name = data.get("name", "Unknown CTF")
    year = data.get("year", "")
    team_name = data.get("team_name", "")
    flag_format = data.get("flag_format", "flag{...}")
    mode = data.get("mode", "jeopardy")
    platform = data.get("platform", "manual")
    url = data.get("url", "")

    lines = [
        "You are a professional CTF (Capture The Flag) competition assistant with deep expertise",
        "in all CTF categories including pwn, crypto, web, forensics, rev, and misc.",
        "",
        f"You are assisting team {team_name or '(unnamed)'} in the {name} {year} competition.",
        "",
        "## Competition Info",
    ]
    if url:
        lines.append(f"- Platform: {url}")
    lines += [
        f"- Flag format: `{flag_format}`",
        f"- Mode: {mode}",
        f"- Platform adapter: {platform}",
        "",
        "Do not assume any challenge is a known or previously seen challenge. Treat every",
        "challenge as original and reason from first principles.",
        "",
        "## Challenge Status",
    ]

    by_cat: dict[str, list[dict]] = {}
    for chal in challenges:
        by_cat.setdefault(chal["category"] or "misc", []).append(chal)

    for cat in sorted(by_cat):
        lines.append(f"\n### {cat}")
        for chal in by_cat[cat]:
            pts = f" ({chal['points']} pts)" if chal.get("points") is not None else ""
            status_marker = "done" if chal["status"] == "solved" else "todo"
            lines.append(f"- {status_marker} `{chal['name']}` [{chal['status']}]{pts}")

    lines += [
        "",
        _MCP_SECTION,
        "",
        _CLI_SECTION,
        "",
        _EXTRA_INFO_HEADER,
        extra_info,
        "",
    ]
    return "\n".join(lines)


@click.command("ai")
@click.option("--print", "do_print", is_flag=True, help="Also print prompt to stdout")
def cmd_ai(do_print: bool) -> None:
    """Generate prompt.md with competition context for LLM use."""
    _, wm, data = _load_active()
    challenges = wm.list_challenges()

    prompt_path = wm.competition_root() / "prompt.md"
    if prompt_path.exists():
        existing = prompt_path.read_text(encoding="utf-8")
        extra_info = _extract_extra_info(existing)
    else:
        extra_info = _EXTRA_INFO_DEFAULT

    prompt = _build_prompt(data, challenges, extra_info)

    if do_print:
        console.print(prompt)
        return

    prompt_path.write_text(prompt, encoding="utf-8")
    console.print(f"[green]Wrote[/green] {prompt_path}")
    console.print(
        f"  [dim]{len(challenges)} challenges listed | "
        "edit '## Extra Info' to add manual context[/dim]"
    )


@click.command("ai_test")
@click.option("-v", "--verbose", is_flag=True, help="Print request target details before testing")
def cmd_ai_test(verbose: bool) -> None:
    """Test the configured AI provider, model, and credentials."""
    cfg = ConfigManager.load()
    provider = get_provider(cfg)
    model = get_model(cfg)
    base_url = get_base_url(cfg, provider)

    if verbose:
        console.print(f"[dim]provider:[/dim] {provider}")
        console.print(f"[dim]model:[/dim] {model}")
        console.print(f"[dim]base_url:[/dim] {base_url}")
        console.print(f"[dim]auth_source:[/dim] {get_api_key_source(cfg)}")

    try:
        result = test_connection(cfg)
    except Exception as exc:
        console.print(f"[red]AI connection failed:[/red] {exc}")
        raise SystemExit(1)

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("provider", str(result["provider"]))
    table.add_row("model", str(result["model"]))
    table.add_row("base_url", str(result["base_url"]))
    table.add_row("response", str(result["text"]))
    console.print(table)

    if not result["ok"]:
        console.print("[yellow]AI endpoint responded, but the reply was not exactly 'OK'.[/yellow]")
        raise SystemExit(1)

    console.print("[green]AI connection OK.[/green]")


@click.command("mcp")
@click.option("--out", default=None, help="Write MCP client config JSON to a file")
def cmd_mcp(out: str | None) -> None:
    """Generate MCP client config for Claude Desktop / Cursor."""
    cfg = ConfigManager.load()
    payload = {
        "mcpServers": {
            "ctfx": {
                "url": f"http://{cfg.serve_host}:{cfg.serve_port}/mcp/",
                "headers": {
                    "Authorization": f"Bearer {cfg.root_token}",
                },
            }
        }
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if out:
        Path(out).write_text(text, encoding="utf-8")
        console.print(f"[green]Wrote[/green] {out}")
        console.print(f"[dim]MCP endpoint: http://{cfg.serve_host}:{cfg.serve_port}/mcp[/dim]")
    else:
        console.print(text)
