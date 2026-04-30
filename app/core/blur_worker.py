"""Background blur analysis worker. Mirrors the ImportWorker pattern."""

import sqlite3
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.blur_service import BlurService
from app.db.photo_repository import PhotoRepository


class BlurWorker(QObject):
    photo_blur_updated = Signal(int, float)   # photo_id, score
    progress = Signal(int, int)               # current, total
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        super().__init__(parent)
        self._folder = folder_path
        self._db_path = db_path
        self._photo_ids = photo_ids
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
            repo = PhotoRepository(conn)
            svc = BlurService()
            total = len(self._photo_ids)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    score = svc.compute_score(self._folder, photo.relative_path)
                    if score is not None:
                        repo.update_blur_score(photo_id, score)
                        self.photo_blur_updated.emit(photo_id, score)
                except Exception:
                    pass
                self.progress.emit(i + 1, total)
        finally:
            conn.close()


class BlurController(QObject):
    """Owns QThread + BlurWorker pair. Same pattern as ImportController."""
    photo_blur_updated = Signal(int, float)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = BlurWorker(folder_path, db_path, photo_ids)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.photo_blur_updated.connect(self.photo_blur_updated)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self.finished)
        self._thread.finished.connect(self._cleanup)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._worker.cancel()

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
