"""ToolkitManager — global registry of personal attack tools, organised into shareable sets."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

TOOLKIT_DIR = Path("~/.config/ctfx/toolkit").expanduser()
INDEX_FILE = TOOLKIT_DIR / "index.json"
SETS_DIR = TOOLKIT_DIR / "sets"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_id(value: str) -> bool:
    return bool(_ID_RE.match(value))


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _default_index() -> dict[str, Any]:
    return {
        "active_sets": ["personal"],
        "sets": {
            "personal": {"path": "sets/personal.json", "pinned": True},
        },
    }


def _empty_set(set_id: str, name: str) -> dict[str, Any]:
    return {
        "id": set_id,
        "name": name,
        "description": "",
        "author": "",
        "version": "1.0.0",
        "source": None,
        "tools": [],
    }


def _validate_tool(tool: dict[str, Any]) -> None:
    """Raise ValueError if a tool entry is malformed."""
    if not isinstance(tool.get("id"), str) or not _valid_id(tool["id"]):
        raise ValueError(f"Tool id must match [a-z0-9][a-z0-9_-]{{0,63}}, got: {tool.get('id')!r}")
    for field in ("name", "cmd"):
        if not isinstance(tool.get(field), str) or not tool[field].strip():
            raise ValueError(f"Tool field '{field}' must be a non-empty string")
    cats = tool.get("categories", [])
    if not isinstance(cats, list):
        raise ValueError("Tool 'categories' must be a list")
    tags = tool.get("tags", [])
    if not isinstance(tags, list):
        raise ValueError("Tool 'tags' must be a list")


def _validate_set(data: dict[str, Any]) -> None:
    """Raise ValueError if a set JSON is malformed."""
    if not isinstance(data.get("id"), str) or not _valid_id(data["id"]):
        raise ValueError(f"Set id must match [a-z0-9][a-z0-9_-]{{0,63}}, got: {data.get('id')!r}")
    if not isinstance(data.get("name"), str):
        raise ValueError("Set 'name' must be a string")
    if not isinstance(data.get("tools"), list):
        raise ValueError("Set 'tools' must be a list")
    for tool in data["tools"]:
        _validate_tool(tool)


# ---------------------------------------------------------------------------
# ToolkitManager
# ---------------------------------------------------------------------------

class ToolkitManager:
    """Manage toolkit sets stored in ~/.config/ctfx/toolkit/."""

    # ── Bootstrap ──────────────────────────────────────────────────────────

    @classmethod
    def ensure_init(cls) -> "ToolkitManager":
        """Load or initialise the toolkit directory and return an instance."""
        TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
        SETS_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX_FILE.exists():
            _atomic_write(INDEX_FILE, _default_index())
        if not (SETS_DIR / "personal.json").exists():
            _atomic_write(SETS_DIR / "personal.json", _empty_set("personal", "Personal"))
        return cls.load()

    @classmethod
    def load(cls) -> "ToolkitManager":
        index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return cls(index)

    def __init__(self, index: dict[str, Any]) -> None:
        self._index = index

    def save(self) -> None:
        _atomic_write(INDEX_FILE, self._index)

    # ── Index accessors ────────────────────────────────────────────────────

    @property
    def active_sets(self) -> list[str]:
        return self._index.get("active_sets", [])

    @property
    def sets_meta(self) -> dict[str, dict[str, Any]]:
        return self._index.get("sets", {})

    def _set_path(self, set_id: str) -> Path:
        meta = self.sets_meta.get(set_id)
        if meta is None:
            raise KeyError(f"Set '{set_id}' not found")
        rel = meta["path"]
        return TOOLKIT_DIR / rel

    # ── Set CRUD ───────────────────────────────────────────────────────────

    def list_sets(self) -> list[dict[str, Any]]:
        rows = []
        for sid, meta in self.sets_meta.items():
            path = TOOLKIT_DIR / meta["path"]
            tool_count = 0
            if path.exists():
                try:
                    tool_count = len(json.loads(path.read_text(encoding="utf-8")).get("tools", []))
                except Exception:
                    pass
            rows.append({
                "id": sid,
                "active": sid in self.active_sets,
                "pinned": bool(meta.get("pinned")),
                "source": meta.get("source"),
                "tool_count": tool_count,
            })
        return rows

    def create_set(self, set_id: str, name: str) -> None:
        if not _valid_id(set_id):
            raise ValueError(f"Invalid set id: {set_id!r}")
        if set_id in self.sets_meta:
            raise ValueError(f"Set '{set_id}' already exists")
        path = SETS_DIR / f"{set_id}.json"
        _atomic_write(path, _empty_set(set_id, name))
        self._index["sets"][set_id] = {"path": f"sets/{set_id}.json"}
        self.save()

    def enable_set(self, set_id: str) -> None:
        if set_id not in self.sets_meta:
            raise KeyError(f"Set '{set_id}' not found")
        if set_id not in self.active_sets:
            self._index["active_sets"].append(set_id)
            self.save()

    def disable_set(self, set_id: str) -> None:
        meta = self.sets_meta.get(set_id)
        if meta is None:
            raise KeyError(f"Set '{set_id}' not found")
        if meta.get("pinned"):
            raise ValueError(f"Set '{set_id}' is pinned and cannot be disabled")
        if set_id in self.active_sets:
            self._index["active_sets"].remove(set_id)
            self.save()

    def remove_set(self, set_id: str) -> None:
        meta = self.sets_meta.get(set_id)
        if meta is None:
            raise KeyError(f"Set '{set_id}' not found")
        if meta.get("pinned"):
            raise ValueError(f"Set '{set_id}' is pinned and cannot be deleted")
        path = TOOLKIT_DIR / meta["path"]
        if path.exists():
            path.unlink()
        self._index["sets"].pop(set_id)
        if set_id in self.active_sets:
            self._index["active_sets"].remove(set_id)
        self.save()

    # ── Set data r/w ───────────────────────────────────────────────────────

    def load_set(self, set_id: str) -> dict[str, Any]:
        path = self._set_path(set_id)
        if not path.exists():
            raise FileNotFoundError(f"Set file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_set(self, set_id: str, data: dict[str, Any]) -> None:
        _validate_set(data)
        _atomic_write(self._set_path(set_id), data)

    # ── Tool CRUD ──────────────────────────────────────────────────────────

    def list_tools(
        self,
        category: str | None = None,
        tags: list[str] | None = None,
        sets: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return merged tools from active (or specified) sets, with set_id injected."""
        target_sets = sets if sets is not None else self.active_sets
        seen_ids: set[str] = set()
        results: list[dict[str, Any]] = []

        for sid in target_sets:
            if sid not in self.sets_meta:
                continue
            try:
                data = self.load_set(sid)
            except Exception:
                continue
            for tool in data.get("tools", []):
                tid = tool.get("id", "")
                if tid in seen_ids:
                    continue  # first active set wins
                if category:
                    cats = [c.lower() for c in tool.get("categories", [])]
                    if category.lower() not in cats:
                        continue
                if tags:
                    tool_tags = [t.lower() for t in tool.get("tags", [])]
                    if not all(t.lower() in tool_tags for t in tags):
                        continue
                seen_ids.add(tid)
                results.append({**tool, "_set": sid})

        return results

    def add_tool(self, set_id: str, tool: dict[str, Any]) -> None:
        _validate_tool(tool)
        data = self.load_set(set_id)
        existing_ids = {t["id"] for t in data["tools"]}
        if tool["id"] in existing_ids:
            raise ValueError(f"Tool '{tool['id']}' already exists in set '{set_id}'")
        data["tools"].append(tool)
        self.save_set(set_id, data)

    def update_tool(self, tool_id: str, updates: dict[str, Any], set_id: str | None = None) -> str:
        """Update fields of a tool. Returns the set_id where the tool was found."""
        sid, data, idx = self._find_tool(tool_id, set_id)
        data["tools"][idx].update(updates)
        _validate_tool(data["tools"][idx])
        self.save_set(sid, data)
        return sid

    def remove_tool(self, tool_id: str, set_id: str | None = None) -> str:
        """Remove a tool. Returns the set_id it was removed from."""
        sid, data, idx = self._find_tool(tool_id, set_id)
        data["tools"].pop(idx)
        self.save_set(sid, data)
        return sid

    def get_tool(self, tool_id: str, set_id: str | None = None) -> dict[str, Any]:
        """Resolve 'set_id:tool_id' or bare 'tool_id' across active sets."""
        if ":" in tool_id:
            set_id, tool_id = tool_id.split(":", 1)
        sid, data, idx = self._find_tool(tool_id, set_id)
        return {**data["tools"][idx], "_set": sid}

    def _find_tool(
        self, tool_id: str, set_id: str | None
    ) -> tuple[str, dict[str, Any], int]:
        search_sets = [set_id] if set_id else list(self.sets_meta.keys())
        for sid in search_sets:
            if sid not in self.sets_meta:
                continue
            try:
                data = self.load_set(sid)
            except Exception:
                continue
            for idx, tool in enumerate(data.get("tools", [])):
                if tool.get("id") == tool_id:
                    return sid, data, idx
        hint = f" in set '{set_id}'" if set_id else " in any set"
        raise KeyError(f"Tool '{tool_id}' not found{hint}")

    # ── Import / Export ────────────────────────────────────────────────────

    def import_set(self, data: dict[str, Any], alias: str | None = None) -> str:
        """Validate and install a set. Returns the set_id used."""
        _validate_set(data)
        set_id = alias or data["id"]
        if not _valid_id(set_id):
            raise ValueError(f"Invalid set id: {set_id!r}")
        data = dict(data)
        data["id"] = set_id
        path = SETS_DIR / f"{set_id}.json"
        _atomic_write(path, data)
        source = data.get("source") or None
        self._index["sets"][set_id] = {"path": f"sets/{set_id}.json", "source": source}
        if set_id not in self.active_sets:
            self._index["active_sets"].append(set_id)
        self.save()
        return set_id

    def export_set(self, set_id: str) -> dict[str, Any]:
        """Return the set JSON dict (suitable for sharing)."""
        return self.load_set(set_id)

    def update_from_source(self, set_id: str) -> None:
        """Re-fetch a set from its source URL and replace local copy."""
        meta = self.sets_meta.get(set_id)
        if meta is None:
            raise KeyError(f"Set '{set_id}' not found")
        source = meta.get("source")
        if not source:
            raise ValueError(f"Set '{set_id}' has no source URL")
        import urllib.request
        with urllib.request.urlopen(source, timeout=15) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        data["id"] = set_id  # keep local alias
        _validate_set(data)
        _atomic_write(self._set_path(set_id), data)
        self._index["sets"][set_id]["source"] = source
        self.save()
