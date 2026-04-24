"""REST API routes — /api/{competition}/..."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from ctfx.managers.ai import test_connection
from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager, VALID_STATUSES
from ctfx.managers.scaffold import ScaffoldManager
from ctfx.server.auth import BearerAuth
from ctfx.utils.process import build_command

router = APIRouter(prefix="/api", tags=["api"])


def _get_wm(request: Request, competition: str) -> WorkspaceManager:
    basedir: Path = request.app.state.basedir
    wm = WorkspaceManager(basedir, competition)
    if not wm.ctf_json_path().exists():
        raise HTTPException(status_code=404, detail=f"Competition '{competition}' not found")
    return wm


def _get_ctfd_platform(wm: WorkspaceManager) -> tuple["Any", dict[str, Any]]:
    data = wm.load_ctf_json()
    if data.get("platform") != "ctfd":
        raise HTTPException(status_code=400, detail="Competition platform is not CTFd")

    from ctfx.managers.platform.ctfd import CTFdPlatform

    url = data.get("url") or ""
    token = data.get("team_token") or None
    cookies = data.get("team_cookies") or None
    if not url or (not token and not cookies):
        raise HTTPException(
            status_code=400,
            detail="Competition URL and team_token or team_cookies must be configured",
        )
    return CTFdPlatform(url, token=token, cookies=cookies), data


def _get_challenge_meta(wm: WorkspaceManager, cat: str, chal: str) -> tuple[str, dict[str, Any]]:
    key = f"{cat}/{chal}"
    data = wm.load_ctf_json()
    entry = data.get("challenges", {}).get(key)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Challenge '{cat}/{chal}' not found")
    return key, entry


def _get_challenge_dir(wm: WorkspaceManager, cat: str, chal: str) -> Path:
    try:
        chal_dir = wm.challenge_dir(cat, chal)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not chal_dir.exists():
        raise HTTPException(status_code=404, detail=f"Challenge '{cat}/{chal}' not found")
    return chal_dir


_SETTABLE_KEYS = {
    "basedir",
    "terminal.cli_cmd",
    "terminal.editor_cmd",
    "terminal.wsl_distro",
    "terminal.python_cmd",
    "terminal.explorer_cmd",
    "terminal.file_manager_cmd",
    "serve.host",
    "serve.port",
    "auth.webui_cookie_name",
    "auth.one_time_login_ttl_sec",
    "auth.session_ttl_sec",
    "ai_provider",
    "ai_api_key",
    "ai_openai_base_url",
    "ai_anthropic_base_url",
    "anthropic_api_key",
    "ai_model",
    "ai_endpoint",
}

_EDITABLE_COMPETITION_FIELDS = {
    "name",
    "year",
    "flag_format",
    "team_name",
    "team_token",
    "team_cookies",
    "mode",
    "platform",
    "url",
    "submit_api",
}


@router.get("/config")
def get_config(_: BearerAuth, request: Request) -> dict[str, Any]:
    import json as _json
    config_path: Path = request.app.state.config_path
    data = _json.loads(config_path.read_text(encoding="utf-8"))
    data.pop("root_token", None)
    return data


class ConfigPatch(BaseModel):
    key: str
    value: Any


@router.post("/config/ai-test")
def ai_test(_: BearerAuth, request: Request) -> dict[str, Any]:
    cfg = ConfigManager.load()
    try:
        return test_connection(cfg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/config")
def patch_config(_: BearerAuth, request: Request, body: ConfigPatch) -> dict[str, Any]:
    if body.key not in _SETTABLE_KEYS:
        raise HTTPException(
            status_code=422,
            detail=f"'{body.key}' is not settable. Settable keys: {sorted(_SETTABLE_KEYS)}",
        )
    import json as _json, os, tempfile
    config_path: Path = request.app.state.config_path
    data = _json.loads(config_path.read_text(encoding="utf-8"))
    parts = body.key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = body.value
    dir_ = config_path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, config_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if body.key == "basedir" and body.value:
        Path(str(body.value)).expanduser().mkdir(parents=True, exist_ok=True)
    return {"ok": True, "key": body.key, "value": body.value}


@router.get("/competitions")
def list_competitions_endpoint(_: BearerAuth, request: Request) -> list[dict]:
    basedir: Path = request.app.state.basedir
    return WorkspaceManager.list_competitions(basedir)


class CreateCompetitionBody(BaseModel):
    name: str
    year: int
    mode: str = "jeopardy"
    platform: str = "manual"
    url: str | None = None
    flag_format: str | None = None
    team_name: str | None = None
    team_token: str | None = None


class UpdateCompetitionBody(BaseModel):
    name: str | None = None
    year: int | None = None
    flag_format: str | None = None
    team_name: str | None = None
    team_token: str | None = None
    team_cookies: str | None = None
    mode: str | None = None
    platform: str | None = None
    url: str | None = None
    submit_api: bool | None = None


class UpdateChallengeBody(BaseModel):
    points: int | None = None
    remote: str | None = None
    extra_info: str | None = None


@router.put("/competitions/active")
def set_active_competition(
    _: BearerAuth, request: Request, body: dict
) -> dict[str, Any]:
    """Persist the active competition to config.json and update server state."""
    comp = body.get("competition", "")
    if not comp:
        raise HTTPException(status_code=422, detail="'competition' field required")
    basedir: Path = request.app.state.basedir
    wm = WorkspaceManager(basedir, comp)
    if not wm.ctf_json_path().exists():
        raise HTTPException(status_code=404, detail=f"Competition '{comp}' not found")

    request.app.state.active_competition = comp
    request.app.state.active_competition_ref["value"] = comp

    import json as _json, os, tempfile
    config_path: Path = request.app.state.config_path
    try:
        data = _json.loads(config_path.read_text(encoding="utf-8"))
        data["active_competition"] = comp
        dir_ = config_path.parent
        fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, config_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")

    return {"active_competition": comp}


@router.post("/competitions")
def create_competition_endpoint(
    _: BearerAuth, request: Request, body: CreateCompetitionBody
) -> dict[str, Any]:
    basedir: Path = request.app.state.basedir
    basedir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]", "_", body.name.lower()).strip("_")
    comp_dir = f"{safe_name}_{body.year}"
    if (basedir / comp_dir).exists():
        raise HTTPException(status_code=409, detail=f"Competition '{comp_dir}' already exists")
    wm = WorkspaceManager(basedir, comp_dir)
    root = wm.init_competition(
        name=body.name,
        year=body.year,
        mode=body.mode,
        platform=body.platform,
        url=body.url,
        flag_format=body.flag_format,
        team_name=body.team_name,
        team_token=body.team_token,
        dir_name=comp_dir,
    )
    return {
        "dir": root.name,
        "name": body.name,
        "year": body.year,
        "mode": body.mode,
        "platform": body.platform,
        "solved": 0,
        "total": 0,
    }


@router.get("/{competition}/info")
def get_info(_: BearerAuth, request: Request, competition: str) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    return wm.load_ctf_json()


@router.put("/{competition}/info")
def update_info(
    _: BearerAuth,
    request: Request,
    competition: str,
    body: UpdateCompetitionBody,
) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    data = wm.load_ctf_json()
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key not in _EDITABLE_COMPETITION_FIELDS:
            raise HTTPException(status_code=422, detail=f"Field '{key}' is not editable")
        data[key] = value
    wm.save_ctf_json(data)
    return data


@router.get("/{competition}/challenges")
def list_challenges(_: BearerAuth, request: Request, competition: str) -> list[dict]:
    wm = _get_wm(request, competition)
    return wm.list_challenges()


@router.get("/{competition}/challenges/{cat}/{chal}")
def get_challenge(
    _: BearerAuth, request: Request, competition: str, cat: str, chal: str
) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    key, entry = _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    return {
        "key": key,
        "name": chal,
        "category": cat,
        "status": entry.get("status", "fetched"),
        "points": entry.get("points"),
        "flag": entry.get("flag"),
        "remote": entry.get("remote"),
        "solved_at": entry.get("solved_at"),
        "extra_info": entry.get("extra_info"),
        "attachments": [
            {
                "name": p.name,
                "path": p.relative_to(chal_dir / "src").as_posix(),
                "size": p.stat().st_size,
            }
            for p in sorted((chal_dir / "src").rglob("*"))
            if p.is_file()
        ],
    }


class StatusUpdate(BaseModel):
    status: str
    flag: str | None = None


@router.post("/{competition}/challenges/{cat}/{chal}/status")
def update_status(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    body: StatusUpdate,
) -> dict[str, str]:
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of {VALID_STATUSES}",
        )
    wm = _get_wm(request, competition)
    try:
        wm.set_challenge_status(chal, body.status, flag=body.flag)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": "true"}


class FlagUpdate(BaseModel):
    flag: str


@router.put("/{competition}/challenges/{cat}/{chal}/meta")
def update_challenge_meta(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    body: UpdateChallengeBody,
) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    key, entry = _get_challenge_meta(wm, cat, chal)
    data = wm.load_ctf_json()
    current = data.setdefault("challenges", {}).setdefault(key, {})
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        current[field] = value
    wm.save_ctf_json(data)
    return {
        "key": key,
        "name": chal,
        "category": cat,
        "status": current.get("status", entry.get("status", "fetched")),
        "points": current.get("points"),
        "flag": current.get("flag"),
        "remote": current.get("remote"),
        "solved_at": current.get("solved_at"),
        "extra_info": current.get("extra_info"),
    }


@router.post("/{competition}/challenges/{cat}/{chal}/flag")
def record_flag(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    body: FlagUpdate,
) -> dict[str, str]:
    wm = _get_wm(request, competition)
    try:
        wm.record_flag(chal, body.flag)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": "true"}


@router.post("/{competition}/challenges/{cat}/{chal}/submit")
def submit_flag(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    body: FlagUpdate,
) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    key, _ = _get_challenge_meta(wm, cat, chal)
    data = wm.load_ctf_json()
    if data.get("platform", "manual") == "manual" or not data.get("submit_api"):
        raise HTTPException(status_code=400, detail="Platform submission is not enabled for this competition")

    platform_id = data.get("challenges", {}).get(key, {}).get("platform_id")
    if platform_id is None:
        raise HTTPException(status_code=400, detail="platform_id missing; run fetch first")

    from ctfx.managers.platform.ctfd import CTFdPlatform

    token = data.get("team_token") or None
    cookies = data.get("team_cookies") or None
    if not data.get("url") or (not token and not cookies):
        raise HTTPException(status_code=400, detail="Competition URL and team_token or team_cookies must be configured")

    try:
        platform = CTFdPlatform(data["url"], token=token, cookies=cookies)
        response = platform.submit_flag(platform_id, body.flag)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission failed: {e}")

    if response.get("data", {}).get("status") == "correct":
        wm.record_flag(chal, body.flag, status="solved")
    return response


@router.get("/{competition}/challenges/{cat}/{chal}/chal.md", response_class=PlainTextResponse)
def get_chal_md(
    _: BearerAuth, request: Request, competition: str, cat: str, chal: str
) -> str:
    wm = _get_wm(request, competition)
    _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    md_path = chal_dir / "chal.md"
    if not md_path.exists():
        return f"# {chal}\n\nNo description available.\n"
    return md_path.read_text(encoding="utf-8")


@router.put("/{competition}/challenges/{cat}/{chal}/chal.md")
def put_chal_md(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    content: str = Body(..., media_type="text/plain"),
) -> dict[str, str]:
    wm = _get_wm(request, competition)
    _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    (chal_dir / "chal.md").write_text(content, encoding="utf-8")
    return {"ok": "true"}


@router.get("/{competition}/challenges/{cat}/{chal}/wp.md", response_class=PlainTextResponse)
def get_wp_md(
    _: BearerAuth, request: Request, competition: str, cat: str, chal: str
) -> str:
    wm = _get_wm(request, competition)
    _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    wp_path = chal_dir / "wp.md"
    if not wp_path.exists():
        return ""
    return wp_path.read_text(encoding="utf-8")


@router.put("/{competition}/challenges/{cat}/{chal}/wp.md")
def put_wp_md(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    content: str = Body(..., media_type="text/plain"),
) -> dict[str, str]:
    wm = _get_wm(request, competition)
    _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    chal_dir.mkdir(parents=True, exist_ok=True)
    (chal_dir / "wp.md").write_text(content, encoding="utf-8")
    return {"ok": "true"}


@router.get("/{competition}/challenges/{cat}/{chal}/attachments")
def list_attachments(
    _: BearerAuth, request: Request, competition: str, cat: str, chal: str
) -> list[dict[str, Any]]:
    wm = _get_wm(request, competition)
    _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    src_dir = chal_dir / "src"
    if not src_dir.exists():
        return []
    return [
        {
            "name": path.name,
            "path": path.relative_to(src_dir).as_posix(),
            "size": path.stat().st_size,
        }
        for path in sorted(src_dir.rglob("*"))
        if path.is_file()
    ]


@router.get("/{competition}/challenges/{cat}/{chal}/attachments/{attachment_path:path}")
def download_attachment(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
    attachment_path: str,
) -> FileResponse:
    wm = _get_wm(request, competition)
    _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    src_dir = (chal_dir / "src").resolve()
    target = (src_dir / attachment_path).resolve()
    if src_dir != target and src_dir not in target.parents:
        raise HTTPException(status_code=422, detail="Attachment path escapes src directory")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(target, filename=target.name)


@router.get("/{competition}/awd/hosts/{service}")
def list_awd_hosts(
    _: BearerAuth, request: Request, competition: str, service: str
) -> list[dict]:
    wm = _get_wm(request, competition)
    try:
        service_dir = wm.resolve_path(service)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    hostlist = service_dir / "hostlist.txt"
    if not hostlist.exists():
        return []
    results = []
    for i, line in enumerate(hostlist.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            results.append({"team": parts[0], "ip": parts[1]})
        else:
            results.append({"team": f"team_{i + 1}", "ip": parts[0]})
    return results


class AddChallengeBody(BaseModel):
    name: str
    category: str
    description: str | None = None
    points: int | None = None
    remote: str | None = None


@router.post("/{competition}/challenges")
def add_challenge(
    _: BearerAuth,
    request: Request,
    competition: str,
    body: AddChallengeBody,
) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    try:
        chal_dir = wm.create_challenge(body.category, body.name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    ScaffoldManager.generate(body.category, chal_dir, remote=body.remote)

    if body.points is not None or body.description is not None or body.remote is not None:
        data = wm.load_ctf_json()
        key = f"{body.category}/{body.name}"
        entry = data["challenges"].get(key, {})
        if body.points is not None:
            entry["points"] = body.points
        if body.remote is not None:
            entry["remote"] = body.remote
        if body.description is not None:
            (chal_dir / "chal.md").write_text(
                f"# {body.name}\n\n{body.description}\n", encoding="utf-8"
            )
        data["challenges"][key] = entry
        wm.save_ctf_json(data)

    return wm.find_challenge(body.name) or {}


@router.delete("/{competition}/challenges/{cat}/{chal}")
def delete_challenge(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
) -> dict[str, str]:
    wm = _get_wm(request, competition)
    key, _ = _get_challenge_meta(wm, cat, chal)
    chal_dir = _get_challenge_dir(wm, cat, chal)
    if chal_dir.exists():
        import shutil
        shutil.rmtree(chal_dir)
    data = wm.load_ctf_json()
    data.get("challenges", {}).pop(key, None)
    wm.save_ctf_json(data)
    return {"ok": "true"}


@router.post("/{competition}/fetch")
def trigger_fetch(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str | None = None,
    chal: str | None = None,
) -> dict[str, str]:
    wm = _get_wm(request, competition)
    data = wm.load_ctf_json()
    platform = data.get("platform", "manual")
    if platform == "manual":
        raise HTTPException(status_code=400, detail="Manual platform does not support fetch")

    from ctfx.managers.platform.ctfd import CTFdPlatform

    token = data.get("team_token", "")
    url = data.get("url", "")
    if not url or not token:
        raise HTTPException(status_code=400, detail="Platform URL or team token not configured")

    p = CTFdPlatform(url, token)
    challenges = p.fetch_challenges()
    created = 0
    for ch in challenges:
        ch_cat = ch.get("category", "misc").lower().replace(" ", "_")
        ch_name = ch.get("name", "").lower().replace(" ", "_")
        if cat and ch_cat != cat:
            continue
        if chal and ch_name != chal:
            continue
        key = f"{ch_cat}/{ch_name}"
        if key not in data.get("challenges", {}):
            try:
                chal_dir = wm.create_challenge(ch_cat, ch_name)
            except ValueError:
                continue
            ScaffoldManager.generate(ch_cat, chal_dir, remote=ch.get("connection_info") or None)
            created += 1

    return {"created": str(created)}


@router.get("/{competition}/platform/status")
def platform_status(_: BearerAuth, request: Request, competition: str) -> dict[str, Any]:
    wm = _get_wm(request, competition)
    platform, _ = _get_ctfd_platform(wm)
    try:
        return platform.get_api_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to query platform API: {e}")


@router.get("/{competition}/platform/challenges")
def platform_challenges(_: BearerAuth, request: Request, competition: str) -> list[dict[str, Any]]:
    wm = _get_wm(request, competition)
    platform, _ = _get_ctfd_platform(wm)
    try:
        return platform.fetch_challenges()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch remote challenges: {e}")


@router.get("/{competition}/platform/scoreboard")
def platform_scoreboard(_: BearerAuth, request: Request, competition: str) -> list[dict[str, Any]]:
    wm = _get_wm(request, competition)
    platform, _ = _get_ctfd_platform(wm)
    try:
        return platform.get_scoreboard()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch remote scoreboard: {e}")


@router.get("/{competition}/platform/challenges/{challenge_id}/solves")
def platform_challenge_solves(
    _: BearerAuth,
    request: Request,
    competition: str,
    challenge_id: int,
) -> list[dict[str, Any]]:
    wm = _get_wm(request, competition)
    platform, _ = _get_ctfd_platform(wm)
    try:
        return platform.get_challenge_solves(challenge_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch remote solves: {e}")


@router.get("/{competition}/awd/exploits/{service}")
def list_awd_exploits(
    _: BearerAuth, request: Request, competition: str, service: str
) -> list[dict]:
    wm = _get_wm(request, competition)
    try:
        service_dir = wm.resolve_path(service) / "exploits"
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not service_dir.exists():
        return []
    results = []
    import json
    for f in sorted(service_dir.glob("*.py")):
        meta_path = f.with_suffix("").with_suffix(".meta.json")
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        results.append({"file": f.name, **meta})
    return results


@router.get("/{competition}/awd/patches/{service}")
def list_awd_patches(
    _: BearerAuth, request: Request, competition: str, service: str
) -> list[dict]:
    wm = _get_wm(request, competition)
    try:
        service_dir = wm.resolve_path(service) / "patches"
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not service_dir.exists():
        return []
    results = []
    import json
    for f in sorted(service_dir.glob("*.diff")):
        meta_path = f.with_suffix("").with_suffix(".meta.json")
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        results.append({"file": f.name, **meta})
    return results


# ---------------------------------------------------------------------------
# Toolkit endpoints — /api/toolkit/...
# ---------------------------------------------------------------------------

toolkit_router = APIRouter(prefix="/toolkit", tags=["toolkit"])


def _toolkit() -> "Any":  # ToolkitManager, imported lazily
    from ctfx.managers.toolkit import ToolkitManager
    return ToolkitManager.ensure_init()


class CreateSetBody(BaseModel):
    id: str
    name: str


class ToolBody(BaseModel):
    id: str
    name: str
    cmd: str
    categories: list[str] = []
    tags: list[str] = []
    description: str = ""
    prompt: str = ""
    ref: str | None = None


class ToolPatch(BaseModel):
    name: str | None = None
    cmd: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None
    description: str | None = None
    prompt: str | None = None
    ref: str | None = None


class ImportBody(BaseModel):
    url: str | None = None
    data: dict | None = None
    alias: str | None = None


@toolkit_router.get("/sets")
def tk_list_sets(_: BearerAuth) -> list[dict]:
    return _toolkit().list_sets()


@toolkit_router.post("/sets", status_code=201)
def tk_create_set(_: BearerAuth, body: CreateSetBody) -> dict:
    try:
        _toolkit().create_set(body.id, body.name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": body.id, "name": body.name}


@toolkit_router.delete("/sets/{set_id}")
def tk_remove_set(_: BearerAuth, set_id: str) -> dict:
    try:
        _toolkit().remove_set(set_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}


@toolkit_router.post("/sets/{set_id}/enable")
def tk_enable_set(_: BearerAuth, set_id: str) -> dict:
    try:
        _toolkit().enable_set(set_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@toolkit_router.post("/sets/{set_id}/disable")
def tk_disable_set(_: BearerAuth, set_id: str) -> dict:
    try:
        _toolkit().disable_set(set_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}


@toolkit_router.post("/import", status_code=201)
def tk_import(_: BearerAuth, body: ImportBody) -> dict:
    import urllib.request as _ur
    import json as _json

    if body.data:
        raw_data = body.data
        if body.url:
            raw_data.setdefault("source", body.url)
    elif body.url:
        try:
            with _ur.urlopen(body.url, timeout=15) as resp:  # noqa: S310
                raw_data = _json.loads(resp.read().decode("utf-8"))
            raw_data.setdefault("source", body.url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")
    else:
        raise HTTPException(status_code=422, detail="Provide either 'url' or 'data'")

    try:
        set_id = _toolkit().import_set(raw_data, body.alias)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": set_id}


@toolkit_router.get("/export/{set_id}")
def tk_export(_: BearerAuth, set_id: str) -> dict:
    try:
        return _toolkit().export_set(set_id)
    except (KeyError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@toolkit_router.get("/tools")
def tk_list_tools(
    _: BearerAuth,
    cat: str | None = None,
    tag: str | None = None,
    set: str | None = None,
) -> list[dict]:
    tags = [tag] if tag else None
    sets = [set] if set else None
    return _toolkit().list_tools(category=cat, tags=tags, sets=sets)


@toolkit_router.post("/tools", status_code=201)
def tk_add_tool(
    _: BearerAuth,
    body: ToolBody,
    set_id: str = "personal",
) -> dict:
    tool = body.model_dump()
    try:
        _toolkit().add_tool(set_id, tool)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return tool


@toolkit_router.patch("/tools/{tool_id}")
def tk_update_tool(
    _: BearerAuth,
    tool_id: str,
    body: ToolPatch,
    set_id: str | None = None,
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    try:
        _toolkit().update_tool(tool_id, updates, set_id)
        return _toolkit().get_tool(tool_id, set_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@toolkit_router.delete("/tools/{tool_id}")
def tk_remove_tool(
    _: BearerAuth,
    tool_id: str,
    set_id: str | None = None,
) -> dict:
    try:
        sid = _toolkit().remove_tool(tool_id, set_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "set": sid}


router.include_router(toolkit_router)


@router.post("/{competition}/challenges/{cat}/{chal}/run")
def run_exploit(
    _: BearerAuth,
    request: Request,
    competition: str,
    cat: str,
    chal: str,
) -> dict[str, str]:
    wm = _get_wm(request, competition)
    python_cmd: str = request.app.state.python_cmd
    try:
        exploit_path = wm.resolve_path(f"{cat}/{chal}/solve/exploit.py")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not exploit_path.exists():
        raise HTTPException(status_code=404, detail="exploit.py not found")

    try:
        result = subprocess.run(
            build_command(python_cmd, str(exploit_path)),
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(exploit_path.parent),
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": str(result.returncode),
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Exploit timed out after 60s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
