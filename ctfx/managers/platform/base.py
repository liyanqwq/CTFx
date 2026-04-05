"""AbstractPlatform — base class for CTF platform adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AbstractPlatform(ABC):
    """Base class for platform integrations."""

    @abstractmethod
    def fetch_challenges(self) -> list[dict[str, Any]]:
        """Return challenge metadata from the remote platform."""

    @abstractmethod
    def submit_flag(self, challenge_id: int, flag: str) -> dict[str, Any]:
        """Submit a flag to the remote platform."""

    @abstractmethod
    def download_file(self, url: str, dst_dir: Path) -> Path:
        """Download a remote file into a destination directory."""
