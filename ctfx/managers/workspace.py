"""WorkspaceManager — directory/file operations and path resolution."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

VALID_STATUSES = ("fetched", "seen", "working", "hoard", "solved")

# Standard category list used for interactive selectors
DEFAULT_CATEGORIES = ["pwn", "crypto", "web", "forensics", "rev", "misc"]


class WorkspaceManager:
    """Manages the competition workspace directory tree.

    Path layout:
        {basedir}/{competition}/          ← competition root
            ctf.json
            prompt.md
            {category}/{challenge}/
                src/
                solve/
                wp.md
                chal.md
    """

    def __init__(self, basedir: Path, competition: str) -> None:
        self.basedir = basedir
        self.competition = competition

    def competition_root(self) -> Path:
        return self.basedir / self.competition

    @staticmethod
    def _validate_component(kind: str, value: str) -> str:
        """Reject path-like values for category/service/challenge names."""
        if not value or not value.strip():
            raise ValueError(f"{kind} must not be empty")
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(f"Invalid {kind}: {value!r}")
        return value

    def resolve_path(self, relative: str | None) -> Path:
        """Resolve a user-supplied relative path segment to an absolute path.

        Accepted forms:
            None or ""          -> competition root
            <cat>               -> {root}/{cat}/
            <cat>/<chal>        -> {root}/{cat}/{chal}/
            <cat>/<chal>/solve  -> {root}/{cat}/{chal}/solve/
            <cat>/<chal>/src    -> {root}/{cat}/{chal}/src/
        """
        root = self.competition_root().resolve()
        if not relative:
            return root
        candidate = (root / relative).resolve()
        if os.path.commonpath([str(root), str(candidate)]) != str(root):
            raise ValueError(f"Path escapes competition root: {relative!r}")
        return candidate

    @classmethod
    def list_competitions(cls, basedir: Path) -> list[dict[str, Any]]:
        """Scan basedir and return metadata list for all competitions."""
        comps: list[dict[str, Any]] = []
        if not basedir.exists():
            return comps
        for entry in sorted(basedir.iterdir()):
            if not entry.is_dir():
                continue
            ctf_file = entry / "ctf.json"
            if not ctf_file.exists():
                continue
            try:
                data = json.loads(ctf_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            challenges = data.get("challenges", {})
            solved = sum(1 for c in challenges.values() if c.get("status") == "solved")
            total = len(challenges)
            comps.append({
                "dir": entry.name,
                "name": data.get("name", entry.name),
                "year": data.get("year"),
                "mode": data.get("mode", "jeopardy"),
                "platform": data.get("platform", "manual"),
                "solved": solved,
                "total": total,
            })
        return comps

    def ctf_json_path(self) -> Path:
        return self.competition_root() / "ctf.json"

    def load_ctf_json(self) -> dict[str, Any]:
        path = self.ctf_json_path()
        if not path.exists():
            raise FileNotFoundError(f"ctf.json not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_ctf_json(self, data: dict[str, Any]) -> None:
        path = self.ctf_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def ensure_basedir(self) -> None:
        """Create basedir if it doesn't exist."""
        self.basedir.mkdir(parents=True, exist_ok=True)

    def init_competition(
        self,
        name: str,
        year: int,
        mode: str,
        platform: str,
        url: str | None = None,
        flag_format: str | None = None,
        team_name: str | None = None,
        team_token: str | None = None,
        dir_name: str | None = None,
    ) -> Path:
        """Create a new competition directory and ctf.json. Returns competition root."""
        self.ensure_basedir()
        comp_name = dir_name or f"{name}_{year}"
        root = self.basedir / comp_name
        root.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {
            "name": name,
            "year": year,
            "flag_format": flag_format or "flag{...}",
            "team_name": team_name or "",
            "team_token": team_token or "",
            "team_cookies": "",
            "mode": mode,
            "platform": platform,
            "url": url or "",
            "submit_api": platform != "manual",
            "challenges": {},
        }
        (root / "ctf.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return root

    def list_challenges(self) -> list[dict[str, Any]]:
        """Return all challenges from ctf.json as a list of dicts."""
        try:
            data = self.load_ctf_json()
        except FileNotFoundError:
            return []
        results: list[dict[str, Any]] = []
        for key, meta in data.get("challenges", {}).items():
            cat, _, chal = key.partition("/")
            results.append({
                "key": key,
                "name": chal or key,
                "category": cat if chal else "",
                "status": meta.get("status", "fetched"),
                "points": meta.get("points"),
                "flag": meta.get("flag"),
                "remote": meta.get("remote"),
                "solved_at": meta.get("solved_at"),
                "extra_info": meta.get("extra_info"),
            })
        return results

    def find_challenge(self, name: str) -> dict[str, Any] | None:
        """Find a challenge by name (case-insensitive). Returns metadata dict or None."""
        for chal in self.list_challenges():
            if chal["name"].lower() == name.lower():
                return chal
        return None

    def create_challenge(self, category: str, name: str) -> Path:
        """Create challenge directory tree and register in ctf.json. Returns chal dir."""
        self.ensure_basedir()
        category = self._validate_component("category", category)
        name = self._validate_component("challenge name", name)
        root = self.competition_root()
        chal_dir = root / category / name
        (chal_dir / "src").mkdir(parents=True, exist_ok=True)
        (chal_dir / "solve").mkdir(parents=True, exist_ok=True)
        (chal_dir / "wp.md").write_text(f"# {name} writeup\n", encoding="utf-8")
        (chal_dir / "chal.md").write_text(
            f"# {name}\n\n<!-- paste challenge description here -->\n", encoding="utf-8"
        )

        data = self.load_ctf_json()
        key = f"{category}/{name}"
        if key not in data.setdefault("challenges", {}):
            data["challenges"][key] = {
                "status": "seen",
                "flag": None,
                "points": None,
                "remote": None,
                "fetched_at": None,
                "solved_at": None,
            }
            self.save_ctf_json(data)

        return chal_dir

    def challenge_dir(self, category: str, name: str) -> Path:
        """Return the on-disk directory for a challenge."""
        category = self._validate_component("category", category)
        name = self._validate_component("challenge name", name)
        return self.competition_root() / category / name

    def remove_challenge(self, name: str) -> None:
        """Remove challenge directory and ctf.json entry."""
        chal = self.find_challenge(name)
        if chal is None:
            raise KeyError(f"Challenge '{name}' not found")

        chal_dir = self.competition_root() / chal["key"]
        if chal_dir.exists():
            shutil.rmtree(chal_dir)

        data = self.load_ctf_json()
        data.get("challenges", {}).pop(chal["key"], None)
        self.save_ctf_json(data)

    def record_flag(self, name: str, flag: str, status: str | None = None) -> None:
        """Store a flag locally and optionally update challenge status."""
        chal = self.find_challenge(name)
        if chal is None:
            raise KeyError(f"Challenge '{name}' not found")
        data = self.load_ctf_json()
        entry = data["challenges"][chal["key"]]
        entry["flag"] = flag
        next_status = status
        if next_status is None and entry.get("status") != "solved":
            next_status = "hoard"
        if next_status:
            if next_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{next_status}'. Must be one of {VALID_STATUSES}")
            entry["status"] = next_status
            if next_status == "solved" and entry.get("solved_at") is None:
                from datetime import datetime, timezone
                entry["solved_at"] = datetime.now(timezone.utc).isoformat()
        self.save_ctf_json(data)

    def set_challenge_status(
        self, name: str, status: str, flag: str | None = None
    ) -> None:
        """Update challenge status (and optionally flag) in ctf.json."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")
        chal = self.find_challenge(name)
        if chal is None:
            raise KeyError(f"Challenge '{name}' not found")

        data = self.load_ctf_json()
        entry = data["challenges"][chal["key"]]
        entry["status"] = status
        if flag is not None:
            entry["flag"] = flag
        if status == "solved" and entry.get("solved_at") is None:
            from datetime import datetime, timezone
            entry["solved_at"] = datetime.now(timezone.utc).isoformat()
        self.save_ctf_json(data)

    def load_hostlist(self, service: str) -> list[tuple[str, str]]:
        """Parse hostlist.txt for an AWD service. Returns [(team_name, ip), ...]."""
        service = self._validate_component("service", service)
        path = self.resolve_path(service) / "hostlist.txt"
        if not path.exists():
            return []
        results = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                results.append((parts[0], parts[1]))
        return results

    def get_service_key_path(self, service: str) -> Path | None:
        service = self._validate_component("service", service)
        path = self.resolve_path(service) / "key.pem"
        return path if path.exists() else None

    @staticmethod
    def to_wsl_path(path: Path) -> str:
        """Convert a Windows absolute path to a WSL /mnt/... path.

        E.g. C:\\Users\\foo\\ctf  ->  /mnt/c/Users/foo/ctf
        """
        path = path.resolve()
        if sys.platform != "win32":
            return str(path)
        drive = path.drive
        rest = str(path)[len(drive):]
        drive_letter = drive.rstrip(":").lower()
        posix_rest = PurePosixPath(rest.replace("\\", "/"))
        return f"/mnt/{drive_letter}{posix_rest}"

    @staticmethod
    def fuzzy_match(query: str, items: list[str]) -> list[str]:
        """Case-insensitive substring/token match."""
        q = query.lower()
        return [
            item for item in items
            if q in item.lower() or any(q in tok for tok in item.lower().split("_"))
        ]
