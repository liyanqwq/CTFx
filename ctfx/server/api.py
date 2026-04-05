"""REST API routes — /api/{competition}/..."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

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
