"""MCP server — StreamableHTTP, mounted at /mcp in the FastAPI app."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, MutableMapping

from mcp.server.fastmcp import FastMCP

from ctfx.managers.workspace import WorkspaceManager
from ctfx.utils.process import build_command


def build_mcp_server(
    basedir: Path,
    active_competition_ref: MutableMapping[str, str | None],
    python_cmd: str,
    config_path: Path | None = None,
) -> FastMCP:
    mcp = FastMCP(
        "ctfx",
        instructions=(
            "CTFx workspace tools. Use these to manage CTF competitions, "
            "list challenges, update status, run exploits, and submit flags."
        ),
        streamable_http_path="/",
    )

    def _wm(competition: str | None = None) -> WorkspaceManager:
        comp = competition or active_competition_ref.get("value")
        if not comp:
            raise ValueError("No active competition set")
        return WorkspaceManager(basedir, comp)

    def _ctfd_platform(competition: str | None = None):
        from ctfx.managers.platform.ctfd import CTFdPlatform

        wm = _wm(competition)
        data = wm.load_ctf_json()
        if data.get("platform") != "ctfd":
            raise ValueError("Competition platform is not CTFd")

        url = data.get("url") or ""
        token = data.get("team_token") or None
        cookies = data.get("team_cookies") or None
        if not url or (not token and not cookies):
            raise ValueError("Set url and team_token or team_cookies first")

        return CTFdPlatform(url, token=token, cookies=cookies), data

    @mcp.tool()
    def list_competitions() -> list[dict[str, Any]]:
        """List all competitions in the CTFx workspace."""
        return WorkspaceManager.list_competitions(basedir)

    @mcp.tool()
    def get_competition(competition: str | None = None) -> dict[str, Any]:
        """Get metadata for the active (or specified) competition."""
        return _wm(competition).load_ctf_json()

    @mcp.tool()
    def list_challenges(
        competition: str | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List challenges with optional category/status filters."""
        chals = _wm(competition).list_challenges()
        if category:
            chals = [c for c in chals if c["category"].lower() == category.lower()]
        if status:
            chals = [c for c in chals if c["status"].lower() == status.lower()]
        return chals

    @mcp.tool()
    def get_challenge(name: str, competition: str | None = None) -> dict[str, Any]:
        """Get detail for a specific challenge by name."""
        wm = _wm(competition)
        entry = wm.find_challenge(name)
        if entry is None:
            raise ValueError(f"Challenge '{name}' not found")
        return entry

    @mcp.tool()
    def add_challenge(
        name: str,
        category: str,
        competition: str | None = None,
        remote: str | None = None,
        points: int | None = None,
    ) -> dict[str, Any]:
        """Create a new challenge directory and scaffold."""
        from ctfx.managers.scaffold import ScaffoldManager

        wm = _wm(competition)
        chal_dir = wm.create_challenge(category, name)
        ScaffoldManager.generate(category, chal_dir, remote=remote)
        if points is not None:
            data = wm.load_ctf_json()
            key = f"{category}/{name}"
            data["challenges"].setdefault(key, {})["points"] = points
            wm.save_ctf_json(data)
        return wm.find_challenge(name) or {}

    @mcp.tool()
    def set_challenge_status(
        name: str,
        status: str,
        flag: str | None = None,
        competition: str | None = None,
    ) -> str:
        """Update challenge status. Valid: fetched, seen, working, hoard, solved."""
        _wm(competition).set_challenge_status(name, status, flag=flag)
        return f"Updated '{name}' -> {status}"

    @mcp.tool()
    def get_prompt(competition: str | None = None) -> str:
        """Read the current prompt.md for the competition."""
        wm = _wm(competition)
        prompt_path = wm.competition_root() / "prompt.md"
        if not prompt_path.exists():
            return "(prompt.md not found - run `ctfx ai` to generate)"
        return prompt_path.read_text(encoding="utf-8")

    @mcp.tool()
    def platform_status(competition: str | None = None) -> dict[str, Any]:
        """Return a CTFd API status summary for the active competition."""
        platform, _ = _ctfd_platform(competition)
        return platform.get_api_status()

    @mcp.tool()
    def platform_challenges(competition: str | None = None) -> list[dict[str, Any]]:
        """List remote challenges from the configured CTFd instance."""
        platform, _ = _ctfd_platform(competition)
        return platform.fetch_challenges()

    @mcp.tool()
    def platform_scoreboard(competition: str | None = None) -> list[dict[str, Any]]:
        """Return the remote CTFd scoreboard."""
        platform, _ = _ctfd_platform(competition)
        return platform.get_scoreboard()

    @mcp.tool()
    def platform_solves(challenge_id: int, competition: str | None = None) -> list[dict[str, Any]]:
        """Return solve records for a remote CTFd challenge ID."""
        platform, _ = _ctfd_platform(competition)
        return platform.get_challenge_solves(challenge_id)

    @mcp.tool()
    def submit_flag(
        flag: str,
        challenge_name: str,
        competition: str | None = None,
    ) -> dict[str, Any]:
        """Submit a flag to the platform and record it if accepted."""
        wm = _wm(competition)
        data = wm.load_ctf_json()
        platform = data.get("platform", "manual")

        if platform == "manual" or not data.get("submit_api"):
            wm.record_flag(challenge_name, flag)
            return {"result": "recorded_locally", "flag": flag}

        from ctfx.managers.platform.ctfd import CTFdPlatform

        entry = wm.find_challenge(challenge_name)
        if entry is None:
            raise ValueError(f"Challenge '{challenge_name}' not found")

        p = CTFdPlatform(
            data["url"],
            token=data.get("team_token") or None,
            cookies=data.get("team_cookies") or None,
        )
        chals_data = data.get("challenges", {})
        key = entry["key"]
        challenge_id = chals_data.get(key, {}).get("platform_id")
        if challenge_id is None:
            return {"result": "no_platform_id", "hint": "Run ctfx fetch first"}

        response = p.submit_flag(challenge_id, flag)
        if response.get("data", {}).get("status") == "correct":
            wm.record_flag(challenge_name, flag, status="solved")
        return response

    @mcp.tool()
    def run_exploit(
        challenge_name: str,
        competition: str | None = None,
    ) -> dict[str, str]:
        """Run solve/exploit.py for a challenge via the configured Python command."""
        wm = _wm(competition)
        entry = wm.find_challenge(challenge_name)
        if entry is None:
            raise ValueError(f"Challenge '{challenge_name}' not found")
        exploit_path = wm.resolve_path(f"{entry['key']}/solve/exploit.py")
        if not exploit_path.exists():
            raise FileNotFoundError(f"exploit.py not found at {exploit_path}")
        try:
            result = subprocess.run(
                build_command(python_cmd, str(exploit_path)),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": str(result.returncode),
            }
        except subprocess.TimeoutExpired:
            return {"error": "Exploit timed out after 60s"}

    @mcp.tool()
    def list_awd_exploits(
        service: str,
        competition: str | None = None,
    ) -> list[dict[str, Any]]:
        """List AWD exploit files and their metadata for a service."""
        wm = _wm(competition)
        service_dir = wm.resolve_path(service) / "exploits"
        if not service_dir.exists():
            return []
        results = []
        for f in sorted(service_dir.glob("*.py")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta: dict[str, Any] = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            results.append({"file": f.name, **meta})
        return results

    @mcp.tool()
    def get_config() -> dict[str, Any]:
        """Read the current CTFx global configuration (root_token is redacted)."""
        from ctfx.managers.config import ConfigManager
        cfg = ConfigManager.load()
        data = dict(cfg.raw)
        data["root_token"] = "<redacted>"
        return data

    @mcp.tool()
    def set_config(key: str, value: str) -> str:
        """Set a CTFx config value by dot-notation key."""
        from ctfx.commands.config import _SETTABLE
        from ctfx.managers.config import ConfigManager

        if key not in _SETTABLE:
            raise ValueError(
                f"'{key}' is not settable. Settable keys: {sorted(_SETTABLE)}"
            )
        cfg = ConfigManager.load()
        parts = key.split(".")
        current = cfg.raw
        for part in parts[:-1]:
            current = current.get(part, {})
        existing = current.get(parts[-1]) if isinstance(current, dict) else None

        coerced: str | int | None
        if value.lower() == "null":
            coerced = None
        elif isinstance(existing, int):
            coerced = int(value)
        else:
            coerced = value

        cfg.set(*parts, coerced)
        cfg.save()
        return f"Set {key} = {coerced}"

    @mcp.tool()
    def list_awd_patches(
        service: str,
        competition: str | None = None,
    ) -> list[dict[str, Any]]:
        """List AWD patch files and their metadata for a service."""
        wm = _wm(competition)
        service_dir = wm.resolve_path(service) / "patches"
        if not service_dir.exists():
            return []
        results = []
        for f in sorted(service_dir.glob("*.diff")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta: dict[str, Any] = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            results.append({"file": f.name, **meta})
        return results

    @mcp.tool()
    def get_toolkit(
        category: str | None = None,
        tags: list[str] | None = None,
        sets: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return attack tools from the personal toolkit, filtered by category and/or tags.
        Call this at the start of working on a challenge to discover available tools.
        The 'prompt' field of each entry explains when and how to use the tool.
        The 'cmd' field is a template — pass its variables to run_toolkit_tool."""
        from ctfx.managers.toolkit import ToolkitManager
        tm = ToolkitManager.ensure_init()
        return tm.list_tools(category=category, tags=tags, sets=sets)

    @mcp.tool()
    def run_toolkit_tool(
        tool_id: str,
        vars: dict[str, str],
        timeout: int = 60,
    ) -> dict[str, str]:
        """Execute a toolkit entry by ID, substituting template variables in its cmd.
        tool_id may be 'set_id:tool_id' or a bare 'tool_id' (searches active sets).
        vars provides substitution values for placeholders such as {exploit}, {file}, {dir}.
        Returns stdout, stderr, and returncode."""
        from ctfx.managers.toolkit import ToolkitManager
        tm = ToolkitManager.ensure_init()
        try:
            tool = tm.get_tool(tool_id)
        except KeyError as e:
            return {"error": str(e), "stdout": "", "stderr": "", "returncode": "-1"}

        cmd_template = tool.get("cmd", "")
        try:
            expanded = cmd_template.format_map(vars)
        except KeyError as e:
            return {
                "error": f"Missing template variable {e} in cmd: {cmd_template!r}",
                "stdout": "",
                "stderr": "",
                "returncode": "-1",
            }

        try:
            result = subprocess.run(
                build_command(expanded),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": str(result.returncode),
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Tool timed out after {timeout}s", "stdout": "", "stderr": "", "returncode": "-1"}
        except Exception as e:
            return {"error": str(e), "stdout": "", "stderr": "", "returncode": "-1"}

    return mcp
