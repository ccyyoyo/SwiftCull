"""Background face analysis worker. Mirrors the ExposureWorker pattern.

The ``FaceService`` lazy-initializes MediaPipe on first ``compute`` call, which
happens inside ``run()`` (i.e. on the worker thread). Initializing on the main
thread can cause native graph builds to hang the UI.
"""

import logging
import sqlite3

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.face_service import FaceService
from app.db.photo_repository import PhotoRepository

log = logging.getLogger(__name__)


class FaceWorker(QObject):
    photo_face_updated = Signal(int, int, float, int)  # photo_id, count, max_area, eyes_closed
    progress = Signal(int, int)                        # current, total
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
        log.info("FaceWorker.run started")
        try:
            self._run_inner()
        except Exception as e:
            log.exception("Exception in FaceWorker.run: %s", e)
        finally:
            log.info("FaceWorker.run finished, emitting finished signal")
            self.finished.emit()

    def _run_inner(self):
        log.info("FaceWorker._run_inner started with %d photos", len(self._photo_ids))
        svc = FaceService()
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            repo = PhotoRepository(conn)
            total = len(self._photo_ids)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    log.info("FaceWorker cancelled")
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    result = svc.compute(self._folder, photo.relative_path)
                    if result is not None:
                        repo.update_face_result(
                            photo_id,
                            result.face_count,
                            result.face_max_area,
                            result.eyes_closed_count,
                        )
                        self.photo_face_updated.emit(
                            photo_id,
                            result.face_count,
                            result.face_max_area,
                            result.eyes_closed_count,
                        )
                    else:
                        # Decode/inference failed; mark as attempted so we don't
                        # re-process every button click.
                        repo.mark_face_no_result(photo_id)
                        log.debug("FaceService returned None for photo %d, marked no_result", photo_id)
                except Exception as e:
                    log.debug("Error computing face for photo %d: %s", photo_id, e)
                self.progress.emit(i + 1, total)
            log.info("FaceWorker._run_inner completed")
        except Exception as e:
            log.exception("Error in FaceWorker._run_inner: %s", e)
        finally:
            try:
                svc.close()
            except Exception:
                pass
            conn.close()


class FaceController(QObject):
    """Owns QThread + FaceWorker pair. Same lifecycle as ExposureController."""
    photo_face_updated = Signal(int, int, float, int)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        log.info("FaceController.__init__ started")
        try:
            super().__init__(parent)
            self._worker = FaceWorker(folder_path, db_path, photo_ids)
            self._thread = None
            log.info("FaceController.__init__ completed")
        except Exception as e:
            log.exception("Error in FaceController.__init__: %s", e)
            raise

    def start(self):
        log.info("FaceController.start called")
        try:
            if self._thread is None:
                self._thread = QThread()
                self._worker.moveToThread(self._thread)
                self._thread.started.connect(self._worker.run)
                self._worker.photo_face_updated.connect(self.photo_face_updated)
                self._worker.progress.connect(self.progress)
                self._worker.finished.connect(self._thread.quit)
                self._thread.finished.connect(self.finished)
                self._thread.finished.connect(self._cleanup)
            self._thread.start()
            log.info("FaceController thread started")
        except Exception as e:
            log.exception("Error in FaceController.start: %s", e)
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
