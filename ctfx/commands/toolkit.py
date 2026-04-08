"""ToolkitCommand — ctfx toolkit ..."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from ctfx.exceptions import CTFxError
from ctfx.managers.toolkit import ToolkitManager

console = Console()


def _tm() -> ToolkitManager:
    return ToolkitManager.ensure_init()


# ---------------------------------------------------------------------------
# ctfx toolkit set ...
# ---------------------------------------------------------------------------

@click.group("set")
def toolkit_set_group() -> None:
    """Manage toolkit sets."""


@toolkit_set_group.command("list")
def toolkit_set_list() -> None:
    """List all toolkit sets."""
    tm = _tm()
    rows = tm.list_sets()

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("ID", style="bold")
    table.add_column("Active")
    table.add_column("Pinned")
    table.add_column("Tools", justify="right")
    table.add_column("Source")

    for row in rows:
        active_mark = "[green]yes[/green]" if row["active"] else ""
        pinned_mark = "[yellow]yes[/yellow]" if row["pinned"] else ""
        source = row["source"] or "[dim]-[/dim]"
        table.add_row(row["id"], active_mark, pinned_mark, str(row["tool_count"]), source)

    console.print(table)


@toolkit_set_group.command("create")
@click.argument("name")
@click.option("--id", "set_id", default=None, help="Set ID (default: slugified name)")
def toolkit_set_create(name: str, set_id: str | None) -> None:
    """Create a new empty toolkit set."""
    if set_id is None:
        set_id = name.lower().replace(" ", "-")
    try:
        _tm().create_set(set_id, name)
    except ValueError as e:
        raise CTFxError(str(e))
    console.print(f"[green]Created[/green] set [bold]{set_id}[/bold] ({name!r})")


@toolkit_set_group.command("enable")
@click.argument("set_id")
def toolkit_set_enable(set_id: str) -> None:
    """Add a set to active sets."""
    try:
        _tm().enable_set(set_id)
    except KeyError as e:
        raise CTFxError(str(e))
    console.print(f"[green]Enabled[/green] set [bold]{set_id}[/bold]")


@toolkit_set_group.command("disable")
@click.argument("set_id")
def toolkit_set_disable(set_id: str) -> None:
    """Remove a set from active sets (keeps file)."""
    try:
        _tm().disable_set(set_id)
    except (KeyError, ValueError) as e:
        raise CTFxError(str(e))
    console.print(f"[yellow]Disabled[/yellow] set [bold]{set_id}[/bold]")


@toolkit_set_group.command("rm")
@click.argument("set_id")
@click.confirmation_option(prompt="Delete this set and all its tools?")
def toolkit_set_rm(set_id: str) -> None:
    """Delete a toolkit set."""
    try:
        _tm().remove_set(set_id)
    except (KeyError, ValueError) as e:
        raise CTFxError(str(e))
    console.print(f"[red]Deleted[/red] set [bold]{set_id}[/bold]")


# ---------------------------------------------------------------------------
# ctfx toolkit list / add / rm / info
# ---------------------------------------------------------------------------

@click.group("toolkit")
def toolkit_group() -> None:
    """Manage your personal attacker toolkit."""


toolkit_group.add_command(toolkit_set_group, name="set")


@toolkit_group.command("list")
@click.option("--cat", default=None, help="Filter by category")
@click.option("--tag", "tags", multiple=True, help="Filter by tag (can repeat)")
@click.option("--set", "set_id", default=None, help="Show only tools from this set")
def toolkit_list(cat: str | None, tags: tuple[str, ...], set_id: str | None) -> None:
    """List toolkit tools across active sets."""
    tm = _tm()
    sets_arg = [set_id] if set_id else None
    tools = tm.list_tools(category=cat, tags=list(tags) or None, sets=sets_arg)

    if not tools:
        console.print("[dim]No tools found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Set")
    table.add_column("Categories")
    table.add_column("Tags")

    for tool in tools:
        cats = ", ".join(tool.get("categories", []))
        tag_str = ", ".join(tool.get("tags", []))
        table.add_row(tool["id"], tool.get("name", ""), tool.get("_set", ""), cats, tag_str)

    console.print(table)


@toolkit_group.command("info")
@click.argument("tool_id")
def toolkit_info(tool_id: str) -> None:
    """Show full detail of a toolkit tool."""
    try:
        tool = _tm().get_tool(tool_id)
    except KeyError as e:
        raise CTFxError(str(e))

    console.print(f"[bold]{tool['id']}[/bold]  [dim](set: {tool.get('_set', '?')})[/dim]")
    console.print(f"  Name:        {tool.get('name', '')}")
    console.print(f"  Categories:  {', '.join(tool.get('categories', []))}")
    console.print(f"  Tags:        {', '.join(tool.get('tags', []))}")
    console.print(f"  Cmd:         [cyan]{tool.get('cmd', '')}[/cyan]")
    if tool.get("description"):
        console.print(f"  Description: {tool['description']}")
    if tool.get("prompt"):
        console.print(f"  Prompt:      [italic]{tool['prompt']}[/italic]")
    if tool.get("ref"):
        console.print(f"  Ref:         {tool['ref']}")


@toolkit_group.command("add")
@click.option("--set", "set_id", default="personal", show_default=True, help="Target set")
def toolkit_add(set_id: str) -> None:
    """Interactively add a tool to a set."""
    console.print(f"Adding tool to set [bold]{set_id}[/bold]. Press Ctrl+C to cancel.\n")

    tool_id = click.prompt("Tool ID (e.g. john-zip)")
    name = click.prompt("Name")
    cmd = click.prompt("Command template (use {exploit}, {file}, {dir} as placeholders)")
    categories_raw = click.prompt("Categories (comma-separated)", default="misc")
    tags_raw = click.prompt("Tags (comma-separated)", default="")
    description = click.prompt("Short description", default="")
    prompt_text = click.prompt("LLM prompt hint (when/how to use)", default="")
    ref = click.prompt("Reference URL or path", default="")

    tool: dict[str, Any] = {
        "id": tool_id,
        "name": name,
        "cmd": cmd,
        "categories": [c.strip() for c in categories_raw.split(",") if c.strip()],
        "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
        "description": description,
        "prompt": prompt_text,
        "ref": ref or None,
    }

    try:
        _tm().add_tool(set_id, tool)
    except (KeyError, ValueError) as e:
        raise CTFxError(str(e))

    console.print(f"[green]Added[/green] tool [bold]{tool_id}[/bold] to set [bold]{set_id}[/bold]")


@toolkit_group.command("rm")
@click.argument("tool_id")
@click.option("--set", "set_id", default=None, help="Restrict search to this set")
@click.confirmation_option(prompt="Remove this tool?")
def toolkit_rm(tool_id: str, set_id: str | None) -> None:
    """Remove a tool from a set."""
    try:
        sid = _tm().remove_tool(tool_id, set_id)
    except KeyError as e:
        raise CTFxError(str(e))
    console.print(f"[red]Removed[/red] [bold]{tool_id}[/bold] from set [bold]{sid}[/bold]")


# ---------------------------------------------------------------------------
# ctfx toolkit import / export / update
# ---------------------------------------------------------------------------

@toolkit_group.command("import")
@click.argument("source")
@click.option("--as", "alias", default=None, help="Override set ID for the imported set")
def toolkit_import(source: str, alias: str | None) -> None:
    """Import a toolkit set from a URL or local JSON file."""
    import urllib.request

    try:
        path = Path(source)
        if path.exists():
            raw = path.read_text(encoding="utf-8")
        elif source.startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=15) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
        else:
            raise CTFxError(f"Not a valid file path or URL: {source!r}")

        data = json.loads(raw)
        if not isinstance(data, dict):
            raise CTFxError("Import source must be a JSON object")

        # Inject source URL so update works later
        if source.startswith("http"):
            data.setdefault("source", source)

        set_id = _tm().import_set(data, alias)
    except (KeyError, ValueError) as e:
        raise CTFxError(str(e))
    except json.JSONDecodeError as e:
        raise CTFxError(f"Invalid JSON: {e}")

    console.print(f"[green]Imported[/green] set [bold]{set_id}[/bold]")


@toolkit_group.command("export")
@click.argument("set_id")
@click.option("--out", default=None, help="Output file path (default: stdout)")
def toolkit_export(set_id: str, out: str | None) -> None:
    """Export a toolkit set to JSON."""
    try:
        data = _tm().export_set(set_id)
    except (KeyError, FileNotFoundError) as e:
        raise CTFxError(str(e))

    output = json.dumps(data, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(output, encoding="utf-8")
        console.print(f"[green]Exported[/green] set [bold]{set_id}[/bold] to {out}")
    else:
        click.echo(output)


@toolkit_group.command("update")
@click.argument("set_id", required=False)
def toolkit_update(set_id: str | None) -> None:
    """Re-fetch set(s) from their source URLs."""
    tm = _tm()
    targets = [set_id] if set_id else [
        sid for sid, meta in tm.sets_meta.items() if meta.get("source")
    ]
    if not targets:
        console.print("[dim]No sets with a source URL to update.[/dim]")
        return
    for sid in targets:
        try:
            tm.update_from_source(sid)
            console.print(f"[green]Updated[/green] set [bold]{sid}[/bold]")
        except (KeyError, ValueError) as e:
            console.print(f"[red]Error updating {sid}:[/red] {e}")
        except Exception as e:  # network / json errors
            console.print(f"[red]Failed to update {sid}:[/red] {e}")
