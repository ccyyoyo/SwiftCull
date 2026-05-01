"""Background blur analysis worker. Mirrors the ImportWorker pattern."""

import logging
import sqlite3
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.blur_service import BlurService
from app.db.photo_repository import PhotoRepository

log = logging.getLogger(__name__)


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
        log.info("BlurWorker.run started")
        try:
            self._run_inner()
        except Exception as e:
            log.exception("Exception in BlurWorker.run: %s", e)
        finally:
            log.info("BlurWorker.run finished, emitting finished signal")
            self.finished.emit()

    def _run_inner(self):
        log.info("_run_inner started with %d photos", len(self._photo_ids))
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            log.info("Connecting to database: %s", self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            repo = PhotoRepository(conn)
            svc = BlurService()
            total = len(self._photo_ids)
            log.info("Starting blur analysis for %d photos", total)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    log.info("Blur analysis cancelled")
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    log.debug("Photo %d not found, skipping", photo_id)
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    log.debug("Computing blur for photo %d: %s", photo_id, photo.relative_path)
                    score = svc.compute_score(self._folder, photo.relative_path)
                    if score is not None:
                        repo.update_blur_score(photo_id, score)
                        self.photo_blur_updated.emit(photo_id, score)
                except Exception as e:
                    log.debug("Error computing blur for photo %d: %s", photo_id, e)
                self.progress.emit(i + 1, total)
            log.info("Blur analysis completed successfully")
        except Exception as e:
            log.exception("Error in _run_inner: %s", e)
        finally:
            log.info("Closing database connection")
            conn.close()


class BlurController(QObject):
    """Owns QThread + BlurWorker pair. Same pattern as ImportController."""
    photo_blur_updated = Signal(int, float)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        log.info("BlurController.__init__ started")
        try:
            super().__init__(parent)
            log.info("Creating BlurWorker with %d photos", len(photo_ids))
            self._worker = BlurWorker(folder_path, db_path, photo_ids)
            log.info("BlurWorker created")
            self._thread = None
            log.info("BlurController.__init__ completed")
        except Exception as e:
            log.exception("Error in BlurController.__init__: %s", e)
            raise

    def start(self):
        log.info("BlurController.start called")
        try:
            if self._thread is None:
                log.info("Creating and setting up QThread")
                self._thread = QThread()
                log.info("QThread created")
                self._worker.moveToThread(self._thread)
                log.info("Worker moved to thread")

                log.info("Connecting signals")
                self._thread.started.connect(self._worker.run)
                log.info("Connected thread.started -> worker.run")
                self._worker.photo_blur_updated.connect(self.photo_blur_updated)
                self._worker.progress.connect(self.progress)
                self._worker.finished.connect(self._thread.quit)
                log.info("Connected worker.finished -> thread.quit")
                self._thread.finished.connect(self.finished)
                self._thread.finished.connect(self._cleanup)

            log.info("Starting thread")
            self._thread.start()
            log.info("Thread started")
        except Exception as e:
            log.exception("Error in BlurController.start: %s", e)
            raise

    def cancel(self):
        self._worker.cancel()

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
