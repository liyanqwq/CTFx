"""Tests for ToolkitManager and toolkit API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ctfx.managers.toolkit import (
    ToolkitManager,
    TOOLKIT_DIR,
    INDEX_FILE,
    SETS_DIR,
    _validate_tool,
    _validate_set,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def toolkit_dir(tmp_path: Path, monkeypatch) -> Path:
    """Redirect toolkit storage to a temp directory."""
    tk_dir = tmp_path / "toolkit"
    sets_dir = tk_dir / "sets"
    index_file = tk_dir / "index.json"

    monkeypatch.setattr("ctfx.managers.toolkit.TOOLKIT_DIR", tk_dir)
    monkeypatch.setattr("ctfx.managers.toolkit.INDEX_FILE", index_file)
    monkeypatch.setattr("ctfx.managers.toolkit.SETS_DIR", sets_dir)
    return tk_dir


@pytest.fixture
def tm(toolkit_dir: Path) -> ToolkitManager:
    return ToolkitManager.ensure_init()


def _make_tool(tool_id: str = "test-tool", **kwargs) -> dict[str, Any]:
    return {
        "id": tool_id,
        "name": "Test Tool",
        "cmd": "echo {file}",
        "categories": ["misc"],
        "tags": ["test"],
        **kwargs,
    }


def _make_set(set_id: str = "test-set") -> dict[str, Any]:
    return {
        "id": set_id,
        "name": "Test Set",
        "description": "",
        "author": "tester",
        "version": "1.0.0",
        "source": None,
        "tools": [_make_tool()],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_tool_ok():
    _validate_tool(_make_tool())


def test_validate_tool_bad_id():
    with pytest.raises(ValueError, match="Tool id"):
        _validate_tool(_make_tool("Bad ID"))


def test_validate_tool_missing_cmd():
    with pytest.raises(ValueError, match="cmd"):
        _validate_tool({"id": "x", "name": "X", "cmd": ""})


def test_validate_set_ok():
    _validate_set(_make_set())


def test_validate_set_bad_tool():
    bad = _make_set()
    bad["tools"][0]["id"] = "!bad"
    with pytest.raises(ValueError):
        _validate_set(bad)


# ---------------------------------------------------------------------------
# ensure_init
# ---------------------------------------------------------------------------

def test_ensure_init_creates_personal(tm: ToolkitManager, toolkit_dir: Path):
    personal_path = toolkit_dir / "sets" / "personal.json"
    assert personal_path.exists()
    assert "personal" in tm.active_sets


def test_ensure_init_idempotent(toolkit_dir: Path):
    tm1 = ToolkitManager.ensure_init()
    tm2 = ToolkitManager.ensure_init()
    assert tm1.active_sets == tm2.active_sets


# ---------------------------------------------------------------------------
# Set CRUD
# ---------------------------------------------------------------------------

def test_create_set(tm: ToolkitManager):
    tm.create_set("my-set", "My Set")
    sets = {s["id"] for s in tm.list_sets()}
    assert "my-set" in sets


def test_create_set_duplicate(tm: ToolkitManager):
    tm.create_set("dup-set", "Dup")
    with pytest.raises(ValueError, match="already exists"):
        tm.create_set("dup-set", "Dup2")


def test_create_set_invalid_id(tm: ToolkitManager):
    with pytest.raises(ValueError, match="Invalid set id"):
        tm.create_set("Bad Set!", "Bad")


def test_enable_disable_set(tm: ToolkitManager):
    tm.create_set("extra", "Extra")
    assert "extra" not in tm.active_sets
    tm.enable_set("extra")
    assert "extra" in tm.active_sets
    tm.disable_set("extra")
    assert "extra" not in tm.active_sets


def test_disable_pinned_set(tm: ToolkitManager):
    with pytest.raises(ValueError, match="pinned"):
        tm.disable_set("personal")


def test_remove_set(tm: ToolkitManager):
    tm.create_set("gone", "Gone")
    tm.remove_set("gone")
    assert "gone" not in {s["id"] for s in tm.list_sets()}


def test_remove_pinned_set(tm: ToolkitManager):
    with pytest.raises(ValueError, match="pinned"):
        tm.remove_set("personal")


# ---------------------------------------------------------------------------
# Tool CRUD
# ---------------------------------------------------------------------------

def test_add_and_list_tool(tm: ToolkitManager):
    tool = _make_tool("john-zip", categories=["crypto"], tags=["zip"])
    tm.add_tool("personal", tool)
    tools = tm.list_tools()
    ids = [t["id"] for t in tools]
    assert "john-zip" in ids


def test_add_duplicate_tool(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("dup"))
    with pytest.raises(ValueError, match="already exists"):
        tm.add_tool("personal", _make_tool("dup"))


def test_filter_by_category(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("pwn-rop", categories=["pwn"], tags=["rop"]))
    tm.add_tool("personal", _make_tool("john-zip", categories=["crypto"], tags=["zip"]))
    pwn_tools = tm.list_tools(category="pwn")
    assert all(("pwn" in t.get("categories", [])) for t in pwn_tools)
    assert any(t["id"] == "pwn-rop" for t in pwn_tools)
    assert not any(t["id"] == "john-zip" for t in pwn_tools)


def test_filter_by_tag(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("rop-tool", categories=["pwn"], tags=["rop", "x86_64"]))
    results = tm.list_tools(tags=["rop"])
    assert any(t["id"] == "rop-tool" for t in results)
    results2 = tm.list_tools(tags=["heap"])
    assert not any(t["id"] == "rop-tool" for t in results2)


def test_get_tool(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("get-me"))
    tool = tm.get_tool("get-me")
    assert tool["id"] == "get-me"
    assert tool["_set"] == "personal"


def test_get_tool_with_set_prefix(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("prefixed"))
    tool = tm.get_tool("personal:prefixed")
    assert tool["id"] == "prefixed"


def test_get_tool_not_found(tm: ToolkitManager):
    with pytest.raises(KeyError):
        tm.get_tool("nonexistent")


def test_update_tool(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("updatable"))
    tm.update_tool("updatable", {"name": "Updated Name"})
    tool = tm.get_tool("updatable")
    assert tool["name"] == "Updated Name"


def test_remove_tool(tm: ToolkitManager):
    tm.add_tool("personal", _make_tool("removable"))
    tm.remove_tool("removable")
    with pytest.raises(KeyError):
        tm.get_tool("removable")


# ---------------------------------------------------------------------------
# Multi-set merge (first-set-wins on id collision)
# ---------------------------------------------------------------------------

def test_multi_set_merge(tm: ToolkitManager):
    tm.create_set("set-a", "A")
    tm.create_set("set-b", "B")
    tm.enable_set("set-a")
    tm.enable_set("set-b")

    tm.add_tool("set-a", _make_tool("shared", name="From A"))
    tm.add_tool("set-b", _make_tool("shared", name="From B"))
    tm.add_tool("set-b", _make_tool("only-b"))

    # Reload to reflect saved state
    tm2 = ToolkitManager.load()
    tools = tm2.list_tools()
    by_id = {t["id"]: t for t in tools}
    # personal is first in active_sets; set-a and set-b follow
    assert "shared" in by_id
    # "only-b" should be present
    assert "only-b" in by_id


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------

def test_import_export_roundtrip(tm: ToolkitManager, tmp_path: Path):
    data = _make_set("shareable")
    set_id = tm.import_set(data)
    assert set_id == "shareable"
    assert "shareable" in tm.active_sets

    exported = tm.export_set("shareable")
    assert exported["id"] == "shareable"
    assert len(exported["tools"]) == 1


def test_import_with_alias(tm: ToolkitManager):
    data = _make_set("original-id")
    set_id = tm.import_set(data, alias="aliased-id")
    assert set_id == "aliased-id"
    exported = tm.export_set("aliased-id")
    assert exported["id"] == "aliased-id"


def test_import_invalid_schema(tm: ToolkitManager):
    with pytest.raises(ValueError):
        tm.import_set({"id": "!bad", "name": "X", "tools": []})


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def client(app):
    from httpx import AsyncClient, ASGITransport
    fa, token = app
    return AsyncClient(transport=ASGITransport(app=fa), base_url="http://test"), token


@pytest.mark.asyncio
async def test_api_list_sets(client, toolkit_dir):
    ac, token = client
    async with ac:
        resp = await ac.get(
            "/api/toolkit/sets",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert "personal" in ids


@pytest.mark.asyncio
async def test_api_create_and_delete_set(client, toolkit_dir):
    ac, token = client
    headers = {"Authorization": f"Bearer {token}"}
    async with ac:
        resp = await ac.post(
            "/api/toolkit/sets",
            json={"id": "api-set", "name": "API Set"},
            headers=headers,
        )
        assert resp.status_code == 201

        resp2 = await ac.delete("/api/toolkit/sets/api-set", headers=headers)
        assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_api_add_and_list_tool(client, toolkit_dir):
    ac, token = client
    headers = {"Authorization": f"Bearer {token}"}
    tool_data = {
        "id": "api-tool",
        "name": "API Tool",
        "cmd": "echo {file}",
        "categories": ["misc"],
        "tags": [],
    }
    async with ac:
        resp = await ac.post(
            "/api/toolkit/tools?set_id=personal",
            json=tool_data,
            headers=headers,
        )
        assert resp.status_code == 201

        resp2 = await ac.get("/api/toolkit/tools", headers=headers)
        assert resp2.status_code == 200
        ids = [t["id"] for t in resp2.json()]
        assert "api-tool" in ids


@pytest.mark.asyncio
async def test_api_delete_tool(client, toolkit_dir):
    ac, token = client
    headers = {"Authorization": f"Bearer {token}"}
    tool_data = {"id": "del-tool", "name": "Del", "cmd": "rm {file}", "categories": [], "tags": []}
    async with ac:
        await ac.post("/api/toolkit/tools?set_id=personal", json=tool_data, headers=headers)
        resp = await ac.delete("/api/toolkit/tools/del-tool", headers=headers)
        assert resp.status_code == 200
