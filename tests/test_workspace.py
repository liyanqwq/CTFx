"""Tests for WorkspaceManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctfx.managers.workspace import WorkspaceManager


def test_init_competition_creates_ctf_json(comp_wm: WorkspaceManager):
    assert comp_wm.ctf_json_path().exists()
    data = comp_wm.load_ctf_json()
    assert data["name"] == "TEST_CTF"
    assert data["year"] == 2025
    assert data["mode"] == "jeopardy"


def test_init_competition_persists_team_token(tmp_basedir: Path):
    wm = WorkspaceManager(tmp_basedir, "TOKEN_CTF_2025")
    wm.init_competition("TOKEN_CTF", 2025, "jeopardy", "ctfd", team_token="secret-token")
    data = wm.load_ctf_json()
    assert data["team_token"] == "secret-token"


def test_create_challenge_creates_dirs(comp_wm: WorkspaceManager):
    chal_dir = comp_wm.create_challenge("pwn", "baby_pwn")
    assert (chal_dir / "src").is_dir()
    assert (chal_dir / "solve").is_dir()
    assert (chal_dir / "wp.md").exists()
    assert (chal_dir / "chal.md").exists()


def test_create_challenge_registers_in_ctf_json(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("crypto", "rsa_warmup")
    data = comp_wm.load_ctf_json()
    assert "crypto/rsa_warmup" in data["challenges"]
    assert data["challenges"]["crypto/rsa_warmup"]["status"] == "seen"


def test_list_challenges(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("pwn", "baby_pwn")
    comp_wm.create_challenge("web", "xss_fun")
    chals = comp_wm.list_challenges()
    names = {c["name"] for c in chals}
    assert "baby_pwn" in names
    assert "xss_fun" in names


def test_find_challenge_case_insensitive(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("pwn", "baby_pwn")
    assert comp_wm.find_challenge("BABY_PWN") is not None
    assert comp_wm.find_challenge("nonexistent") is None


def test_set_challenge_status(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("pwn", "baby_pwn")
    comp_wm.set_challenge_status("baby_pwn", "working")
    chals = comp_wm.list_challenges()
    assert chals[0]["status"] == "working"


def test_set_challenge_status_solved_records_flag(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("crypto", "rsa")
    comp_wm.set_challenge_status("rsa", "solved", flag="flag{test}")
    data = comp_wm.load_ctf_json()
    assert data["challenges"]["crypto/rsa"]["flag"] == "flag{test}"
    assert data["challenges"]["crypto/rsa"]["solved_at"] is not None


def test_set_challenge_status_invalid_raises(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("pwn", "baby_pwn")
    with pytest.raises(ValueError):
        comp_wm.set_challenge_status("baby_pwn", "invalid_status")


def test_remove_challenge(comp_wm: WorkspaceManager):
    comp_wm.create_challenge("misc", "hello")
    comp_wm.remove_challenge("hello")
    assert comp_wm.find_challenge("hello") is None
    assert not (comp_wm.competition_root() / "misc" / "hello").exists()


def test_remove_nonexistent_raises(comp_wm: WorkspaceManager):
    with pytest.raises(KeyError):
        comp_wm.remove_challenge("ghost")


def test_list_competitions(tmp_basedir: Path):
    wm1 = WorkspaceManager(tmp_basedir, "COMP_A_2024")
    wm1.init_competition("COMP_A", 2024, "jeopardy", "manual")
    wm2 = WorkspaceManager(tmp_basedir, "COMP_B_2025")
    wm2.init_competition("COMP_B", 2025, "awd", "ctfd")

    comps = WorkspaceManager.list_competitions(tmp_basedir)
    names = {c["dir"] for c in comps}
    assert "COMP_A_2024" in names
    assert "COMP_B_2025" in names


def test_fuzzy_match():
    items = ["HKCERT_CTF_2025", "RITSEC_CTF_2025", "BSidesHK_2025"]
    assert "HKCERT_CTF_2025" in WorkspaceManager.fuzzy_match("hkcert", items)
    assert "BSidesHK_2025" in WorkspaceManager.fuzzy_match("bsides", items)
    assert WorkspaceManager.fuzzy_match("zzznomatch", items) == []


def test_resolve_path(comp_wm: WorkspaceManager):
    root = comp_wm.competition_root()
    assert comp_wm.resolve_path(None) == root.resolve()
    assert comp_wm.resolve_path("pwn") == root / "pwn"
    assert comp_wm.resolve_path("pwn/baby_pwn") == root / "pwn" / "baby_pwn"
    assert comp_wm.resolve_path("pwn/baby_pwn/solve") == root / "pwn" / "baby_pwn" / "solve"


def test_resolve_path_rejects_escape(comp_wm: WorkspaceManager):
    with pytest.raises(ValueError):
        comp_wm.resolve_path("../outside")


def test_create_challenge_rejects_path_components(comp_wm: WorkspaceManager):
    with pytest.raises(ValueError):
        comp_wm.create_challenge("pwn", "../baby_pwn")


def test_load_hostlist(awd_wm: WorkspaceManager):
    service_dir = awd_wm.competition_root() / "web"
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "hostlist.txt").write_text(
        "TeamAlpha 10.0.1.1\nTeamBeta  10.0.1.2\n# comment\n",
        encoding="utf-8",
    )
    hosts = awd_wm.load_hostlist("web")
    assert hosts == [("TeamAlpha", "10.0.1.1"), ("TeamBeta", "10.0.1.2")]


def test_load_hostlist_missing(comp_wm: WorkspaceManager):
    assert comp_wm.load_hostlist("nonexistent") == []


def test_to_wsl_path_linux():
    import sys
    if sys.platform == "win32":
        pytest.skip("WSL path test only on Windows")
    p = Path("/home/user/ctf")
    assert WorkspaceManager.to_wsl_path(p) == str(p)
