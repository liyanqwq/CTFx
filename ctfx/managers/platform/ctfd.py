"""CTFd platform adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from ctfx.managers.platform.base import AbstractPlatform


class CTFdPlatform(AbstractPlatform):
    """Minimal CTFd REST API integration."""

    def __init__(self, base_url: str, token: str | None = None, cookies: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if token:
            self.session.headers["Authorization"] = f"Token {token}"
        if cookies:
            self.session.headers["Cookie"] = cookies

    def _api_get(self, path: str, *, timeout: int = 15) -> dict[str, Any]:
        resp = self.session.get(f"{self.base_url}{path}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def has_auth(self) -> bool:
        return "Authorization" in self.session.headers or "Cookie" in self.session.headers

    def auth_mode(self) -> str:
        if "Authorization" in self.session.headers:
            return "token"
        if "Cookie" in self.session.headers:
            return "cookie"
        return "none"

    def fetch_challenges(self) -> list[dict[str, Any]]:
        data = self._api_get("/api/v1/challenges").get("data", [])
        results: list[dict[str, Any]] = []
        for item in data:
            files = item.get("files") or []
            if isinstance(files, dict):
                files = files.get("files", [])
            results.append({
                "platform_id": item["id"],
                "name": item.get("name", "").lower().replace(" ", "_"),
                "display_name": item.get("name", ""),
                "category": item.get("category", "misc").lower().replace(" ", "_"),
                "description": item.get("description", ""),
                "points": item.get("value"),
                "connection_info": item.get("connection_info", ""),
                "files": files,
                "solved_by_me": bool(item.get("solved_by_me", False)),
            })
        return results

    def get_scoreboard(self) -> list[dict[str, Any]]:
        return self._api_get("/api/v1/scoreboard").get("data", [])

    def get_challenge_solves(self, challenge_id: int) -> list[dict[str, Any]]:
        return self._api_get(f"/api/v1/challenges/{challenge_id}/solves").get("data", [])

    def get_api_status(self) -> dict[str, Any]:
        challenges = self.fetch_challenges()
        scoreboard = self.get_scoreboard()
        solved = sum(1 for item in challenges if item.get("solved_by_me"))
        return {
            "base_url": self.base_url,
            "auth_mode": self.auth_mode(),
            "authenticated": self.has_auth(),
            "challenge_count": len(challenges),
            "solved_count": solved,
            "scoreboard_entries": len(scoreboard),
        }

    def submit_flag(self, challenge_id: int, flag: str) -> dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/api/v1/challenges/attempt",
            json={"challenge_id": challenge_id, "submission": flag},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def download_file(self, url: str, dst_dir: Path) -> Path:
        dst_dir.mkdir(parents=True, exist_ok=True)
        parsed = urlparse(url)
        filename = Path(parsed.path).name or "download.bin"
        dst = dst_dir / filename
        with self.session.get(url, timeout=30, stream=True) as resp:
            resp.raise_for_status()
            with dst.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return dst
