"""Background noise analysis worker. Mirrors the BlurWorker pattern."""

import logging
import sqlite3
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.noise_service import NoiseService
from app.db.photo_repository import PhotoRepository

log = logging.getLogger(__name__)


class NoiseWorker(QObject):
    photo_noise_updated = Signal(int, float)   # photo_id, score
    progress = Signal(int, int)                # current, total
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
        log.info("NoiseWorker.run started")
        try:
            self._run_inner()
        except Exception as e:
            log.exception("Exception in NoiseWorker.run: %s", e)
        finally:
            log.info("NoiseWorker.run finished, emitting finished signal")
            self.finished.emit()

    def _run_inner(self):
        log.info("NoiseWorker._run_inner started with %d photos", len(self._photo_ids))
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            repo = PhotoRepository(conn)
            svc = NoiseService()
            total = len(self._photo_ids)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    log.info("Noise analysis cancelled")
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    log.debug("Computing noise for photo %d: %s", photo_id, photo.relative_path)
                    score = svc.compute_score(self._folder, photo.relative_path)
                    if score is not None:
                        repo.update_noise_score(photo_id, score)
                        self.photo_noise_updated.emit(photo_id, score)
                except Exception as e:
                    log.debug("Error computing noise for photo %d: %s", photo_id, e)
                self.progress.emit(i + 1, total)
            log.info("Noise analysis completed successfully")
        except Exception as e:
            log.exception("Error in NoiseWorker._run_inner: %s", e)
        finally:
            conn.close()


class NoiseController(QObject):
    """Owns QThread + NoiseWorker pair. Same pattern as BlurController."""
    photo_noise_updated = Signal(int, float)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        log.info("NoiseController.__init__ started")
        try:
            super().__init__(parent)
            self._worker = NoiseWorker(folder_path, db_path, photo_ids)
            self._thread = None
            log.info("NoiseController.__init__ completed")
        except Exception as e:
            log.exception("Error in NoiseController.__init__: %s", e)
            raise

    def start(self):
        log.info("NoiseController.start called")
        try:
            if self._thread is None:
                self._thread = QThread()
                self._worker.moveToThread(self._thread)
                self._thread.started.connect(self._worker.run)
                self._worker.photo_noise_updated.connect(self.photo_noise_updated)
                self._worker.progress.connect(self.progress)
                self._worker.finished.connect(self._thread.quit)
                self._thread.finished.connect(self.finished)
                self._thread.finished.connect(self._cleanup)
            self._thread.start()
            log.info("NoiseController thread started")
        except Exception as e:
            log.exception("Error in NoiseController.start: %s", e)
            raise

    def cancel(self):
        self._worker.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        if self._thread is None:
            return True
        return self._thread.wait(timeout_ms)

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
