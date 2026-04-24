"""Tests for the ctfx api command group."""

from __future__ import annotations

from click.testing import CliRunner

from ctfx.cli import main
from ctfx.managers.config import ConfigManager
from ctfx.managers.workspace import WorkspaceManager


def _prepare_ctfd_competition(tmp_path):
    cfg = ConfigManager.load()
    cfg.set("basedir", str(tmp_path / "ctf"))
    cfg.active_competition = "TEST_API_2026"
    cfg.save()

    wm = WorkspaceManager(cfg.basedir, "TEST_API_2026")
    wm.init_competition(
        "TEST_API",
        2026,
        "jeopardy",
        "ctfd",
        url="https://ctfd.example",
        team_token="secret-token",
        dir_name="TEST_API_2026",
    )
    return wm


def test_api_test_command_reports_success(tmp_path, monkeypatch):
    _prepare_ctfd_competition(tmp_path)
    monkeypatch.setattr(
        "ctfx.managers.platform.ctfd.CTFdPlatform.fetch_challenges",
        lambda self: [
            {
                "platform_id": 1,
                "name": "warmup",
                "display_name": "Warmup",
                "category": "misc",
                "points": 100,
                "solved_by_me": False,
            }
        ],
    )

    result = CliRunner().invoke(main, ["api", "test"])
    assert result.exit_code == 0
    assert "API OK." in result.output
    assert "1 challenge" in result.output


def test_api_status_command_reports_summary(tmp_path, monkeypatch):
    _prepare_ctfd_competition(tmp_path)
    monkeypatch.setattr(
        "ctfx.managers.platform.ctfd.CTFdPlatform.get_api_status",
        lambda self: {
            "base_url": "https://ctfd.example",
            "auth_mode": "token",
            "authenticated": True,
            "challenge_count": 12,
            "solved_count": 3,
            "scoreboard_entries": 10,
        },
    )

    result = CliRunner().invoke(main, ["api", "status"])
    assert result.exit_code == 0
    assert "https://ctfd.example" in result.output
    assert "token" in result.output
    assert "12" in result.output


def test_api_challenges_command_lists_remote_challenges(tmp_path, monkeypatch):
    _prepare_ctfd_competition(tmp_path)
    monkeypatch.setattr(
        "ctfx.managers.platform.ctfd.CTFdPlatform.fetch_challenges",
        lambda self: [
            {
                "platform_id": 7,
                "name": "baby_pwn",
                "display_name": "Baby Pwn",
                "category": "pwn",
                "points": 500,
                "solved_by_me": True,
            }
        ],
    )

    result = CliRunner().invoke(main, ["api", "challenges"])
    assert result.exit_code == 0
    assert "Baby Pwn" in result.output
    assert "pwn" in result.output
    assert "500" in result.output
