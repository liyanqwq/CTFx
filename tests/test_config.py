"""Tests for ConfigManager."""

from __future__ import annotations

from pathlib import Path

from ctfx.managers.config import ConfigManager, _default_config, _migrate, SCHEMA_VERSION


def test_default_config_has_required_keys(tmp_path):
    data = _default_config(str(tmp_path))
    assert "root_token" in data
    assert "token_version" in data
    assert len(data["root_token"]) == 64
    assert data["token_version"] == 1
    assert data["schema_version"] == SCHEMA_VERSION
    assert "serve" in data
    assert data["serve"]["port"] == 8694
    assert "auth" in data


def test_migrate_backfills_missing_fields():
    minimal = {"basedir": "~/ctf", "root_token": "abc"}
    migrated = _migrate(minimal)
    assert migrated["schema_version"] == SCHEMA_VERSION
    assert migrated["token_version"] == 1
    assert "auth" in migrated


def test_get_nested(config: ConfigManager):
    assert config.get("serve", "port") == 8694
    assert config.get("serve", "host") == "127.0.0.1"
    assert config.get("nonexistent", default="fallback") == "fallback"


def test_set_nested(config: ConfigManager):
    config.set("serve", "port", 9000)
    assert config.serve_port == 9000


def test_rotate_token(config: ConfigManager):
    old_token = config.root_token
    old_version = config.token_version
    new_token = config.rotate_token()
    assert new_token != old_token
    assert len(new_token) == 64
    assert config.token_version == old_version + 1
    assert config.root_token == new_token


def test_save_and_reload(tmp_path: Path, monkeypatch):
    import ctfx.managers.config as cfg_module
    monkeypatch.setattr(cfg_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", tmp_path / "config.json")

    data = _default_config(str(tmp_path / "ctf"))
    cfg = ConfigManager(data)
    cfg.save()

    loaded = ConfigManager.load()
    assert loaded.root_token == cfg.root_token
    assert loaded.serve_port == cfg.serve_port


def test_active_competition(config: ConfigManager):
    assert config.active_competition is None
    config.active_competition = "HKCERT_CTF_2025"
    assert config.active_competition == "HKCERT_CTF_2025"
