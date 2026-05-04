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
        import logging
        log = logging.getLogger(__name__)
        log.info("ExposureWorker.run started")
        try:
            self._run_inner()
        except Exception as e:
            log.exception("Exception in ExposureWorker.run: %s", e)
        finally:
            log.info("ExposureWorker.run finished, emitting finished signal")
            self.finished.emit()

    def _run_inner(self):
        import logging
        log = logging.getLogger(__name__)
        log.info("ExposureWorker._run_inner started with %d photos", len(self._photo_ids))
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            repo = PhotoRepository(conn)
            svc = ExposureService()
            total = len(self._photo_ids)
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    log.info("ExposureWorker cancelled")
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    result = svc.compute_scores(self._folder, photo.relative_path)
                    if result is not None:
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
                    else:
                        log.debug("ExposureService returned None for photo %d, skipping DB write", photo_id)
                except Exception as e:
                    log.debug("Error computing exposure for photo %d: %s", photo_id, e)
                self.progress.emit(i + 1, total)
            log.info("ExposureWorker._run_inner completed")
        except Exception as e:
            log.exception("Error in ExposureWorker._run_inner: %s", e)
        finally:
            conn.close()


class ExposureController(QObject):
    """Owns QThread + ExposureWorker pair. Same lifecycle as BlurController."""
    photo_exposure_updated = Signal(int, float, float, float)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, folder_path: str, db_path: str, photo_ids: list, parent=None):
        import logging
        self._log = logging.getLogger(__name__)
        self._log.info("ExposureController.__init__ started")
        super().__init__(parent)
        self._worker = ExposureWorker(folder_path, db_path, photo_ids)
        self._thread = None
        self._log.info("ExposureController.__init__ completed")

    def start(self):
        self._log.info("ExposureController.start called")
        if self._thread is None:
            self._thread = QThread()
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.photo_exposure_updated.connect(self.photo_exposure_updated)
            self._worker.progress.connect(self.progress)
            self._worker.finished.connect(self._thread.quit)
            self._thread.finished.connect(self.finished)
            self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self._log.info("ExposureController thread started")

    def cancel(self):
        self._worker.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        if self._thread is None:
            return True
        return self._thread.wait(timeout_ms)

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
