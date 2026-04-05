"""Tests for configured process helpers."""

from __future__ import annotations

from ctfx.utils import process


def test_split_command_windows_quoted_path(monkeypatch):
    monkeypatch.setattr(process.sys, "platform", "win32")
    parts = process.split_command('"C:\\Program Files\\Python313\\python.exe" -u')
    assert parts == ["C:\\Program Files\\Python313\\python.exe", "-u"]


def test_split_command_rejects_empty():
    try:
        process.split_command("   ")
    except ValueError as e:
        assert "must not be empty" in str(e)
    else:
        raise AssertionError("Expected ValueError for empty command")
