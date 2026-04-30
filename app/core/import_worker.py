"""Background importer.

The caller (MainWindow / GridView) computes the work via ScanService and then
hands explicit `new_paths` / `modified_paths` to this worker — keeping the
"detect changes" and "apply changes" responsibilities separate.

The worker:
- inserts minimal rows for new files (UI gets a placeholder thumbnail at once),
- updates file_size + mtime for modified files and invalidates their thumbnail
  cache (so the next view regenerates),
- then enriches all touched rows with EXIF + dimensions in a second pass.

Runs on its own QThread with its own SQLite connection (WAL mode allows
multi-connection access).
"""

import os
import sqlite3
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.import_service import ImportService
from app.core.thumbnail_service import ThumbnailService
from app.db.photo_repository import PhotoRepository


class ImportWorker(QObject):
    """Lives on a QThread. Driven by start()."""
    photo_imported = Signal(object)   # new Photo (minimal) — UI inserts a tile
    photo_updated = Signal(int)       # modified row id (UI may refresh tag/cache)
    photo_enriched = Signal(int)      # row id whose EXIF/dimensions just landed
    progress = Signal(int, int)       # current, total
    error = Signal(str, str)          # (relative_path, message)
    finished = Signal()

    def __init__(
        self,
        folder_path: str,
        db_path: str,
        new_paths: list[str],
        modified_paths: Optional[list[str]] = None,
        cache_dir: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._folder = folder_path
        self._db_path = db_path
        self._new_paths = list(new_paths)
        self._modified_paths = list(modified_paths or [])
        self._cache_dir = cache_dir
        self._cancel = False

    @Slot()
    def cancel(self):
        self._cancel = True

    @Slot()
    def run(self):
        try:
            self._run_inner()
        finally:
            self.finished.emit()

    def _run_inner(self):
        if not self._new_paths and not self._modified_paths:
            return

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            repo = PhotoRepository(conn)
            svc = ImportService()
            thumb_svc = ThumbnailService(self._cache_dir) if self._cache_dir else None

            touched: list[tuple[int, str]] = []  # (photo_id, rel) — enrich later
            total = len(self._new_paths) + len(self._modified_paths)
            done = 0

            # Phase 1a: insert minimal rows for newcomers.
            for rel in self._new_paths:
                if self._cancel:
                    return
                try:
                    photo = svc.build_photo_minimal(self._folder, rel)
                    existing_id = repo.get_id_by_relative_path(rel)
                    if existing_id is not None:
                        # Race: another scan slipped in. Treat as modified.
                        repo.update_metadata(existing_id, {
                            "file_size": photo.file_size,
                            "mtime": photo.mtime,
                        })
                        photo.id = existing_id
                        self.photo_updated.emit(existing_id)
                        touched.append((existing_id, rel))
                    else:
                        photo_id = repo.insert(photo)
                        photo.id = photo_id
                        self.photo_imported.emit(photo)
                        touched.append((photo_id, rel))
                except Exception as exc:
                    self.error.emit(rel, str(exc))
                done += 1
                self.progress.emit(done, total)

            # Phase 1b: refresh size/mtime + invalidate cache for modified rows.
            for rel in self._modified_paths:
                if self._cancel:
                    return
                photo_id = repo.get_id_by_relative_path(rel)
                if photo_id is None:
                    # Lost row? Promote to insert so we don't drop the file.
                    try:
                        photo = svc.build_photo_minimal(self._folder, rel)
                        photo_id = repo.insert(photo)
                        photo.id = photo_id
                        self.photo_imported.emit(photo)
                        touched.append((photo_id, rel))
                    except Exception as exc:
                        self.error.emit(rel, str(exc))
                    done += 1
                    self.progress.emit(done, total)
                    continue
                try:
                    abs_path = os.path.join(self._folder, rel)
                    repo.update_metadata(photo_id, {
                        "file_size": os.path.getsize(abs_path),
                        "mtime": os.path.getmtime(abs_path),
                    })
                    if thumb_svc is not None:
                        thumb_svc.invalidate(abs_path)
                    self.photo_updated.emit(photo_id)
                    touched.append((photo_id, rel))
                except Exception as exc:
                    self.error.emit(rel, str(exc))
                done += 1
                self.progress.emit(done, total)

            # Phase 2: enrich EXIF + dimensions for everything touched.
            for photo_id, rel in touched:
                if self._cancel:
                    return
                try:
                    meta = svc.enrich_photo(self._folder, rel)
                    repo.update_metadata(photo_id, meta)
                    self.photo_enriched.emit(photo_id)
                except Exception as exc:
                    self.error.emit(rel, str(exc))
        finally:
            conn.close()


class ImportController(QObject):
    """Owns the QThread + Worker pair and exposes a simple API."""
    photo_imported = Signal(object)
    photo_updated = Signal(int)
    photo_enriched = Signal(int)
    progress = Signal(int, int)
    error = Signal(str, str)
    finished = Signal()

    def __init__(
        self,
        folder_path: str,
        db_path: str,
        new_paths: list[str],
        modified_paths: Optional[list[str]] = None,
        cache_dir: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = ImportWorker(
            folder_path, db_path,
            new_paths=new_paths,
            modified_paths=modified_paths,
            cache_dir=cache_dir,
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.photo_imported.connect(self.photo_imported)
        self._worker.photo_updated.connect(self.photo_updated)
        self._worker.photo_enriched.connect(self.photo_enriched)
        self._worker.progress.connect(self.progress)
        self._worker.error.connect(self.error)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self.finished)
        self._thread.finished.connect(self._cleanup)

    @property
    def total(self) -> int:
        return len(self._worker._new_paths) + len(self._worker._modified_paths)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._worker.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        return self._thread.wait(timeout_ms)

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
