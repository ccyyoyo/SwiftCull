"""Background importer that scans a folder, inserts minimal photo rows,
then enriches each row with EXIF/dimensions. Runs on its own thread with
its own SQLite connection (WAL mode allows multi-connection access)."""

import sqlite3
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.import_service import ImportService
from app.core.models import Photo
from app.db.photo_repository import PhotoRepository


class ImportWorker(QObject):
    """Lives on a QThread. Driven by start()."""
    scanned = Signal(int)
    photo_imported = Signal(object)
    progress = Signal(int, int)
    photo_enriched = Signal(int)
    error = Signal(str, str)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, parent=None):
        super().__init__(parent)
        self._folder = folder_path
        self._db_path = db_path
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
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            repo = PhotoRepository(conn)
            svc = ImportService()

            paths = svc.scan_folder(self._folder)
            self.scanned.emit(len(paths))
            if not paths:
                return

            inserted = []
            total = len(paths)
            for i, rel in enumerate(paths):
                if self._cancel:
                    return
                existing_id = repo.get_id_by_relative_path(rel)
                if existing_id is not None:
                    inserted.append((existing_id, rel, False))
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    photo = svc.build_photo_minimal(self._folder, rel)
                    photo_id = repo.insert(photo)
                    photo.id = photo_id
                    inserted.append((photo_id, rel, True))
                    self.photo_imported.emit(photo)
                except Exception as e:
                    self.error.emit(rel, str(e))
                self.progress.emit(i + 1, total)

            for photo_id, rel, is_new in inserted:
                if self._cancel:
                    return
                if not is_new:
                    continue
                try:
                    meta = svc.enrich_photo(self._folder, rel)
                    repo.update_metadata(photo_id, meta)
                    self.photo_enriched.emit(photo_id)
                except Exception as e:
                    self.error.emit(rel, str(e))
        finally:
            conn.close()


class ImportController(QObject):
    """Owns the QThread + Worker pair and exposes a simple API."""
    scanned = Signal(int)
    photo_imported = Signal(object)
    progress = Signal(int, int)
    photo_enriched = Signal(int)
    error = Signal(str, str)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = ImportWorker(folder_path, db_path)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.scanned.connect(self.scanned)
        self._worker.photo_imported.connect(self.photo_imported)
        self._worker.progress.connect(self.progress)
        self._worker.photo_enriched.connect(self.photo_enriched)
        self._worker.error.connect(self.error)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self.finished)
        self._thread.finished.connect(self._cleanup)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._worker.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        return self._thread.wait(timeout_ms)

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
