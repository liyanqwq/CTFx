"""PlatformCommand — ctfx fetch / ctfx submit / ctfx import"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager
from ctfx.managers.scaffold import ScaffoldManager

console = Console()


def _load_wm() -> tuple[ConfigManager, WorkspaceManager, dict]:
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


def _get_platform(data: dict):
    platform = data.get("platform", "manual")
    if platform == "manual":
        console.print("[red]Platform is 'manual' — fetch/submit not available.[/red]")
        raise SystemExit(1)
    if platform == "ctfd":
        from ctfx.managers.platform.ctfd import CTFdPlatform
        url = data.get("url", "")
        token = data.get("team_token", "")
        cookies = data.get("team_cookies", "")
        if not url or (not token and not cookies):
            console.print("[red]Platform URL and team_token or team_cookies must be set in ctf.json.[/red]")
            raise SystemExit(1)
        return CTFdPlatform(url, token=token or None, cookies=cookies or None)
    console.print(f"[red]Platform '{platform}' is not yet supported.[/red]")
    raise SystemExit(1)


@click.command("fetch")
@click.option("--cat", default=None, help="Fetch only this category")
@click.option("--chal", default=None, help="Fetch only this challenge name")
@click.option("--no-files", is_flag=True, help="Skip downloading attachments")
def cmd_fetch(cat: str | None, chal: str | None, no_files: bool) -> None:
    """Fetch challenge list and attachments from platform."""
    cfg, wm, data = _load_wm()
    platform = _get_platform(data)

    console.print(f"[cyan]Fetching challenges from {data.get('url', '')}...[/cyan]")

    try:
        challenges = platform.fetch_challenges()
    except Exception as e:
        console.print(f"[red]Fetch failed:[/red] {e}")
        raise SystemExit(1)

    created = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Processing...", total=len(challenges))

        for ch in challenges:
            ch_cat = ch["category"]
            ch_name = ch["name"]

            if cat and ch_cat != cat:
                progress.advance(task)
                continue
            if chal and ch_name != chal:
                progress.advance(task)
                continue

            key = f"{ch_cat}/{ch_name}"
            existing = data.get("challenges", {}).get(key)

            if existing:
                existing.setdefault("platform_id", ch["platform_id"])
                if existing.get("points") is None:
                    existing["points"] = ch["points"]
                skipped += 1
                progress.advance(task)
                continue

            progress.update(task, description=f"Adding {key}")

            try:
                chal_dir = wm.create_challenge(ch_cat, ch_name)
            except ValueError as e:
                console.print(f"  [yellow]Warning:[/yellow] skipped invalid challenge {key}: {e}")
                progress.advance(task)
                continue
            remote = ch.get("connection_info", "")
            ScaffoldManager.generate(ch_cat, chal_dir, remote=remote or None)

            if ch.get("description"):
                (chal_dir / "chal.md").write_text(
                    f"# {ch['display_name']}\n\n{ch['description']}\n",
                    encoding="utf-8",
                )

            data.setdefault("challenges", {})[key] = {
                "platform_id": ch["platform_id"],
                "status": "solved" if ch["solved_by_me"] else "fetched",
                "flag": None,
                "points": ch["points"],
                "remote": remote or None,
                "fetched_at": now,
                "solved_at": now if ch["solved_by_me"] else None,
            }
            created += 1

            if not no_files and ch.get("files"):
                src_dir = chal_dir / "src"
                for file_url in ch["files"]:
                    full_url = (
                        f"{data['url'].rstrip('/')}{file_url}"
                        if file_url.startswith("/")
                        else file_url
                    )
                    progress.update(task, description=f"Downloading {Path(file_url).name}")
                    try:
                        platform.download_file(full_url, src_dir)
                    except Exception as e:
                        console.print(f"  [yellow]Warning:[/yellow] failed to download {file_url}: {e}")

            progress.advance(task)

    wm.save_ctf_json(data)

    console.print(
        f"[green]Done.[/green] {created} new challenge(s) added, {skipped} already present."
    )


@click.command("submit")
@click.argument("flag")
@click.option("--chal", default=None, help="Challenge name (required if ambiguous)")
def cmd_submit(flag: str, chal: str | None) -> None:
    """Submit a flag to the platform."""
    cfg, wm, data = _load_wm()

    if not data.get("submit_api"):
        console.print("[red]submit_api is disabled for this competition.[/red]")
        raise SystemExit(1)

    platform = _get_platform(data)

    if chal:
        entry = wm.find_challenge(chal)
    else:
        working = [c for c in wm.list_challenges() if c["status"] in ("working", "seen", "fetched", "hoard")]
        if len(working) == 1:
            entry = working[0]
            console.print(f"[dim]Auto-selected challenge:[/dim] {entry['name']}")
        else:
            console.print("[red]Multiple unsolved challenges — use --chal to specify.[/red]")
            raise SystemExit(1)

    if entry is None:
        console.print(f"[red]Challenge '{chal}' not found.[/red]")
        raise SystemExit(1)

    platform_id = data.get("challenges", {}).get(entry["key"], {}).get("platform_id")
    if platform_id is None:
        console.print(
            f"[yellow]No platform_id for '{entry['name']}'.[/yellow] "
            "Run [cyan]ctfx fetch[/cyan] first, or record flag locally with "
            "[cyan]ctfx chal status <name> solved <flag>[/cyan]."
        )
        raise SystemExit(1)

    console.print(f"Submitting flag for [bold]{entry['name']}[/bold]...")

    try:
        resp = platform.submit_flag(platform_id, flag)
    except Exception as e:
        console.print(f"[red]Submission failed:[/red] {e}")
        raise SystemExit(1)

    result_status = resp.get("data", {}).get("status", "")
    message = resp.get("data", {}).get("message", "")

    if result_status == "correct":
        wm.set_challenge_status(entry["name"], "solved", flag=flag)
        console.print(f"[green bold]Correct![/green bold] Flag accepted. {message}")
    elif result_status == "already_solved":
        console.print(f"[yellow]Already solved.[/yellow] {message}")
    else:
        console.print(f"[red]Incorrect.[/red] {message or result_status}")


@click.command("import")
@click.argument("url", required=False)
@click.option("--stdin", is_flag=True, help="Read challenge data from stdin")
def cmd_import(url: str | None, stdin: bool) -> None:
    """LLM-assisted challenge import from URL or stdin."""
    cfg, wm, data = _load_wm()

    if stdin:
        console.print("[dim]Reading from stdin (Ctrl+D to finish)...[/dim]")
        raw_content = sys.stdin.read()
    elif url:
        console.print(f"[cyan]Fetching {url}...[/cyan]")
        import requests
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            raw_content = resp.text
        except Exception as e:
            console.print(f"[red]Failed to fetch URL:[/red] {e}")
            raise SystemExit(1)
    else:
        console.print("[red]Provide a URL argument or --stdin.[/red]")
        raise SystemExit(1)

    extracted = _llm_extract(raw_content, cfg)
    if extracted is None:
        raise SystemExit(1)

    console.print("\n[bold]Extracted challenge:[/bold]")
    _print_extracted(extracted)
    if not click.confirm("\nCreate this challenge?", default=True):
        console.print("[dim]Cancelled.[/dim]")
        return

    cat = extracted.get("category", "misc")
    name = extracted.get("name", "imported").lower().replace(" ", "_")
    remote = extracted.get("remote", "")
    points = extracted.get("points")

    try:
        chal_dir = wm.create_challenge(cat, name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    ScaffoldManager.generate(cat, chal_dir, remote=remote or None)

    desc = extracted.get("description", "")
    if desc:
        (chal_dir / "chal.md").write_text(
            f"# {extracted.get('name', name)}\n\n{desc}\n", encoding="utf-8"
        )

    if extracted.get("attachments"):
        import requests
        src_dir = chal_dir / "src"
        src_dir.mkdir(exist_ok=True)
        for att in extracted["attachments"]:
            att_url = att.get("url", "")
            att_name = att.get("name", Path(att_url).name)
            if not att_url:
                continue
            console.print(f"  [dim]Downloading[/dim] {att_name}...")
            try:
                r = requests.get(att_url, timeout=30)
                r.raise_for_status()
                (src_dir / att_name).write_bytes(r.content)
            except Exception as e:
                console.print(f"  [yellow]Warning:[/yellow] failed: {e}")

    key = f"{cat}/{name}"
    data.setdefault("challenges", {})[key] = {
        "status": "seen",
        "flag": None,
        "points": points,
        "remote": remote or None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "solved_at": None,
    }
    if extracted.get("flag_format"):
        data["flag_format"] = extracted["flag_format"]

    wm.save_ctf_json(data)
    console.print(f"\n[green]Created[/green] [bold]{cat}/{name}[/bold] at {chal_dir}")


def _llm_extract(content: str, cfg: ConfigManager) -> dict | None:
    """Send content to the configured LLM and extract structured challenge data."""
    try:
        import anthropic
    except ImportError:
        console.print(
            "[red]anthropic package not installed.[/red] "
            "Run: [cyan]pip install CTFx[llm][/cyan]"
        )
        return None

    api_key = _get_api_key(cfg)
    if not api_key:
        return None

    model = cfg.get("ai_model") or "claude-sonnet-4-6"
    endpoint = cfg.get("ai_endpoint")

    schema_example = json.dumps({
        "name": "baby_pwn",
        "category": "pwn",
        "description": "Overflow the buffer and get shell.",
        "attachments": [{"name": "chall", "url": "https://..."}],
        "flag_format": "flag{...}",
        "remote": "nc chall.ctf.org 1337",
        "points": 100,
    }, indent=2)

    prompt = (
        "Extract CTF challenge information from the following text and output ONLY valid JSON "
        "matching this schema (no preamble, no markdown fences):\n\n"
        f"{schema_example}\n\n"
        "Use null for missing fields. Category must be one of: pwn, crypto, web, forensics, rev, misc.\n\n"
        f"Text to extract from:\n---\n{content[:8000]}\n---"
    )

    console.print(f"[dim]Calling {model} for extraction...[/dim]")

    client_kwargs: dict = {"api_key": api_key}
    if endpoint:
        client_kwargs["base_url"] = endpoint

    client = anthropic.Anthropic(**client_kwargs)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]LLM returned invalid JSON:[/red] {e}")
        return None
    except Exception as e:
        console.print(f"[red]LLM call failed:[/red] {e}")
        return None


def _get_api_key(cfg: ConfigManager) -> str | None:
    import os
    key = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("anthropic_api_key")
    if key:
        return key
    console.print(
        "[red]No Anthropic API key found.[/red] "
        "Set [cyan]ANTHROPIC_API_KEY[/cyan] environment variable or "
        "run: [cyan]ctfx config set anthropic_api_key <key>[/cyan]"
    )
    return None


def _print_extracted(d: dict) -> None:
    from rich.table import Table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    for k in ("name", "category", "points", "remote", "flag_format", "description"):
        v = d.get(k)
        if v:
            table.add_row(k, str(v)[:80])
    atts = d.get("attachments", [])
    if atts:
        table.add_row("attachments", ", ".join(a.get("name", "?") for a in atts))
    console.print(table)
