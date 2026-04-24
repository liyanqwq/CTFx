"""Integration tests for FastAPI REST routes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ctfx.managers.workspace import WorkspaceManager
from ctfx.server.app import create_app


@pytest.fixture
def workspace(tmp_path: Path):
    wm = WorkspaceManager(tmp_path, "TEST_2025")
    wm.init_competition("TEST", 2025, "jeopardy", "manual")
    wm.create_challenge("pwn", "baby_pwn")
    wm.create_challenge("crypto", "rsa")
    return wm, tmp_path


@pytest.fixture
def token():
    return secrets.token_hex(32)


@pytest.fixture
def test_app(workspace, token):
    _, basedir = workspace
    return create_app(
        root_token=token,
        token_version=1,
        auth_config={
            "webui_cookie_name": "ctfx_auth",
            "one_time_login_ttl_sec": 60,
            "session_ttl_sec": 86400,
        },
        basedir=basedir,
        active_competition="TEST_2025",
        python_cmd="python3",
    )


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_ticket(root_token: str, version: int, ttl: int) -> str:
    nonce = secrets.token_hex(16)
    expires = int(time.time()) + ttl
    payload = f"{nonce}.{expires}.{version}"
    sig = hmac.new(root_token.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


@pytest.mark.asyncio
async def test_no_auth_returns_401(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/TEST_2025/info")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_token_returns_401(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/TEST_2025/info", headers={"Authorization": "Bearer wrongtoken"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_returns_200(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/TEST_2025/info", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "TEST"


@pytest.mark.asyncio
async def test_one_time_login_sets_cookie(test_app, token):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        ticket = make_ticket(token, 1, 60)
        r = await c.get(f"/auth/webui/one-time-login?ticket={ticket}&next=/")
        assert r.status_code == 302
        assert "ctfx_auth" in r.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_one_time_login_single_use(test_app, token):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        ticket = make_ticket(token, 1, 60)
        r1 = await c.get(f"/auth/webui/one-time-login?ticket={ticket}&next=/")
        assert r1.status_code == 302
        r2 = await c.get(f"/auth/webui/one-time-login?ticket={ticket}&next=/")
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_expired_ticket_rejected(test_app, token):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        ticket = make_ticket(token, 1, -1)
        r = await c.get(f"/auth/webui/one-time-login?ticket={ticket}&next=/")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_version_ticket_rejected(test_app, token):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        ticket = make_ticket(token, 99, 60)
        r = await c.get(f"/auth/webui/one-time-login?ticket={ticket}&next=/")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_open_redirect_blocked(test_app, token):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        ticket = make_ticket(token, 1, 60)
        r = await c.get(f"/auth/webui/one-time-login?ticket={ticket}&next=https://evil.com")
        assert r.status_code == 302
        assert r.headers["location"] == "/"


@pytest.mark.asyncio
async def test_list_challenges(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/TEST_2025/challenges", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        names = {ch["name"] for ch in data}
        assert "baby_pwn" in names
        assert "rsa" in names


@pytest.mark.asyncio
async def test_get_challenge(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/TEST_2025/challenges/pwn/baby_pwn", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "baby_pwn"


@pytest.mark.asyncio
async def test_get_challenge_not_found(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/TEST_2025/challenges/pwn/ghost", headers=auth_headers)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_status(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/TEST_2025/challenges/pwn/baby_pwn/status",
            json={"status": "working"},
            headers=auth_headers,
        )
        assert r.status_code == 200

        r2 = await c.get("/api/TEST_2025/challenges/pwn/baby_pwn", headers=auth_headers)
        assert r2.json()["status"] == "working"


@pytest.mark.asyncio
async def test_update_status_invalid(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/TEST_2025/challenges/pwn/baby_pwn/status",
            json={"status": "hacked"},
            headers=auth_headers,
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_record_flag(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/TEST_2025/challenges/crypto/rsa/flag",
            json={"flag": "flag{test123}"},
            headers=auth_headers,
        )
        assert r.status_code == 200

        r2 = await c.get("/api/TEST_2025/challenges/crypto/rsa", headers=auth_headers)
        assert r2.json()["flag"] == "flag{test123}"
        assert r2.json()["status"] == "solved"


@pytest.mark.asyncio
async def test_add_challenge_api(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/TEST_2025/challenges",
            json={"name": "new_web", "category": "web", "points": 200},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "new_web"


@pytest.mark.asyncio
async def test_create_competition_persists_team_token(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/competitions",
            json={
                "name": "Remote CTF",
                "year": 2026,
                "mode": "jeopardy",
                "platform": "ctfd",
                "url": "https://ctfd.example",
                "team_token": "secret-token",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["dir"] == "remote_ctf_2026"

    created = Path(test_app.state.basedir) / "remote_ctf_2026" / "ctf.json"
    assert created.exists()
    assert "secret-token" in created.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_patch_config_accepts_ai_provider(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch(
            "/api/config",
            json={"key": "ai_provider", "value": "anthropic"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["value"] == "anthropic"


@pytest.mark.asyncio
async def test_ai_test_endpoint(test_app, auth_headers, monkeypatch):
    def fake_ai_test(_cfg):
        return {
            "ok": True,
            "provider": "openai",
            "model": "gpt-5.4",
            "base_url": "https://api.example.test/v1",
            "text": "OK",
        }

    monkeypatch.setattr("ctfx.server.api.test_connection", fake_ai_test)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/config/ai-test", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["text"] == "OK"


@pytest.mark.asyncio
async def test_add_challenge_rejects_path_escape(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/TEST_2025/challenges",
            json={"name": "../escape", "category": "web"},
            headers=auth_headers,
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_competition_not_found(test_app, auth_headers):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/FAKE_2099/info", headers=auth_headers)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_set_active_competition_updates_mcp(test_app, auth_headers, workspace):
    _, basedir = workspace
    wm2 = WorkspaceManager(basedir, "SECOND_2025")
    wm2.init_competition("SECOND", 2025, "jeopardy", "manual")

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.put(
            "/api/competitions/active",
            json={"competition": "SECOND_2025"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    mcp_result = test_app.state.mcp_server.call_tool("get_competition", {})
    assert mcp_result["name"] == "SECOND"
