"""Background pHash analysis worker.

Two-phase execution:
  Phase A – compute pHash for each unanalyzed photo (emits per-photo progress)
  Phase B – run similarity grouping, persist groups, emit grouping_finished
"""

import logging
import sqlite3
from typing import List

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.core.phash_service import PHashService
from app.db.group_repository import GroupRepository
from app.db.photo_repository import PhotoRepository

log = logging.getLogger(__name__)

_GROUP_TYPE = "similar"


class PHashWorker(QObject):
    phash_computed = Signal(int)      # photo_id
    progress = Signal(int, int)       # current, total
    grouping_finished = Signal(int)   # group_count
    finished = Signal()

    def __init__(
        self,
        folder_path: str,
        db_path: str,
        photo_ids: List[int],
        hamming_threshold: int = 10,
        parent=None,
    ):
        super().__init__(parent)
        self._folder = folder_path
        self._db_path = db_path
        self._photo_ids = photo_ids
        self._threshold = hamming_threshold
        self._cancel = False

    @Slot()
    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        log.info("PHashWorker.run started")
        try:
            self._run_inner()
        except Exception as e:
            log.exception("Exception in PHashWorker.run: %s", e)
        finally:
            log.info("PHashWorker.run finished")
            self.finished.emit()

    def _run_inner(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            repo = PhotoRepository(conn)
            svc = PHashService()
            total = len(self._photo_ids)

            # Phase A: compute hashes
            for i, photo_id in enumerate(self._photo_ids):
                if self._cancel:
                    log.info("PHashWorker cancelled during hashing")
                    return
                photo = repo.get_by_id(photo_id)
                if photo is None:
                    self.progress.emit(i + 1, total)
                    continue
                try:
                    hash_str = svc.compute_hash(self._folder, photo.relative_path)
                    if hash_str is not None:
                        repo.update_phash_hash(photo_id, hash_str)
                        self.phash_computed.emit(photo_id)
                except Exception as e:
                    log.debug("Error hashing photo %d: %s", photo_id, e)
                self.progress.emit(i + 1, total)

            if self._cancel:
                return

            # Phase B: group by similarity
            all_hashes = repo.get_all_phash_hashes()
            groups = PHashService.group_by_similarity(all_hashes, self._threshold)

            group_repo = GroupRepository(conn)
            group_repo.clear_groups_by_type(_GROUP_TYPE)

            for idx, members in enumerate(groups, 1):
                gid = group_repo.create_group(f"相似組 {idx}", _GROUP_TYPE)
                for photo_id in members:
                    group_repo.add_photo_to_group(photo_id, gid, is_best=False)

            log.info("PHash grouping done: %d groups", len(groups))
            self.grouping_finished.emit(len(groups))
        finally:
            conn.close()


class PHashController(QObject):
    """Owns QThread + PHashWorker pair."""
    phash_computed = Signal(int)
    progress = Signal(int, int)
    grouping_finished = Signal(int)
    finished = Signal()

    def __init__(
        self,
        folder_path: str,
        db_path: str,
        photo_ids: List[int],
        hamming_threshold: int = 10,
        parent=None,
    ):
        super().__init__(parent)
        self._worker = PHashWorker(folder_path, db_path, photo_ids, hamming_threshold)
        self._thread = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = QThread()
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.phash_computed.connect(self.phash_computed)
            self._worker.progress.connect(self.progress)
            self._worker.grouping_finished.connect(self.grouping_finished)
            self._worker.finished.connect(self._thread.quit)
            self._thread.finished.connect(self.finished)
            self._thread.finished.connect(self._cleanup)
        self._thread.start()

    def cancel(self) -> None:
        self._worker.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        if self._thread is None:
            return True
        return self._thread.wait(timeout_ms)

    def _cleanup(self) -> None:
        self._worker.deleteLater()
        self._thread.deleteLater()
