"""Background horizon skew analysis worker. Mirrors the BlurWorker pattern."""

import logging
import sqlite3
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.horizon_service import HorizonService
from app.db.photo_repository import PhotoRepository

log = logging.getLogger(__name__)


class HorizonWorker(QObject):
    photo_horizon_updated = Signal(int, float)  # photo_id, skew_angle
    progress = Signal(int, int)                 # current, total
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
        log.info("HorizonWorker.run started")
        try:
            self._run_inner()
        except Exception as e:
            log.exception("Exception in HorizonWorker.run: %s", e)
        finally:
            log.info("HorizonWorker.run finished, emitting finished signal")
            self.finished.emit()

    def _run_inner(self):
        log.info("HorizonWorker._run_inner started with %d photos", len(self._photo_ids))
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            repo = PhotoRepository(conn)
            svc = HorizonService()
            total = len(self._photo_ids)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    log.info("HorizonWorker cancelled")
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    skew = svc.compute_skew(self._folder, photo.relative_path)
                    if skew is not None:
                        repo.update_horizon_skew(photo_id, skew)
                        self.photo_horizon_updated.emit(photo_id, skew)
                    else:
                        # No detectable horizon — mark analyzed so we don't retry forever
                        repo.mark_horizon_no_result(photo_id)
                        log.debug("No horizon found for photo %d; marked analyzed", photo_id)
                except Exception as e:
                    log.debug("Error computing horizon skew for photo %d: %s", photo_id, e)
                self.progress.emit(i + 1, total)
            log.info("HorizonWorker._run_inner completed")
        except Exception as e:
            log.exception("Error in HorizonWorker._run_inner: %s", e)
        finally:
            conn.close()


class HorizonController(QObject):
    """Owns QThread + HorizonWorker pair. Same lifecycle as BlurController."""
    photo_horizon_updated = Signal(int, float)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        log.info("HorizonController.__init__ started")
        try:
            super().__init__(parent)
            self._worker = HorizonWorker(folder_path, db_path, photo_ids)
            self._thread = None
            log.info("HorizonController.__init__ completed")
        except Exception as e:
            log.exception("Error in HorizonController.__init__: %s", e)
            raise

    def start(self):
        log.info("HorizonController.start called")
        try:
            if self._thread is None:
                self._thread = QThread()
                self._worker.moveToThread(self._thread)
                self._thread.started.connect(self._worker.run)
                self._worker.photo_horizon_updated.connect(self.photo_horizon_updated)
                self._worker.progress.connect(self.progress)
                self._worker.finished.connect(self._thread.quit)
                self._thread.finished.connect(self.finished)
                self._thread.finished.connect(self._cleanup)
            self._thread.start()
            log.info("HorizonController thread started")
        except Exception as e:
            log.exception("Error in HorizonController.start: %s", e)
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
