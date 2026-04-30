"""Compare files on disk against what's recorded in the project DB.

Pure: no Qt, no threading, no SQLite — takes the relevant inputs as plain
data so it's trivial to unit-test and to call from a background worker.

The service answers one question: given the supported-format files in
`folder_path` and a `{relative_path: db_mtime}` map from the DB, which
relative paths are *new* (not in DB) and which are *modified* (mtime on
disk is meaningfully newer than what was stored)?
"""

import os
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from app.core.import_service import ImportService

# Filesystem mtime can have float noise around precision boundaries; only
# treat differences larger than this as a real modification.
_MTIME_EPSILON = 1.0


@dataclass(frozen=True)
class ScanResult:
    new_paths: list[str] = field(default_factory=list)
    modified_paths: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.new_paths) + len(self.modified_paths)

    @property
    def has_changes(self) -> bool:
        return self.total > 0


class ScanService:
    def __init__(
        self,
        import_service: Optional[ImportService] = None,
        mtime_epsilon: float = _MTIME_EPSILON,
    ):
        self._importer = import_service or ImportService()
        self._epsilon = mtime_epsilon

    def scan(
        self,
        folder_path: str,
        db_path_mtime: Mapping[str, Optional[float]],
    ) -> ScanResult:
        disk_paths = self._importer.scan_folder(folder_path)
        return self.compare(folder_path, disk_paths, db_path_mtime)

    def compare(
        self,
        folder_path: str,
        disk_paths: Iterable[str],
        db_path_mtime: Mapping[str, Optional[float]],
    ) -> ScanResult:
        new_paths: list[str] = []
        modified_paths: list[str] = []
        for rel in disk_paths:
            if rel not in db_path_mtime:
                new_paths.append(rel)
                continue
            db_mtime = db_path_mtime[rel]
            disk_mtime = self._safe_mtime(folder_path, rel)
            if disk_mtime is None:
                continue
            if db_mtime is None:
                # Legacy row imported before mtime tracking; record now without
                # bothering the user — treat as already-known.
                continue
            if disk_mtime - db_mtime > self._epsilon:
                modified_paths.append(rel)
        return ScanResult(new_paths=new_paths, modified_paths=modified_paths)

    @staticmethod
    def _safe_mtime(folder_path: str, relative_path: str) -> Optional[float]:
        try:
            return os.path.getmtime(os.path.join(folder_path, relative_path))
        except OSError:
            return None
