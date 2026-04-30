"""Run ScanService on a QThread.

Compares files on disk against the project DB without blocking the UI.
Worker holds its own short-lived SQLite connection, fetches the path/mtime
map, runs ScanService, and emits a single ScanResult.
"""

import sqlite3

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.scan_service import ScanResult, ScanService
from app.db.photo_repository import PhotoRepository


class ScanWorker(QObject):
    finished = Signal(object)  # ScanResult

    def __init__(self, folder_path: str, db_path: str, parent=None):
        super().__init__(parent)
        self._folder = folder_path
        self._db_path = db_path

    @Slot()
    def run(self):
        result = ScanResult()
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                repo = PhotoRepository(conn)
                db_map = repo.get_path_mtime_map()
            finally:
                conn.close()
            result = ScanService().scan(self._folder, db_map)
        except Exception:
            result = ScanResult()
        finally:
            self.finished.emit(result)


class ScanController(QObject):
    finished = Signal(object)  # ScanResult

    def __init__(self, folder_path: str, db_path: str, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = ScanWorker(folder_path, db_path)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

    def start(self):
        self._thread.start()

    def wait(self, timeout_ms: int = 5000) -> bool:
        return self._thread.wait(timeout_ms)

    def _on_worker_finished(self, result: ScanResult):
        self.finished.emit(result)

    def _cleanup(self):
        self._worker.deleteLater()
        self._thread.deleteLater()
