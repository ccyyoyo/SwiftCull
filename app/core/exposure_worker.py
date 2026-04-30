"""Background exposure analysis worker. Mirrors the BlurWorker pattern."""

import sqlite3
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.exposure_service import ExposureService
from app.db.photo_repository import PhotoRepository


class ExposureWorker(QObject):
    photo_exposure_updated = Signal(int, float, float, float)  # photo_id, mean, over, under
    progress = Signal(int, int)                                # current, total
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
            svc = ExposureService()
            total = len(self._photo_ids)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    result = svc.compute_scores(self._folder, photo.relative_path)
                    repo.update_exposure_scores(
                        photo_id,
                        result.mean_brightness,
                        result.overexposed_fraction,
                        result.underexposed_fraction,
                    )
                    self.photo_exposure_updated.emit(
                        photo_id,
                        result.mean_brightness,
                        result.overexposed_fraction,
                        result.underexposed_fraction,
                    )
                except Exception:
                    pass
                self.progress.emit(i + 1, total)
        finally:
            conn.close()


class ExposureController(QObject):
    """Owns QThread + ExposureWorker pair. Same pattern as BlurController."""
    photo_exposure_updated = Signal(int, float, float, float)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = ExposureWorker(folder_path, db_path, photo_ids)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.photo_exposure_updated.connect(self.photo_exposure_updated)
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
