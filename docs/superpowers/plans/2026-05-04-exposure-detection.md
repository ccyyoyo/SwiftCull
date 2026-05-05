# Exposure Detection MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing ExposureService/ExposureWorker into the full product flow — manual "Analyze Exposure" trigger, EXPOSURE filter panel section, Loupe exposure label, and Loupe blur/exposure context preservation.

**Architecture:** Add a shared classifier helper to ExposureService (no stored DB column — thresholds are runtime parameters). Extend FilterService with an `exposure` dimension. Add EXPOSURE section to FilterPanel (emitting a 4-tuple signal). Add ExposureController lifecycle to GridView matching the BlurController pattern. Show exposure state in LoupeView's top-right label stack. Preserve blur+exposure filter context when Loupe re-filters on status/color changes.

**Tech Stack:** PySide6, SQLite (WAL), OpenCV via existing ExposureService, SettingsDB for thresholds.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/core/exposure_service.py` | Modify | Add `exposure_states()` and `exposure_display_state()` static helpers; change `compute_scores()` to return `Optional[ExposureResult]` on decode failure |
| `app/core/exposure_worker.py` | Modify | Skip DB write when `compute_scores()` returns `None`; add logging; adopt BlurController lazy-thread lifecycle |
| `app/core/filter_service.py` | Modify | Add `exposure` parameter and threshold params to `filter()`; call shared classifier |
| `app/db/photo_repository.py` | Modify | Add `get_exposure_unanalyzed_ids()` and `clear_exposure_scores()` |
| `app/utils/theme.py` | Modify | Add exposure state color constants |
| `app/ui/filter_panel.py` | Modify | Add EXPOSURE section; change `filter_changed` signal to emit 4-tuple `(statuses, colors, blur, exposure)` |
| `app/ui/grid_view.py` | Modify | Add ExposureController, manual trigger button, update all `_refresh()` and filter propagation to carry exposure; update `_on_loupe()` to pass exposure context |
| `app/ui/loupe_view.py` | Modify | Add exposure label below blur label; pass exposure filter to `FilterService.filter()`; preserve parent blur+exposure context |
| `tests/core/test_exposure_classifier.py` | Create | Unit tests for `exposure_states()` and `exposure_display_state()` |
| `tests/core/test_exposure_service_none.py` | Create | Verify `compute_scores()` returns `None` on missing file |
| `tests/db/test_photo_repository_exposure.py` | Create | Tests for `get_exposure_unanalyzed_ids()` and `clear_exposure_scores()` |
| `tests/core/test_filter_service_exposure.py` | Create | Tests for exposure filter dimension in FilterService |

---

## Task 1: Add shared exposure classifier helpers to ExposureService

**Files:**
- Modify: `app/core/exposure_service.py`
- Create: `tests/core/test_exposure_classifier.py`
- Create: `tests/core/test_exposure_service_none.py`

- [ ] **Step 1: Write failing classifier tests**

Create `tests/core/test_exposure_classifier.py`:

```python
import pytest
import numpy as np
import cv2


def _make_jpeg(tmp_path, name, pixel_value):
    arr = np.full((200, 200, 3), pixel_value, dtype=np.uint8)
    path = tmp_path / name
    cv2.imwrite(str(path), arr)
    return str(path)


def _photo(mean, over, under):
    from app.core.models import Photo
    return Photo(
        id=1, relative_path="x.jpg", filename="x.jpg", file_size=0,
        mtime=None, shot_at=None, imported_at=None,
        width=None, height=None, camera_model=None, lens_model=None,
        iso=None, aperture=None, shutter_speed=None, focal_length=None,
        blur_score=None,
        exposure_mean=mean,
        exposure_overexposed=over,
        exposure_underexposed=under,
    )


# --- exposure_states ---

def test_states_unanalyzed_when_all_none():
    from app.core.exposure_service import ExposureService
    p = _photo(None, None, None)
    assert ExposureService.exposure_states(p) == {"unanalyzed"}


def test_states_unanalyzed_when_any_none():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, None, 0.0)
    assert ExposureService.exposure_states(p) == {"unanalyzed"}


def test_states_normal_for_well_exposed():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.0, 0.0)
    assert ExposureService.exposure_states(p) == {"normal"}


def test_states_overexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(240.0, 0.05, 0.0)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" in states
    assert "normal" not in states


def test_states_underexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(20.0, 0.0, 0.05)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "underexposed" in states
    assert "normal" not in states


def test_states_black_frame():
    from app.core.exposure_service import ExposureService
    p = _photo(3.0, 0.0, 0.95)
    states = ExposureService.exposure_states(
        p,
        clip_threshold=0.01,
        black_mean_threshold=8.0,
        black_shadow_threshold=0.90,
    )
    assert "black_frame" in states
    assert "underexposed" in states  # black_frame is underexposed subtype


def test_states_black_frame_not_included_in_overexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(3.0, 0.0, 0.95)
    states = ExposureService.exposure_states(p)
    assert "overexposed" not in states


def test_states_mixed_over_and_under():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.05, 0.05)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" in states
    assert "underexposed" in states


def test_states_boundary_exact_clip_threshold_not_overexposed():
    from app.core.exposure_service import ExposureService
    # Exactly at threshold is NOT overexposed (strict >)
    p = _photo(200.0, 0.01, 0.0)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" not in states


def test_states_boundary_just_above_clip_threshold_is_overexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(200.0, 0.011, 0.0)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" in states


# --- exposure_display_state priority ---

def test_display_state_black_frame_wins_over_underexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(3.0, 0.0, 0.95)
    assert ExposureService.exposure_display_state(p) == "black_frame"


def test_display_state_overexposed_wins_over_underexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.05, 0.05)
    assert ExposureService.exposure_display_state(p, clip_threshold=0.01) == "overexposed"


def test_display_state_normal():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.0, 0.0)
    assert ExposureService.exposure_display_state(p) == "normal"


def test_display_state_unanalyzed():
    from app.core.exposure_service import ExposureService
    p = _photo(None, None, None)
    assert ExposureService.exposure_display_state(p) == "unanalyzed"
```

- [ ] **Step 2: Write failing None-return tests**

Create `tests/core/test_exposure_service_none.py`:

```python
def test_compute_scores_returns_none_for_missing_file(tmp_path):
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "nonexistent.jpg")
    assert result is None


def test_compute_scores_returns_result_for_valid_file(tmp_path):
    import numpy as np
    import cv2
    arr = np.full((100, 100, 3), 128, dtype=np.uint8)
    (tmp_path / "img.jpg").write_bytes(cv2.imencode(".jpg", arr)[1].tobytes())
    from app.core.exposure_service import ExposureService, ExposureResult
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "img.jpg")
    assert isinstance(result, ExposureResult)
```

- [ ] **Step 3: Run tests to verify they fail**

```
pytest tests/core/test_exposure_classifier.py tests/core/test_exposure_service_none.py -v
```

Expected: `AttributeError: type object 'ExposureService' has no attribute 'exposure_states'` and `AssertionError` on None test (currently returns `_ZERO` not `None`).

- [ ] **Step 4: Update ExposureService**

Replace `app/core/exposure_service.py` with:

```python
import os
from dataclasses import dataclass
from typing import List, Optional, Set

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

_HIGHLIGHT_THRESHOLD = 250
_SHADOW_THRESHOLD = 5
_EPSILON = 1e-9


@dataclass
class ExposureResult:
    mean_brightness: float
    overexposed_fraction: float
    underexposed_fraction: float


class ExposureService:
    def compute_scores(self, root_path: str, relative_path: str) -> Optional[ExposureResult]:
        """Analyse luminance histogram. Returns None if cv2 unavailable or image unreadable."""
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            from app.core.image_io import read_image_color
            img = read_image_color(abs_path)
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            total = gray.size
            mean_brightness = float(gray.mean())
            overexposed_fraction = float(np.sum(gray >= _HIGHLIGHT_THRESHOLD) / total)
            underexposed_fraction = float(np.sum(gray <= _SHADOW_THRESHOLD) / total)
            return ExposureResult(mean_brightness, overexposed_fraction, underexposed_fraction)
        except Exception:
            return None

    def is_overexposed(self, result: ExposureResult, fraction_threshold: float = 0.01) -> bool:
        return result.overexposed_fraction > fraction_threshold

    def is_underexposed(self, result: ExposureResult, fraction_threshold: float = 0.01) -> bool:
        return result.underexposed_fraction > fraction_threshold

    def relative_overexposed_threshold(self, fractions: List[float], top_percent: float) -> float:
        if not fractions:
            return 1.0
        sorted_fracs = sorted(fractions, reverse=True)
        idx = max(0, int(len(sorted_fracs) * top_percent / 100.0) - 1)
        return sorted_fracs[idx] - _EPSILON

    def relative_underexposed_threshold(self, fractions: List[float], top_percent: float) -> float:
        if not fractions:
            return 1.0
        sorted_fracs = sorted(fractions, reverse=True)
        idx = max(0, int(len(sorted_fracs) * top_percent / 100.0) - 1)
        return sorted_fracs[idx] - _EPSILON

    @staticmethod
    def exposure_states(
        photo,
        clip_threshold: float = 0.01,
        black_mean_threshold: float = 8.0,
        black_shadow_threshold: float = 0.90,
    ) -> Set[str]:
        """Return all matching exposure states for a photo. photo must have
        exposure_mean, exposure_overexposed, exposure_underexposed attributes."""
        if (photo.exposure_mean is None
                or photo.exposure_overexposed is None
                or photo.exposure_underexposed is None):
            return {"unanalyzed"}

        states: Set[str] = set()
        if photo.exposure_overexposed > clip_threshold:
            states.add("overexposed")
        is_under = photo.exposure_underexposed > clip_threshold
        is_black = (
            photo.exposure_mean <= black_mean_threshold
            and photo.exposure_underexposed > black_shadow_threshold
        )
        if is_black:
            states.add("black_frame")
            states.add("underexposed")
        elif is_under:
            states.add("underexposed")
        if not states:
            states.add("normal")
        return states

    @staticmethod
    def exposure_display_state(
        photo,
        clip_threshold: float = 0.01,
        black_mean_threshold: float = 8.0,
        black_shadow_threshold: float = 0.90,
    ) -> str:
        """Return single highest-priority state for UI display.
        Priority: unanalyzed > black_frame > overexposed > underexposed > normal."""
        states = ExposureService.exposure_states(
            photo, clip_threshold, black_mean_threshold, black_shadow_threshold
        )
        for priority in ("unanalyzed", "black_frame", "overexposed", "underexposed", "normal"):
            if priority in states:
                return priority
        return "unanalyzed"
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/core/test_exposure_classifier.py tests/core/test_exposure_service_none.py -v
```

Expected: all pass.

- [ ] **Step 6: Verify existing exposure tests still pass**

```
pytest tests/core/test_exposure_service.py -v
```

Expected: the one test checking `result.mean_brightness == 0.0` for missing file will now fail — update it:

In `tests/core/test_exposure_service.py`, change `test_compute_scores_missing_file_returns_zeros` to:

```python
def test_compute_scores_missing_file_returns_none(tmp_path):
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "nonexistent.jpg")
    assert result is None
```

Run again:

```
pytest tests/core/test_exposure_service.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```
git add app/core/exposure_service.py tests/core/test_exposure_classifier.py tests/core/test_exposure_service_none.py tests/core/test_exposure_service.py
git commit -m "feat: add exposure_states/exposure_display_state classifiers; compute_scores returns None on failure"
```

---

## Task 2: Update ExposureWorker to skip DB write on None

**Files:**
- Modify: `app/core/exposure_worker.py`

- [ ] **Step 1: Update `_run_inner` in ExposureWorker**

In `app/core/exposure_worker.py`, replace the `_run_inner` method:

```python
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
```

Also add logging to `run()`:

```python
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
```

- [ ] **Step 2: Adopt BlurController lazy-thread lifecycle in ExposureController**

Replace `ExposureController` class entirely:

```python
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
```

- [ ] **Step 3: Run existing tests**

```
pytest tests/ -v -k "exposure"
```

Expected: all pass.

- [ ] **Step 4: Commit**

```
git add app/core/exposure_worker.py
git commit -m "feat: ExposureWorker skips DB write on None result; ExposureController adopts BlurController lifecycle"
```

---

## Task 3: Add repository helpers for exposure unanalyzed IDs and clearing scores

**Files:**
- Modify: `app/db/photo_repository.py`
- Create: `tests/db/test_photo_repository_exposure.py`

- [ ] **Step 1: Write failing tests**

Create `tests/db/test_photo_repository_exposure.py`:

```python
import sqlite3
import pytest
from app.db.connection import init_db
from app.db.photo_repository import PhotoRepository
from app.core.models import Photo


def _make_repo(tmp_path):
    db_path = tmp_path / "project.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return PhotoRepository(conn), conn


def _insert_photo(repo, relative_path="a.jpg"):
    from datetime import datetime, timezone
    p = Photo(
        id=None, relative_path=relative_path, filename=relative_path,
        file_size=100, mtime=None, shot_at=None,
        imported_at=datetime.now(timezone.utc).isoformat(),
        width=None, height=None, camera_model=None, lens_model=None,
        iso=None, aperture=None, shutter_speed=None, focal_length=None,
        blur_score=None, exposure_mean=None, exposure_overexposed=None,
        exposure_underexposed=None,
    )
    return repo.insert(p)


def test_get_exposure_unanalyzed_ids_returns_all_when_no_scores(tmp_path):
    repo, _ = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    ids = repo.get_exposure_unanalyzed_ids()
    assert pid in ids


def test_get_exposure_unanalyzed_ids_excludes_analyzed(tmp_path):
    repo, _ = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    repo.update_exposure_scores(pid, 128.0, 0.0, 0.0)
    ids = repo.get_exposure_unanalyzed_ids()
    assert pid not in ids


def test_get_exposure_unanalyzed_ids_includes_partially_null(tmp_path):
    repo, conn = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    # Set only mean, leave over/under NULL
    conn.execute("UPDATE photos SET exposure_mean=128.0 WHERE id=?", (pid,))
    conn.commit()
    ids = repo.get_exposure_unanalyzed_ids()
    assert pid in ids


def test_clear_exposure_scores_sets_all_null(tmp_path):
    repo, _ = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    repo.update_exposure_scores(pid, 128.0, 0.01, 0.02)
    repo.clear_exposure_scores(pid)
    photo = repo.get_by_id(pid)
    assert photo.exposure_mean is None
    assert photo.exposure_overexposed is None
    assert photo.exposure_underexposed is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/db/test_photo_repository_exposure.py -v
```

Expected: `AttributeError: 'PhotoRepository' object has no attribute 'get_exposure_unanalyzed_ids'`

- [ ] **Step 3: Add methods to PhotoRepository**

In `app/db/photo_repository.py`, after `get_unanalyzed_ids()` (line 86), add:

```python
def get_exposure_unanalyzed_ids(self) -> list[int]:
    """Return IDs where any exposure analysis field is NULL."""
    rows = self._conn.execute(
        "SELECT id FROM photos WHERE exposure_mean IS NULL"
        " OR exposure_overexposed IS NULL"
        " OR exposure_underexposed IS NULL"
    ).fetchall()
    return [int(r["id"]) for r in rows]

def clear_exposure_scores(self, photo_id: int) -> None:
    """Clear stored exposure fields so the photo will be re-analyzed."""
    self._conn.execute(
        "UPDATE photos SET exposure_mean=NULL, exposure_overexposed=NULL,"
        " exposure_underexposed=NULL WHERE id=?",
        (photo_id,),
    )
    self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/db/test_photo_repository_exposure.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add app/db/photo_repository.py tests/db/test_photo_repository_exposure.py
git commit -m "feat: add get_exposure_unanalyzed_ids and clear_exposure_scores to PhotoRepository"
```

---

## Task 4: Add exposure filter to FilterService

**Files:**
- Modify: `app/core/filter_service.py`
- Create: `tests/core/test_filter_service_exposure.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_filter_service_exposure.py`:

```python
import pytest
from unittest.mock import MagicMock
from app.core.models import Photo
from app.core.filter_service import FilterService


def _photo(pid, mean, over, under):
    return Photo(
        id=pid, relative_path=f"{pid}.jpg", filename=f"{pid}.jpg",
        file_size=0, mtime=None, shot_at=None, imported_at=None,
        width=None, height=None, camera_model=None, lens_model=None,
        iso=None, aperture=None, shutter_speed=None, focal_length=None,
        blur_score=None,
        exposure_mean=mean,
        exposure_overexposed=over,
        exposure_underexposed=under,
    )


def _make_svc(photos):
    photo_repo = MagicMock()
    photo_repo.get_all.return_value = photos
    tag_repo = MagicMock()
    tag_repo.get_by_photo_id.return_value = None
    return FilterService(photo_repo, tag_repo)


def test_exposure_filter_none_returns_all():
    p1 = _photo(1, 128.0, 0.0, 0.0)
    svc = _make_svc([p1])
    result = svc.filter(exposure=None)
    assert len(result) == 1


def test_exposure_filter_unanalyzed():
    p_none = _photo(1, None, None, None)
    p_normal = _photo(2, 128.0, 0.0, 0.0)
    svc = _make_svc([p_none, p_normal])
    result = svc.filter(exposure=["unanalyzed"])
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_overexposed():
    p_over = _photo(1, 240.0, 0.05, 0.0)
    p_normal = _photo(2, 128.0, 0.0, 0.0)
    svc = _make_svc([p_over, p_normal])
    result = svc.filter(exposure=["overexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_underexposed():
    p_under = _photo(1, 20.0, 0.0, 0.05)
    p_normal = _photo(2, 128.0, 0.0, 0.0)
    svc = _make_svc([p_under, p_normal])
    result = svc.filter(exposure=["underexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_black_frame():
    p_black = _photo(1, 3.0, 0.0, 0.95)
    p_dark = _photo(2, 20.0, 0.0, 0.05)  # underexposed but not black
    svc = _make_svc([p_black, p_dark])
    result = svc.filter(
        exposure=["black_frame"],
        exposure_clip_threshold=0.01,
        exposure_black_mean_threshold=8.0,
        exposure_black_shadow_threshold=0.90,
    )
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_underexposed_includes_black_frame():
    p_black = _photo(1, 3.0, 0.0, 0.95)
    svc = _make_svc([p_black])
    result = svc.filter(
        exposure=["underexposed"],
        exposure_clip_threshold=0.01,
        exposure_black_mean_threshold=8.0,
        exposure_black_shadow_threshold=0.90,
    )
    assert len(result) == 1


def test_exposure_filter_normal():
    p_normal = _photo(1, 128.0, 0.0, 0.0)
    p_over = _photo(2, 240.0, 0.05, 0.0)
    svc = _make_svc([p_normal, p_over])
    result = svc.filter(exposure=["normal"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_or_semantics_multiple_values():
    p_over = _photo(1, 240.0, 0.05, 0.0)
    p_under = _photo(2, 20.0, 0.0, 0.05)
    p_normal = _photo(3, 128.0, 0.0, 0.0)
    svc = _make_svc([p_over, p_under, p_normal])
    result = svc.filter(exposure=["overexposed", "underexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 in ids
    assert 3 not in ids


def test_exposure_and_status_and_semantics():
    from unittest.mock import MagicMock
    from app.core.models import Tag
    p_over_pick = _photo(1, 240.0, 0.05, 0.0)
    p_over_reject = _photo(2, 240.0, 0.05, 0.0)

    photo_repo = MagicMock()
    photo_repo.get_all.return_value = [p_over_pick, p_over_reject]
    tag_repo = MagicMock()

    tag_pick = Tag(photo_id=1, status="pick", color=None, updated_at=None)
    tag_reject = Tag(photo_id=2, status="reject", color=None, updated_at=None)
    tag_repo.get_by_photo_id.side_effect = lambda pid: {1: tag_pick, 2: tag_reject}[pid]

    svc = FilterService(photo_repo, tag_repo)
    result = svc.filter(statuses=["pick"], exposure=["overexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/core/test_filter_service_exposure.py -v
```

Expected: `TypeError: filter() got an unexpected keyword argument 'exposure'`

- [ ] **Step 3: Update FilterService**

Replace `app/core/filter_service.py`:

```python
import logging
from typing import List, Optional
from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.models import Photo

log = logging.getLogger(__name__)


class FilterService:
    def __init__(self, photo_repo: PhotoRepository, tag_repo: TagRepository):
        self._photos = photo_repo
        self._tags = tag_repo

    def filter(
        self,
        statuses: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        blur: Optional[List[str]] = None,
        exposure: Optional[List[str]] = None,
        blur_mode: str = "fixed",
        blur_fixed_threshold: float = 100.0,
        blur_relative_percent: float = 20.0,
        exposure_clip_threshold: float = 0.01,
        exposure_black_mean_threshold: float = 8.0,
        exposure_black_shadow_threshold: float = 0.90,
    ) -> List[Photo]:
        log.debug(
            "filter called: statuses=%s colors=%s blur=%s exposure=%s",
            statuses, colors, blur, exposure,
        )
        all_photos = self._photos.get_all()
        if not statuses and not colors and not blur and not exposure:
            return all_photos

        effective_threshold = blur_fixed_threshold
        if blur and blur_mode == "relative":
            from app.core.blur_service import BlurService
            scores = [p.blur_score for p in all_photos if p.blur_score is not None]
            effective_threshold = BlurService().relative_threshold(scores, blur_relative_percent)

        result = []
        for photo in all_photos:
            tag = self._tags.get_by_photo_id(photo.id)
            current_status = tag.status if tag else None
            current_color = tag.color if tag else None

            if statuses:
                if "untagged" in statuses:
                    if current_status is not None:
                        continue
                elif current_status not in statuses:
                    continue

            if colors and current_color not in colors:
                continue

            if blur:
                score = photo.blur_score
                passes = False
                if "unanalyzed" in blur and score is None:
                    passes = True
                if "blurry" in blur and score is not None and score < effective_threshold:
                    passes = True
                if "sharp" in blur and score is not None and score >= effective_threshold:
                    passes = True
                if not passes:
                    continue

            if exposure:
                from app.core.exposure_service import ExposureService
                states = ExposureService.exposure_states(
                    photo,
                    clip_threshold=exposure_clip_threshold,
                    black_mean_threshold=exposure_black_mean_threshold,
                    black_shadow_threshold=exposure_black_shadow_threshold,
                )
                if not states.intersection(set(exposure)):
                    continue

            result.append(photo)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/core/test_filter_service_exposure.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```
git add app/core/filter_service.py tests/core/test_filter_service_exposure.py
git commit -m "feat: add exposure filter dimension to FilterService"
```

---

## Task 5: Add exposure theme colors

**Files:**
- Modify: `app/utils/theme.py`

- [ ] **Step 1: Add exposure color constants**

In `app/utils/theme.py`, after the `BLUR_*` constants (line 24), add:

```python
EXPOSURE_OVEREXPOSED = "#FFB347"  # warm amber
EXPOSURE_UNDEREXPOSED = "#64B5F6"  # cool blue
EXPOSURE_BLACK        = "#FF4D4D"  # red
EXPOSURE_NORMAL       = "#3ddc84"  # muted green (same as PICK_CLR)
EXPOSURE_UNKNOWN      = "#555555"  # muted gray (same as BLUR_UNKNOWN)
```

- [ ] **Step 2: Verify theme imports in other files still work**

```
python -c "from app.utils.theme import EXPOSURE_OVEREXPOSED, EXPOSURE_UNDEREXPOSED, EXPOSURE_BLACK, EXPOSURE_NORMAL, EXPOSURE_UNKNOWN; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```
git add app/utils/theme.py
git commit -m "feat: add exposure state color constants to theme"
```

---

## Task 6: Add EXPOSURE section to FilterPanel and update signal

**Files:**
- Modify: `app/ui/filter_panel.py`

The `filter_changed` signal currently emits `(list, list, list)` = `(statuses, colors, blur)`.
We need to change it to emit `(list, list, list, list)` = `(statuses, colors, blur, exposure)`.

- [ ] **Step 1: Update FilterPanel**

Replace `app/ui/filter_panel.py` with:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox,
    QPushButton, QSizePolicy, QHBoxLayout, QScrollArea
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Signal, Qt, QRect
from app.utils.theme import (
    BG_PANEL, BG_HOVER, BORDER, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    STATUS_ICON, STATUS_COLOR, COLOR_DOT,
    PICK_CLR, REJECT_CLR, MAYBE_CLR,
    BLUR_BLURRY, BLUR_SHARP, BLUR_UNKNOWN,
    EXPOSURE_OVEREXPOSED, EXPOSURE_UNDEREXPOSED, EXPOSURE_BLACK, EXPOSURE_NORMAL, EXPOSURE_UNKNOWN,
)

STATUSES = ["pick", "reject", "maybe", "untagged"]
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

PANEL_WIDTH = 160
TAB_WIDTH = 28


class _ColorDotCheckBox(QWidget):
    """Custom checkbox showing color dot + label."""
    stateChanged = Signal(int)

    def __init__(self, color_key: str, parent=None):
        super().__init__(parent)
        self._color_key = color_key
        self._checked = False
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool):
        self._checked = v
        self.update()
        self.stateChanged.emit(2 if v else 0)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.stateChanged.emit(2 if self._checked else 0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dot_color = QColor(COLOR_DOT.get(self._color_key, "#888"))
        if self._checked:
            p.setBrush(dot_color)
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(dot_color, 1.5))
        p.drawEllipse(4, 5, 12, 12)
        p.setPen(QColor(TEXT_PRIMARY if self._checked else TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRect(22, 0, self.width() - 22, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._color_key)
        p.end()


class _StatusCheckBox(QWidget):
    """Custom checkbox showing status icon + label."""
    stateChanged = Signal(int)

    def __init__(self, status_key: str, parent=None):
        super().__init__(parent)
        self._key = status_key
        self._checked = False
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool):
        self._checked = v
        self.update()
        self.stateChanged.emit(2 if v else 0)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.stateChanged.emit(2 if self._checked else 0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._key == "untagged":
            icon_color = QColor(TEXT_MUTED)
            icon_char = "—"
        else:
            icon_color = QColor(STATUS_COLOR.get(self._key, "#888"))
            icon_char = STATUS_ICON.get(self._key, "?")

        if self._checked:
            p.setBrush(icon_color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(2, 3, 16, 16)
            p.setPen(QColor("#000"))
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(icon_color, 1.5))
            p.drawEllipse(2, 3, 16, 16)
            p.setPen(icon_color)

        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRect(2, 3, 16, 16), Qt.AlignCenter, icon_char)
        p.setPen(QColor(TEXT_PRIMARY if self._checked else TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRect(24, 0, self.width() - 24, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._key.capitalize())
        p.end()


class _CollapsedTab(QWidget):
    """Vertical tab shown when panel is collapsed."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(TAB_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("展開篩選面板")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.fillRect(self.rect(), QColor(BG_PANEL))
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        p.fillRect(0, 0, self.width() - 1, self.height(), QColor(BG_PANEL))
        p.save()
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(-90)
        font = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(font)
        p.setPen(QColor(TEXT_SECONDARY))
        text = "▶  FILTER"
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        p.drawText(int(-tw / 2), int(th / 3), text)
        p.restore()
        p.end()

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


class FilterPanel(QWidget):
    filter_changed = Signal(list, list, list, list)  # statuses, colors, blur, exposure

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._expanded = True
        self._status_checks: dict[str, _StatusCheckBox] = {}
        self._color_checks: dict[str, _ColorDotCheckBox] = {}
        self._blur_checks: dict = {}
        self._exposure_checks: dict = {}

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"background:{BG_PANEL};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._collapsed_tab = _CollapsedTab()
        self._collapsed_tab.clicked.connect(self._toggle)
        self._collapsed_tab.hide()
        root.addWidget(self._collapsed_tab)

        self._panel_body = QWidget()
        self._panel_body.setFixedWidth(PANEL_WIDTH)
        self._panel_body.setStyleSheet(
            f"background:{BG_PANEL}; border-right:1px solid #2a2a2a;"
        )
        body_layout = QVBoxLayout(self._panel_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(f"background:#1e1e1e; border-bottom:1px solid #2a2a2a;")
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(10, 0, 6, 0)
        title_lbl = QLabel("FILTER")
        title_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:10px; letter-spacing:2px; font-weight:600;"
        )
        hrow.addWidget(title_lbl)
        hrow.addStretch()
        self._toggle_btn = QPushButton("«")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_SECONDARY}; border:none;"
            f" font-size:14px; padding:0;"
        )
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        hrow.addWidget(self._toggle_btn)
        body_layout.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content = QWidget()
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(2)

        # STATUS section
        sec1 = QLabel("STATUS")
        sec1.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec1)
        for s in STATUSES:
            cb = _StatusCheckBox(s)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[s] = cb
            cl.addWidget(cb)

        cl.addSpacing(8)

        # COLOR section
        sec2 = QLabel("COLOR")
        sec2.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec2)
        for c in COLORS:
            cb = _ColorDotCheckBox(c)
            cb.stateChanged.connect(self._emit_filter)
            self._color_checks[c] = cb
            cl.addWidget(cb)

        cl.addSpacing(8)
        clear_btn = QPushButton("清除篩選")
        clear_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_SECONDARY}; border:1px solid #333;"
            f" border-radius:3px; padding:4px 8px; font-size:10px;"
        )
        clear_btn.clicked.connect(self._clear_all)
        cl.addWidget(clear_btn)

        cl.addSpacing(8)

        # BLUR section
        sec3 = QLabel("BLUR")
        sec3.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec3)

        blur_header_w = QWidget()
        blur_header_l = QHBoxLayout(blur_header_w)
        blur_header_l.setContentsMargins(0, 0, 0, 0)
        blur_header_l.setSpacing(4)
        blur_header_l.addStretch()
        gear_btn = QPushButton("⚙")
        gear_btn.setFixedSize(18, 18)
        gear_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_MUTED}; border:none; font-size:11px; padding:0;"
        )
        gear_btn.setCursor(Qt.PointingHandCursor)
        gear_btn.setToolTip("模糊偵測設定")
        gear_btn.clicked.connect(self._open_blur_settings)
        blur_header_l.addWidget(gear_btn)
        cl.addWidget(blur_header_w)

        for blur_key, label in [("blurry", "模糊"), ("sharp", "清晰"), ("unanalyzed", "未分析")]:
            cb = QCheckBox(label)
            cb.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px;")
            cb.stateChanged.connect(self._emit_filter)
            self._blur_checks[blur_key] = cb
            cl.addWidget(cb)

        cl.addSpacing(8)

        # EXPOSURE section
        sec4 = QLabel("EXPOSURE")
        sec4.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec4)

        exposure_items = [
            ("overexposed",  "過曝", EXPOSURE_OVEREXPOSED),
            ("underexposed", "欠曝", EXPOSURE_UNDEREXPOSED),
            ("black_frame",  "純黑", EXPOSURE_BLACK),
            ("normal",       "正常", EXPOSURE_NORMAL),
            ("unanalyzed",   "未分析", EXPOSURE_UNKNOWN),
        ]
        for exp_key, label, color in exposure_items:
            cb = QCheckBox(label)
            cb.setStyleSheet(f"color:{color}; font-size:10px;")
            cb.stateChanged.connect(self._emit_filter)
            self._exposure_checks[exp_key] = cb
            cl.addWidget(cb)

        cl.addStretch()

        scroll.setWidget(self._content)
        body_layout.addWidget(scroll, stretch=1)
        root.addWidget(self._panel_body)

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._collapsed_tab.hide()
            self._panel_body.show()
        else:
            self._panel_body.hide()
            self._collapsed_tab.show()

    def _emit_filter(self):
        if getattr(self, "_suppress", False):
            return
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        blur = [k for k, cb in self._blur_checks.items() if cb.isChecked()]
        exposure = [k for k, cb in self._exposure_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors, blur, exposure)

    def _clear_all(self):
        for cb in (list(self._status_checks.values())
                   + list(self._color_checks.values())
                   + list(self._blur_checks.values())
                   + list(self._exposure_checks.values())):
            cb.setChecked(False)

    def _open_blur_settings(self):
        from app.ui.blur_settings_dialog import BlurSettingsDialog
        if self._settings is None:
            return
        dlg = BlurSettingsDialog(self._settings, self)
        dlg.settings_changed.connect(lambda *_: self._emit_filter())
        dlg.exec()

    def set_filter(self, statuses, colors):
        """Programmatically reflect external filter changes without re-emitting."""
        wanted_s = set(statuses or [])
        wanted_c = set(colors or [])
        self._suppress = True
        try:
            for s, cb in self._status_checks.items():
                cb.setChecked(s in wanted_s)
            for c, cb in self._color_checks.items():
                cb.setChecked(c in wanted_c)
        finally:
            self._suppress = False
```

- [ ] **Step 2: Run the application and verify FilterPanel renders**

```
python main.py
```

Open a folder. Verify left panel shows STATUS, COLOR, BLUR, and new EXPOSURE section with 5 checkboxes. Scroll the panel if needed. Click each exposure checkbox — no crash.

- [ ] **Step 3: Commit**

```
git add app/ui/filter_panel.py
git commit -m "feat: add EXPOSURE filter section to FilterPanel; filter_changed now emits 4-tuple"
```

---

## Task 7: Update GridView to handle 4-tuple filter_changed and add ExposureController

**Files:**
- Modify: `app/ui/grid_view.py`

The `FilterPanel.filter_changed` signal now emits `(statuses, colors, blur, exposure)`.
GridView's `_on_filter_changed` must accept 4 args. `_refresh` must pass exposure to FilterService.
Also add: ExposureController wiring, manual "分析曝光" button, exposure settings read.

- [ ] **Step 1: Update GridView**

In `app/ui/grid_view.py`:

**1a. Add `_exposure_ctrl = None` to `__init__`** (after `self._blur_ctrl = None` on line 81):

```python
self._exposure_ctrl = None
self._current_exposure = None
```

**1b. Add exposure settings helper** (after `_blur_settings()` method, around line 299):

```python
def _exposure_settings(self):
    clip = float(self._settings.get("exposure_clip_threshold", 0.01))
    black_mean = float(self._settings.get("exposure_black_mean_threshold", 8.0))
    black_shadow = float(self._settings.get("exposure_black_shadow_threshold", 0.90))
    return clip, black_mean, black_shadow
```

**1c. Update `_refresh` signature and body** (replace lines 279–293):

```python
def _refresh(self, statuses=None, colors=None, blur=None, exposure=None,
             blur_mode=None, blur_fixed_threshold=None,
             blur_relative_percent=None):
    self._current_statuses = statuses
    self._current_colors = colors
    self._current_blur = blur
    self._current_exposure = exposure
    if blur_mode is None or blur_fixed_threshold is None or blur_relative_percent is None:
        blur_mode, blur_fixed_threshold, blur_relative_percent = self._blur_settings()
    clip, black_mean, black_shadow = self._exposure_settings()
    photos = self._filter_svc.filter(
        statuses=statuses, colors=colors, blur=blur, exposure=exposure,
        blur_mode=blur_mode,
        blur_fixed_threshold=blur_fixed_threshold,
        blur_relative_percent=blur_relative_percent,
        exposure_clip_threshold=clip,
        exposure_black_mean_threshold=black_mean,
        exposure_black_shadow_threshold=black_shadow,
    )
    self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)
```

**1d. Add "分析曝光" button** in the toolbar (after the `self._analyse_btn` block, before `self._split_btn`). In `__init__`, around line 176 after:
```python
        self._analyse_btn.clicked.connect(self._on_analyse_clicked)
        tb.addWidget(self._analyse_btn)
```
Add:
```python
        self._exposure_btn = QPushButton("◉  分析曝光")
        self._exposure_btn.setCursor(Qt.PointingHandCursor)
        self._exposure_btn.setToolTip("分析尚未計算曝光分數的照片")
        self._exposure_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
            f" border:1px solid #333; border-radius:3px; padding:3px 10px;"
            f" font-size:10px; }}"
            f"QPushButton:hover:!disabled {{ background:#2a2a2a; color:#ddd;"
            f" border-color:#555; }}"
            f"QPushButton:disabled {{ color:{TEXT_MUTED}; border-color:#222; }}"
        )
        self._exposure_btn.clicked.connect(self._on_exposure_clicked)
        tb.addWidget(self._exposure_btn)
```

**1e. Update `_on_filter_changed`** (replace the existing method at line 427):

```python
def _on_filter_changed(self, statuses, colors, blur, exposure):
    self._current_blur = blur or None
    self._current_exposure = exposure or None
    mode, threshold, percent = self._blur_settings()
    self._refresh(
        statuses or None, colors or None, blur or None, exposure or None,
        blur_mode=mode,
        blur_fixed_threshold=threshold,
        blur_relative_percent=percent,
    )
```

**1f. Update `_on_loupe_filter_changed`** (replace the existing method at line 510):

```python
def _on_loupe_filter_changed(self, statuses: list, colors: list):
    self._filter_panel.set_filter(statuses, colors)
    mode, threshold, percent = self._blur_settings()
    self._refresh(
        statuses or None, colors or None, self._current_blur, self._current_exposure,
        blur_mode=mode,
        blur_fixed_threshold=threshold,
        blur_relative_percent=percent,
    )
```

**1g. Update `_on_loupe`** — pass `initial_exposure` to LoupeView (replace the `loupe = LoupeView(...)` call, around line 495):

```python
        loupe = LoupeView(
            photo_ids, photo_ids.index(photo_id),
            self._folder, self._photo_repo,
            self._tag_repo, self._tag_svc,
            filter_svc=self._filter_svc,
            initial_statuses=self._current_statuses,
            initial_colors=self._current_colors,
            initial_blur=self._current_blur,
            initial_exposure=self._current_exposure,
            settings=self._settings,
        )
```

Also update the `filter()` call just before the LoupeView construction (around line 484):

```python
        clip, black_mean, black_shadow = self._exposure_settings()
        photos = self._filter_svc.filter(
            statuses=self._current_statuses,
            colors=self._current_colors,
            blur=self._current_blur,
            exposure=self._current_exposure,
            blur_mode=mode,
            blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
            exposure_clip_threshold=clip,
            exposure_black_mean_threshold=black_mean,
            exposure_black_shadow_threshold=black_shadow,
        )
```

**1h. Add ExposureController methods** (after `stop_blur_analysis` at end of file):

```python
    def _on_exposure_clicked(self):
        if self._db_path:
            self._start_exposure_analysis(self._db_path)

    def _start_exposure_analysis(self, db_path: str):
        import sqlite3 as _sq
        from app.core.exposure_worker import ExposureController
        from app.db.photo_repository import PhotoRepository as _PR
        if self._exposure_ctrl is not None:
            return
        conn = _sq.connect(db_path)
        conn.row_factory = _sq.Row
        repo = _PR(conn)
        photo_ids = repo.get_exposure_unanalyzed_ids()
        conn.close()
        if not photo_ids:
            return
        self._exposure_btn.setEnabled(False)
        self._exposure_ctrl = ExposureController(self._folder, db_path, photo_ids)
        self._exposure_ctrl.photo_exposure_updated.connect(self._on_photo_exposure_updated)
        self._exposure_ctrl.finished.connect(self._on_exposure_finished)
        self._exposure_ctrl.start()

    def _on_photo_exposure_updated(self, photo_id: int, mean: float, over: float, under: float):
        self._grid.update_item_tag(photo_id)

    def _on_exposure_finished(self):
        self._exposure_ctrl = None
        self._exposure_btn.setEnabled(True)

    def stop_exposure_analysis(self, timeout_ms: int = 3000):
        ctrl = self._exposure_ctrl
        if ctrl is None:
            return
        ctrl.cancel()
        ctrl.wait(timeout_ms)
```

- [ ] **Step 2: Update `closeEvent` in `main_window.py` to also stop exposure**

Find `app/ui/main_window.py` and locate where `stop_blur_analysis` is called in `closeEvent`. Add a call to `stop_exposure_analysis` immediately after:

```python
self._grid_view.stop_exposure_analysis()
```

- [ ] **Step 3: Run the application and verify**

```
python main.py
```

Open a folder. Verify:
- "◉  分析曝光" button appears in toolbar
- Clicking it triggers background exposure analysis (no crash, button disables while running)
- EXPOSURE filter checkboxes update grid after analysis

- [ ] **Step 4: Commit**

```
git add app/ui/grid_view.py app/ui/main_window.py
git commit -m "feat: wire ExposureController and Analyze Exposure button into GridView"
```

---

## Task 8: Show exposure label in LoupeView and preserve exposure filter context

**Files:**
- Modify: `app/ui/loupe_view.py`

LoupeView needs:
1. Accept `initial_exposure` parameter.
2. Pass `exposure` to `FilterService.filter()` in `_on_filter_changed`.
3. Add an exposure label below the blur label (top-right overlay).
4. Call `_update_exposure_label()` in `_load_current()`.

- [ ] **Step 1: Update LoupeView**

In `app/ui/loupe_view.py`:

**1a. Add `initial_exposure` parameter to `__init__`** (add after `initial_blur` parameter, around line 113):

```python
                 initial_exposure: Optional[list[str]] = None,
```

And in the body, after `self._blur = list(initial_blur) if initial_blur else []`:

```python
        self._exposure = list(initial_exposure) if initial_exposure else []
```

**1b. Add exposure label widget** (after the `_blur_label` block, around line 166):

```python
        # --- exposure label overlay (top-right, below blur) ---
        self._exposure_label = QLabel("")
        self._exposure_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._exposure_label.setStyleSheet(
            "color: #aaa; font-size: 13px; background: transparent; padding: 4px;"
        )
        self._exposure_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._exposure_label.setParent(self)
        self._exposure_label.resize(200, 30)
        self._exposure_label.raise_()
```

**1c. Position exposure label in `resizeEvent`** (add after `self._blur_label.move(self.width() - 210, 16)` at line 238):

```python
        self._exposure_label.move(self.width() - 210, 46)
```

**1d. Call `_update_exposure_label()` in `_load_current`** (add after `self._update_blur_label()` at line 322):

```python
        self._update_exposure_label()
```

**1e. Add `_update_exposure_label` method** (after `_update_blur_label`, around line 416):

```python
    def _update_exposure_label(self):
        from app.utils.theme import (
            EXPOSURE_OVEREXPOSED, EXPOSURE_UNDEREXPOSED, EXPOSURE_BLACK,
            EXPOSURE_NORMAL, EXPOSURE_UNKNOWN,
        )
        from app.core.exposure_service import ExposureService

        if not self._ids:
            self._exposure_label.setText("")
            return

        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        if photo is None:
            self._exposure_label.setText("")
            return

        clip = 0.01
        black_mean = 8.0
        black_shadow = 0.90
        if self._settings is not None:
            clip = float(self._settings.get("exposure_clip_threshold", 0.01))
            black_mean = float(self._settings.get("exposure_black_mean_threshold", 8.0))
            black_shadow = float(self._settings.get("exposure_black_shadow_threshold", 0.90))

        display = ExposureService.exposure_display_state(
            photo,
            clip_threshold=clip,
            black_mean_threshold=black_mean,
            black_shadow_threshold=black_shadow,
        )

        state_map = {
            "unanalyzed": ("Exposure: —", EXPOSURE_UNKNOWN),
            "normal":     ("Exposure: OK", EXPOSURE_NORMAL),
            "overexposed": (
                f"Exposure: Over {photo.exposure_overexposed * 100:.1f}%",
                EXPOSURE_OVEREXPOSED,
            ),
            "underexposed": (
                f"Exposure: Under {photo.exposure_underexposed * 100:.1f}%",
                EXPOSURE_UNDEREXPOSED,
            ),
            "black_frame": ("Exposure: Black", EXPOSURE_BLACK),
        }
        text, color = state_map.get(display, ("Exposure: —", EXPOSURE_UNKNOWN))
        self._exposure_label.setText(text)
        self._exposure_label.setStyleSheet(
            f"color:{color}; font-size:13px; background:transparent; padding:4px;"
        )
```

**1f. Update `_on_filter_changed` to pass exposure to FilterService** (replace the existing `_on_filter_changed` method, around line 324):

```python
    def _on_filter_changed(self, statuses: list, colors: list):
        self._statuses = list(statuses)
        self._colors = list(colors)
        self.filter_changed.emit(self._statuses, self._colors)
        if self._filter_svc is None:
            return

        prev_id = self._ids[self._idx] if self._ids else None
        mode, threshold, percent = self._blur_settings()
        clip, black_mean, black_shadow = self._exposure_settings()
        new_photos = self._filter_svc.filter(
            statuses=self._statuses or None,
            colors=self._colors or None,
            blur=self._blur or None,
            exposure=self._exposure or None,
            blur_mode=mode,
            blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
            exposure_clip_threshold=clip,
            exposure_black_mean_threshold=black_mean,
            exposure_black_shadow_threshold=black_shadow,
        )
        new_ids = [p.id for p in new_photos]

        if prev_id is not None and prev_id in new_ids:
            self._idx = new_ids.index(prev_id)
        else:
            self._idx = 0
        self._ids = new_ids
        self._load_current()
```

**1g. Add `_exposure_settings` helper to LoupeView** (after `_blur_settings`, around line 434):

```python
    def _exposure_settings(self):
        if self._settings is None:
            return 0.01, 8.0, 0.90
        clip = float(self._settings.get("exposure_clip_threshold", 0.01))
        black_mean = float(self._settings.get("exposure_black_mean_threshold", 8.0))
        black_shadow = float(self._settings.get("exposure_black_shadow_threshold", 0.90))
        return clip, black_mean, black_shadow
```

- [ ] **Step 2: Run application and verify Loupe exposure label**

```
python main.py
```

1. Open a folder. Click "◉  分析曝光" and wait for it to finish.
2. Double-click a thumbnail to open Loupe.
3. Verify top-right shows both "Blur: X.X" and "Exposure: OK" / "Exposure: Over X.X%" etc.
4. Navigate with arrow keys — label updates per photo.
5. Check that status/color filter changes in Loupe top bar preserve the exposure context (grid doesn't lose exposure filter when returning).

- [ ] **Step 3: Commit**

```
git add app/ui/loupe_view.py
git commit -m "feat: add exposure label to LoupeView; preserve exposure filter context during Loupe navigation"
```

---

## Task 9: Run full test suite and final smoke test

**Files:** no new changes, verification only.

- [ ] **Step 1: Run all tests**

```
pytest tests/ -v
```

Expected: all previously passing tests still pass. New tests pass.

- [ ] **Step 2: Final smoke test**

```
python main.py
```

1. Open a folder with a mix of photos.
2. Import finishes; exposure does NOT auto-start.
3. Click "◉  分析曝光" — button disables, analysis runs in background.
4. After analysis, button re-enables.
5. Check "過曝" in EXPOSURE filter — only overexposed photos show.
6. Check "欠曝" — only underexposed photos show (including black frames if any).
7. Check "純黑" — only black frame photos show.
8. Check "正常" — only well-exposed photos show.
9. Check "未分析" — only unanalyzed photos show (should be empty after full analysis).
10. Double-click a photo → Loupe shows exposure label (color-coded).
11. Change status filter in Loupe top bar → exposure context preserved, photo list still respects exposure filter.
12. Close Loupe → Grid reflects same exposure filter.
13. Click "清除篩選" → exposure checkboxes clear.

- [ ] **Step 3: Commit any fixes found during smoke test**

If smoke test reveals issues, fix them with targeted commits before declaring done.
