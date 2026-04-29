# Blur Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add blur score analysis to SwiftCull — computed automatically after import and on-demand via re-analysis, with configurable threshold modes, blur filter in the filter panel, and score display in Loupe view.

**Architecture:** A new `BlurService` computes Laplacian variance scores via OpenCV; a `BlurWorker` (QThread) runs analysis in the background, emitting per-photo signals. The `FilterService` gains a blur dimension; `FilterPanel` gains a blur section with a settings gear; `LoupeView` overlays the score in the top-right corner.

**Tech Stack:** OpenCV (`cv2`), PySide6 QThread/Signal, SQLite via existing PhotoRepository, JSON settings at `%APPDATA%\SwiftCull\settings.json`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `app/core/blur_service.py` | Compute Laplacian variance; classify as blurry given threshold config |
| Create | `app/core/blur_worker.py` | QThread worker + controller; emits `photo_blur_updated(int, float)` per photo |
| Create | `app/ui/blur_settings_dialog.py` | Modal dialog to choose threshold mode and value |
| Modify | `app/core/models.py` | Add `blur_score: Optional[float]` to `Photo` |
| Modify | `app/db/connection.py` | Migration: add `blur_score REAL` column to `photos` |
| Modify | `app/db/photo_repository.py` | `update_blur_score()`, `get_all()` maps new column |
| Modify | `app/core/filter_service.py` | Accept `blur` filter param (`"blurry"` / `"sharp"` / `"unanalyzed"`) |
| Modify | `app/core/import_worker.py` | After enrich loop finishes, emit `blur_analysis_requested` signal |
| Modify | `app/utils/theme.py` | Add `BLUR_BLURRY`, `BLUR_SHARP`, `BLUR_UNKNOWN` color constants |
| Modify | `app/ui/filter_panel.py` | Add BLUR section with three checkboxes and gear button |
| Modify | `app/ui/loupe_view.py` | Add `_blur_label` overlay top-right; call `_update_blur_label()` |
| Modify | `app/ui/grid_view.py` | Wire `BlurController`; connect `photo_blur_updated`; expose `start_blur_analysis()` |
| Modify | `app/ui/main_window.py` | Pass `blur_repo` (photo_repo) to GridView; connect import-finished → blur start |

---

## Task 1: Photo model + DB migration

**Files:**
- Modify: `app/core/models.py`
- Modify: `app/db/connection.py`
- Modify: `app/db/photo_repository.py`
- Test: `tests/db/test_photo_repository.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/db/test_photo_repository.py  (add to existing file)

def test_update_blur_score(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.core.models import Photo
    repo = PhotoRepository(db_conn)
    photo = Photo(id=None, relative_path="a.jpg", filename="a.jpg", file_size=100)
    pid = repo.insert(photo)
    repo.update_blur_score(pid, 42.5)
    p = repo.get_by_id(pid)
    assert abs(p.blur_score - 42.5) < 0.001

def test_blur_score_defaults_none(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.core.models import Photo
    repo = PhotoRepository(db_conn)
    photo = Photo(id=None, relative_path="b.jpg", filename="b.jpg", file_size=100)
    pid = repo.insert(photo)
    p = repo.get_by_id(pid)
    assert p.blur_score is None
```

- [ ] **Step 2: Run tests — confirm FAIL**

```
pytest tests/db/test_photo_repository.py::test_update_blur_score tests/db/test_photo_repository.py::test_blur_score_defaults_none -v
```
Expected: `AttributeError` or `OperationalError` (column missing)

- [ ] **Step 3: Add `blur_score` to Photo model**

In `app/core/models.py`, add after `focal_length`:
```python
    blur_score: Optional[float] = None
```

- [ ] **Step 4: Add DB column via migration in `init_db`**

In `app/db/connection.py`, after the `conn.executescript(...)` block and before `conn.commit()`, add:
```python
    # Migration: add blur_score if absent (safe on existing DBs)
    try:
        conn.execute("ALTER TABLE photos ADD COLUMN blur_score REAL")
    except Exception:
        pass  # column already exists
```

- [ ] **Step 5: Add `update_blur_score` and fix `_row_to_photo`**

In `app/db/photo_repository.py`, add method after `update_metadata`:
```python
    def update_blur_score(self, photo_id: int, score: float) -> None:
        self._conn.execute(
            "UPDATE photos SET blur_score=? WHERE id=?", (score, photo_id)
        )
        self._conn.commit()
```

In `_row_to_photo`, add after `focal_length=row["focal_length"],`:
```python
            blur_score=row["blur_score"] if "blur_score" in row.keys() else None,
```

- [ ] **Step 6: Run tests — confirm PASS**

```
pytest tests/db/test_photo_repository.py -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add app/core/models.py app/db/connection.py app/db/photo_repository.py tests/db/test_photo_repository.py
git commit -m "feat: add blur_score column to photos and model"
```

---

## Task 2: BlurService — score computation and classification

**Files:**
- Create: `app/core/blur_service.py`
- Test: `tests/core/test_blur_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_blur_service.py
import numpy as np
import cv2
from PIL import Image
import io

def _make_sharp_jpeg(tmp_path):
    """Checkerboard pattern — high frequency = high Laplacian variance."""
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    for i in range(200):
        for j in range(200):
            arr[i, j] = 255 if (i // 10 + j // 10) % 2 == 0 else 0
    path = tmp_path / "sharp.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)

def _make_blurry_jpeg(tmp_path):
    """Solid color — zero variance = maximum blur."""
    arr = np.full((200, 200, 3), 128, dtype=np.uint8)
    path = tmp_path / "blurry.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)

def test_compute_score_sharp_higher_than_blurry(tmp_path):
    from app.core.blur_service import BlurService
    svc = BlurService()
    sharp_score = svc.compute_score(str(tmp_path / "sharp.jpg").replace("sharp.jpg", ""),
                                     "sharp.jpg")
    # write files first
    _make_sharp_jpeg(tmp_path)
    _make_blurry_jpeg(tmp_path)
    svc2 = BlurService()
    sharp = svc2.compute_score(str(tmp_path), "sharp.jpg")
    blurry = svc2.compute_score(str(tmp_path), "blurry.jpg")
    assert sharp > blurry

def test_compute_score_returns_float(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    svc = BlurService()
    score = svc.compute_score(str(tmp_path), "sharp.jpg")
    assert isinstance(score, float)
    assert score >= 0.0

def test_is_blurry_fixed_mode(tmp_path):
    from app.core.blur_service import BlurService
    _make_blurry_jpeg(tmp_path)
    svc = BlurService()
    score = svc.compute_score(str(tmp_path), "blurry.jpg")
    # solid color has score ~0, threshold 100 → blurry
    assert svc.is_blurry_fixed(score, threshold=100.0) is True

def test_is_blurry_fixed_mode_sharp(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    svc = BlurService()
    score = svc.compute_score(str(tmp_path), "sharp.jpg")
    # checkerboard has high variance → not blurry
    assert svc.is_blurry_fixed(score, threshold=10.0) is False

def test_classify_relative(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    _make_blurry_jpeg(tmp_path)
    svc = BlurService()
    scores = [svc.compute_score(str(tmp_path), "blurry.jpg"),
              svc.compute_score(str(tmp_path), "sharp.jpg")]
    # bottom 50% relative → blurry.jpg is blurry
    threshold = svc.relative_threshold(scores, bottom_percent=50)
    assert svc.is_blurry_fixed(scores[0], threshold) is True
    assert svc.is_blurry_fixed(scores[1], threshold) is False
```

- [ ] **Step 2: Run tests — confirm FAIL**

```
pytest tests/core/test_blur_service.py -v
```
Expected: `ModuleNotFoundError: app.core.blur_service`

- [ ] **Step 3: Implement BlurService**

Create `app/core/blur_service.py`:
```python
import os
from typing import List

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


class BlurService:
    def compute_score(self, root_path: str, relative_path: str) -> float:
        """Return Laplacian variance of image. Higher = sharper. Returns 0.0 on failure."""
        if not _CV2_AVAILABLE:
            return 0.0
        abs_path = os.path.join(root_path, relative_path)
        try:
            img = cv2.imread(abs_path)
            if img is None:
                return 0.0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return 0.0

    def is_blurry_fixed(self, score: float, threshold: float) -> bool:
        """True if score is below threshold (fixed mode)."""
        return score < threshold

    def relative_threshold(self, scores: List[float], bottom_percent: float) -> float:
        """Return the score value at the bottom_percent percentile."""
        if not scores:
            return 0.0
        sorted_scores = sorted(scores)
        idx = max(0, int(len(sorted_scores) * bottom_percent / 100) - 1)
        return sorted_scores[idx]
```

- [ ] **Step 4: Run tests — confirm PASS**

```
pytest tests/core/test_blur_service.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/core/blur_service.py tests/core/test_blur_service.py
git commit -m "feat: add BlurService with Laplacian variance scoring"
```

---

## Task 3: BlurWorker — background analysis QThread

**Files:**
- Create: `app/core/blur_worker.py`

*(No unit test — QThread workers are integration-tested via UI; logic is in BlurService)*

- [ ] **Step 1: Create `app/core/blur_worker.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/core/blur_worker.py
git commit -m "feat: add BlurWorker/BlurController for background blur analysis"
```

---

## Task 4: FilterService blur support

**Files:**
- Modify: `app/core/filter_service.py`
- Test: `tests/core/test_filter_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_filter_service.py  (add to existing file)

def _insert_photo_with_blur(repo, path, blur_score):
    from app.core.models import Photo
    photo = Photo(id=None, relative_path=path, filename=path, file_size=100)
    pid = repo.insert(photo)
    if blur_score is not None:
        repo.update_blur_score(pid, blur_score)
    return pid

def test_filter_blur_blurry(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    from app.core.blur_service import BlurService
    photo_repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(photo_repo, tag_repo)
    blur_svc = BlurService()

    pid_blurry = _insert_photo_with_blur(photo_repo, "blurry.jpg", 5.0)
    pid_sharp = _insert_photo_with_blur(photo_repo, "sharp.jpg", 500.0)

    results = svc.filter(blur=["blurry"], blur_threshold=100.0)
    ids = [p.id for p in results]
    assert pid_blurry in ids
    assert pid_sharp not in ids

def test_filter_blur_unanalyzed(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    photo_repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(photo_repo, tag_repo)

    pid_none = _insert_photo_with_blur(photo_repo, "none.jpg", None)
    pid_scored = _insert_photo_with_blur(photo_repo, "scored.jpg", 200.0)

    results = svc.filter(blur=["unanalyzed"])
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_scored not in ids
```

- [ ] **Step 2: Run tests — confirm FAIL**

```
pytest tests/core/test_filter_service.py -v
```
Expected: `TypeError` (unexpected keyword `blur`)

- [ ] **Step 3: Update FilterService**

Replace `app/core/filter_service.py` entirely:
```python
from typing import List, Optional
from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.models import Photo


class FilterService:
    def __init__(self, photo_repo: PhotoRepository, tag_repo: TagRepository):
        self._photos = photo_repo
        self._tags = tag_repo

    def filter(
        self,
        statuses: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        blur: Optional[List[str]] = None,
        blur_threshold: float = 100.0,
    ) -> List[Photo]:
        all_photos = self._photos.get_all()
        if not statuses and not colors and not blur:
            return all_photos
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
                if "unanalyzed" in blur and score is not None:
                    continue
                if "blurry" in blur and (score is None or score >= blur_threshold):
                    continue
                if "sharp" in blur and (score is None or score < blur_threshold):
                    continue

            result.append(photo)
        return result
```

- [ ] **Step 4: Run tests — confirm PASS**

```
pytest tests/core/test_filter_service.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/core/filter_service.py tests/core/test_filter_service.py
git commit -m "feat: add blur filter dimension to FilterService"
```

---

## Task 5: Theme constants for blur

**Files:**
- Modify: `app/utils/theme.py`

- [ ] **Step 1: Add blur color constants to `app/utils/theme.py`**

After the `MAYBE_CLR` line, add:
```python
BLUR_BLURRY  = "#FF6B6B"   # red-ish — indicates blur warning
BLUR_SHARP   = "#3ddc84"   # green — same as PICK_CLR
BLUR_UNKNOWN = "#555555"   # muted — unanalyzed
```

- [ ] **Step 2: Commit**

```bash
git add app/utils/theme.py
git commit -m "feat: add blur color constants to theme"
```

---

## Task 6: BlurSettingsDialog

**Files:**
- Create: `app/ui/blur_settings_dialog.py`

- [ ] **Step 1: Create `app/ui/blur_settings_dialog.py`**

```python
import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal

_SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "SwiftCull", "settings.json"
)


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    try:
        existing = _load_settings()
        existing.update(data)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass


class BlurSettingsDialog(QDialog):
    settings_changed = Signal(str, float)   # mode, threshold_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模糊偵測設定")
        self.setFixedSize(320, 200)
        self.setStyleSheet("background:#1e1e1e; color:#e8e8e8;")

        settings = _load_settings()
        self._mode = settings.get("blur_mode", "fixed")
        self._fixed_threshold = float(settings.get("blur_fixed_threshold", 100.0))
        self._relative_percent = int(settings.get("blur_relative_percent", 20))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["fixed (固定閾值)", "relative (相對底部%)"])
        self._mode_combo.setCurrentIndex(0 if self._mode == "fixed" else 1)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        layout.addLayout(mode_row)

        # Fixed threshold row
        self._fixed_row = QHBoxLayout()
        self._fixed_row.addWidget(QLabel("閾值 (Laplacian):"))
        self._fixed_spin = QSpinBox()
        self._fixed_spin.setRange(1, 10000)
        self._fixed_spin.setValue(int(self._fixed_threshold))
        self._fixed_row.addWidget(self._fixed_spin)
        layout.addLayout(self._fixed_row)

        # Relative percent row
        self._rel_row = QHBoxLayout()
        self._rel_row.addWidget(QLabel("底部 %:"))
        self._rel_spin = QSpinBox()
        self._rel_spin.setRange(1, 99)
        self._rel_spin.setValue(self._relative_percent)
        self._rel_row.addWidget(self._rel_spin)
        layout.addLayout(self._rel_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("確定")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._on_mode_changed(self._mode_combo.currentIndex())

    def _on_mode_changed(self, idx: int):
        is_fixed = idx == 0
        for i in range(self._fixed_row.count()):
            w = self._fixed_row.itemAt(i).widget()
            if w:
                w.setVisible(is_fixed)
        for i in range(self._rel_row.count()):
            w = self._rel_row.itemAt(i).widget()
            if w:
                w.setVisible(not is_fixed)

    def _on_ok(self):
        mode = "fixed" if self._mode_combo.currentIndex() == 0 else "relative"
        fixed_val = float(self._fixed_spin.value())
        rel_val = self._rel_spin.value()
        _save_settings({
            "blur_mode": mode,
            "blur_fixed_threshold": fixed_val,
            "blur_relative_percent": rel_val,
        })
        threshold = fixed_val if mode == "fixed" else float(rel_val)
        self.settings_changed.emit(mode, threshold)
        self.accept()
```

- [ ] **Step 2: Commit**

```bash
git add app/ui/blur_settings_dialog.py
git commit -m "feat: add BlurSettingsDialog for threshold mode configuration"
```

---

## Task 7: FilterPanel blur section

**Files:**
- Modify: `app/ui/filter_panel.py`

- [ ] **Step 1: Update imports in `filter_panel.py`**

Add to the existing import from `app.utils.theme`:
```python
from app.utils.theme import (
    BG_PANEL, BG_HOVER, BORDER, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    STATUS_ICON, STATUS_COLOR, COLOR_DOT,
    PICK_CLR, REJECT_CLR, MAYBE_CLR,
    BLUR_BLURRY, BLUR_SHARP, BLUR_UNKNOWN,
)
```

- [ ] **Step 2: Change `filter_changed` signal signature**

Replace:
```python
    filter_changed = Signal(list, list)
```
With:
```python
    filter_changed = Signal(list, list, list)   # statuses, colors, blur
```

- [ ] **Step 3: Add `_blur_checks` dict to `__init__`**

After `self._color_checks: dict[str, _ColorDotCheckBox] = {}`, add:
```python
        self._blur_checks: dict[str, QCheckBox] = {}
```

- [ ] **Step 4: Add blur section to panel content**

After the `clear_btn` and before `cl.addStretch()`, insert:
```python
        cl.addSpacing(8)

        sec3 = QLabel("BLUR")
        sec3.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec3)

        blur_header = QHBoxLayout()
        blur_header.setContentsMargins(0, 0, 0, 0)
        blur_header.setSpacing(4)
        blur_header.addStretch()
        gear_btn = QPushButton("⚙")
        gear_btn.setFixedSize(18, 18)
        gear_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_MUTED}; border:none; font-size:11px; padding:0;"
        )
        gear_btn.setCursor(Qt.PointingHandCursor)
        gear_btn.setToolTip("模糊偵測設定")
        gear_btn.clicked.connect(self._open_blur_settings)
        blur_header.addWidget(gear_btn)
        cl.addLayout(blur_header)

        for blur_key, label in [("blurry", "模糊"), ("sharp", "清晰"), ("unanalyzed", "未分析")]:
            from PySide6.QtWidgets import QCheckBox as _QCB
            cb = _QCB(label)
            cb.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px;")
            cb.stateChanged.connect(self._emit_filter)
            self._blur_checks[blur_key] = cb
            cl.addWidget(cb)
```

- [ ] **Step 5: Add `_open_blur_settings` method**

Add after `_clear_all`:
```python
    def _open_blur_settings(self):
        from app.ui.blur_settings_dialog import BlurSettingsDialog
        dlg = BlurSettingsDialog(self)
        dlg.exec()
```

- [ ] **Step 6: Update `_emit_filter` to include blur**

Replace:
```python
    def _emit_filter(self):
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors)
```
With:
```python
    def _emit_filter(self):
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        blur = [k for k, cb in self._blur_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors, blur)
```

- [ ] **Step 7: Update `_clear_all` to include blur checks**

Replace:
```python
    def _clear_all(self):
        for cb in list(self._status_checks.values()) + list(self._color_checks.values()):
            cb.setChecked(False)
```
With:
```python
    def _clear_all(self):
        for cb in (list(self._status_checks.values())
                   + list(self._color_checks.values())
                   + list(self._blur_checks.values())):
            cb.setChecked(False)
```

- [ ] **Step 8: Commit**

```bash
git add app/ui/filter_panel.py
git commit -m "feat: add blur filter section to FilterPanel"
```

---

## Task 8: LoupeView blur score overlay

**Files:**
- Modify: `app/ui/loupe_view.py`

- [ ] **Step 1: Add `_blur_label` overlay in `__init__`**

After the `self._status_label.raise_()` block, add:
```python
        # --- blur score overlay (top-right) ---
        self._blur_label = QLabel("")
        self._blur_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._blur_label.setStyleSheet(
            "color: #aaa; font-size: 13px; background: transparent; padding: 4px;"
        )
        self._blur_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._blur_label.setParent(self)
        self._blur_label.resize(200, 30)
        self._blur_label.raise_()
```

- [ ] **Step 2: Position `_blur_label` in `resizeEvent`**

In `resizeEvent`, after `super().resizeEvent(event)`, add:
```python
        self._blur_label.move(self.width() - 210, 16)
```

- [ ] **Step 3: Update `_load_current` to call `_update_blur_label`**

At the end of `_load_current`, add:
```python
        self._update_blur_label()
```

- [ ] **Step 4: Add `_update_blur_label` method**

Add after `_update_status_label`:
```python
    def _update_blur_label(self):
        from app.utils.theme import BLUR_BLURRY, BLUR_SHARP, BLUR_UNKNOWN
        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        score = photo.blur_score if photo else None
        if score is None:
            self._blur_label.setText("Blur: —")
            self._blur_label.setStyleSheet(
                f"color:{BLUR_UNKNOWN}; font-size:13px; background:transparent; padding:4px;"
            )
        else:
            # use fixed threshold 100 as display heuristic (user can change in settings)
            import json, os
            settings_path = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")),
                "SwiftCull", "settings.json"
            )
            threshold = 100.0
            try:
                with open(settings_path, encoding="utf-8") as f:
                    s = json.load(f)
                    threshold = float(s.get("blur_fixed_threshold", 100.0))
            except Exception:
                pass
            color = BLUR_BLURRY if score < threshold else BLUR_SHARP
            self._blur_label.setText(f"Blur: {score:.1f}")
            self._blur_label.setStyleSheet(
                f"color:{color}; font-size:13px; background:transparent; padding:4px;"
            )
```

- [ ] **Step 5: Commit**

```bash
git add app/ui/loupe_view.py
git commit -m "feat: add blur score overlay to LoupeView"
```

---

## Task 9: GridView + ImportWorker wiring

**Files:**
- Modify: `app/ui/grid_view.py`
- Modify: `app/core/import_worker.py`

- [ ] **Step 1: Update `filter_changed` connection in GridView**

In `app/ui/grid_view.py`, find:
```python
        self._filter_panel.filter_changed.connect(self._on_filter_changed)
```
Keep it as-is — `_on_filter_changed` signature will be updated next.

- [ ] **Step 2: Update `_on_filter_changed` in GridView**

Replace:
```python
    def _on_filter_changed(self, statuses, colors):
        self._refresh(statuses or None, colors or None)
```
With:
```python
    def _on_filter_changed(self, statuses, colors, blur):
        self._current_blur = blur or None
        self._refresh(statuses or None, colors or None, blur or None)
```

Also add `self._current_blur = None` in `__init__` after `self._current_colors = None`.

- [ ] **Step 3: Update `_refresh` in GridView**

Replace:
```python
    def _refresh(self, statuses=None, colors=None):
        self._current_statuses = statuses
        self._current_colors = colors
        photos = self._filter_svc.filter(statuses=statuses, colors=colors)
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)
```
With:
```python
    def _refresh(self, statuses=None, colors=None, blur=None):
        self._current_statuses = statuses
        self._current_colors = colors
        self._current_blur = blur
        photos = self._filter_svc.filter(statuses=statuses, colors=colors, blur=blur)
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)
```

- [ ] **Step 4: Update `_on_loupe` in GridView to pass blur**

In `_on_loupe`, replace:
```python
        photos = self._filter_svc.filter(
            statuses=self._current_statuses,
            colors=self._current_colors,
        )
```
With:
```python
        photos = self._filter_svc.filter(
            statuses=self._current_statuses,
            colors=self._current_colors,
            blur=self._current_blur,
        )
```

- [ ] **Step 5: Add `start_blur_analysis` to GridView**

Add method to `GridView`:
```python
    def start_blur_analysis(self, db_path: str):
        from app.core.blur_worker import BlurController
        from app.db.photo_repository import PhotoRepository
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = __import__("sqlite3").Row
        repo = PhotoRepository(conn)
        all_photos = repo.get_all()
        conn.close()
        photo_ids = [p.id for p in all_photos]
        if not photo_ids:
            return
        self._blur_ctrl = BlurController(self._folder, db_path, photo_ids)
        self._blur_ctrl.photo_blur_updated.connect(self._on_photo_blur_updated)
        self._blur_ctrl.start()

    def _on_photo_blur_updated(self, photo_id: int, score: float):
        self._grid.update_item_tag(photo_id)
```

- [ ] **Step 6: Commit**

```bash
git add app/ui/grid_view.py
git commit -m "feat: wire BlurController into GridView, add start_blur_analysis"
```

---

## Task 10: MainWindow wiring

**Files:**
- Modify: `app/ui/main_window.py`

- [ ] **Step 1: Trigger blur analysis in `_on_import_finished`**

`main_window.py` already has `_on_import_finished`. Replace it with:
```python
    def _on_import_finished(self):
        if self._grid_view is not None:
            self._grid_view.end_import()
            self._grid_view.start_blur_analysis(self._db_path)
        self._import_ctrl = None
```

This triggers blur analysis on all photos every time import finishes (both first import and re-scan). `start_blur_analysis` skips photos that would be a no-op in future iterations; for Phase 2 this is acceptable.

- [ ] **Step 2: Commit**

```bash
git add app/ui/main_window.py
git commit -m "feat: auto-trigger blur analysis after import completes in MainWindow"
```

---

## Task 11: Run full test suite

- [ ] **Step 1: Run all tests**

```
pytest -v
```
Expected: all existing tests pass, new tests pass.

- [ ] **Step 2: Manually smoke-test the app**

```
python main.py
```

Verify:
1. Open a folder with photos → import runs → blur analysis auto-starts (no crash)
2. Filter panel shows BLUR section with 模糊/清晰/未分析 checkboxes and ⚙ button
3. ⚙ opens BlurSettingsDialog, can change mode/threshold, saves settings
4. Checking "模糊" in filter shows only low-score photos
5. Open a photo in Loupe → `Blur: 123.4` appears top-right in green/red
6. Top bar "↻ 重新掃描" triggers re-import which re-triggers blur analysis

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: phase 2 blur detection complete"
```
