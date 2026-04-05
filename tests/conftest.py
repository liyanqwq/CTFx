"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctfx.managers.config import ConfigManager, _default_config
from ctfx.managers.workspace import WorkspaceManager


@pytest.fixture
def tmp_basedir(tmp_path: Path) -> Path:
    return tmp_path / "ctf"


@pytest.fixture
def config(tmp_path: Path) -> ConfigManager:
    data = _default_config(str(tmp_path / "ctf"))
    return ConfigManager(data)


@pytest.fixture
def comp_wm(tmp_basedir: Path) -> WorkspaceManager:
    wm = WorkspaceManager(tmp_basedir, "TEST_CTF_2025")
    wm.init_competition("TEST_CTF", 2025, "jeopardy", "manual")
    return wm


@pytest.fixture
def awd_wm(tmp_basedir: Path) -> WorkspaceManager:
    wm = WorkspaceManager(tmp_basedir, "AWD_CTF_2025")
    wm.init_competition("AWD_CTF", 2025, "awd", "manual")
    return wm


@pytest.fixture
def app(comp_wm: WorkspaceManager):
    """FastAPI test app wired to a real temp workspace."""
    from ctfx.server.app import create_app
    import secrets

    token = secrets.token_hex(32)
    return create_app(
        root_token=token,
        token_version=1,
        auth_config={
            "webui_cookie_name": "ctfx_auth",
            "one_time_login_ttl_sec": 60,
            "session_ttl_sec": 86400,
        },
        basedir=comp_wm.basedir,
        active_competition="TEST_CTF_2025",
        python_cmd="python3",
    ), token


@pytest.fixture
def bearer(app):
    _, token = app
    return {"Authorization": f"Bearer {token}"}
