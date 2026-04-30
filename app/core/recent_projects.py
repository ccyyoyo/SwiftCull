"""Most-recently-opened project folders.

Backed by a single key in SettingsDB (`recent_folders`), stored as a list of
{"path": str, "opened_at": iso8601} entries, ordered most-recent first, capped
at MAX_RECENT.

The helper is deliberately pure logic + thin SettingsDB I/O so it's trivially
unit-testable without the Qt event loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Protocol

MAX_RECENT = 10


class _SettingsLike(Protocol):
    def get(self, key: str, default=None): ...
    def set(self, key: str, value) -> None: ...


@dataclass(frozen=True)
class RecentProject:
    path: str
    opened_at: str  # ISO8601 UTC

    @property
    def name(self) -> str:
        return Path(self.path).name or self.path

    def exists(self) -> bool:
        return Path(self.path).is_dir()


class RecentProjects:
    KEY = "recent_folders"

    def __init__(self, settings: _SettingsLike):
        self._settings = settings

    def list_all(self) -> List[RecentProject]:
        raw = self._settings.get(self.KEY, []) or []
        out: List[RecentProject] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            opened = item.get("opened_at", "")
            if not path:
                continue
            out.append(RecentProject(path=str(path), opened_at=str(opened)))
        return out

    def list_existing(self) -> List[RecentProject]:
        return [p for p in self.list_all() if p.exists()]

    def add(self, folder_path: str, now: Optional[datetime] = None) -> None:
        """Push folder to the front, deduping by normalized path."""
        if not folder_path:
            return
        normalized = self._normalize(folder_path)
        if not normalized:
            return
        when = (now or datetime.now(timezone.utc)).isoformat()

        existing = self.list_all()
        existing = [p for p in existing if self._normalize(p.path) != normalized]
        existing.insert(0, RecentProject(path=normalized, opened_at=when))
        existing = existing[:MAX_RECENT]
        self._settings.set(self.KEY, [
            {"path": p.path, "opened_at": p.opened_at} for p in existing
        ])

    def remove(self, folder_path: str) -> None:
        normalized = self._normalize(folder_path)
        if not normalized:
            return
        existing = [p for p in self.list_all()
                    if self._normalize(p.path) != normalized]
        self._settings.set(self.KEY, [
            {"path": p.path, "opened_at": p.opened_at} for p in existing
        ])

    def prune_missing(self) -> None:
        """Drop entries whose path no longer exists on disk."""
        kept = self.list_existing()
        self._settings.set(self.KEY, [
            {"path": p.path, "opened_at": p.opened_at} for p in kept
        ])

    @staticmethod
    def _normalize(path: str) -> str:
        try:
            return str(Path(path).resolve())
        except (OSError, RuntimeError):
            return str(Path(path))
