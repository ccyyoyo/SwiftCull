# Blur Detection Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete blur detection wiring (Tasks 9–11) and fix 6 known bugs: settings persistence, relative mode, RAW misclassification, OR filter logic, missing manual re-analyse UI, and test coverage gaps.

**Architecture:** `BlurService.compute_score()` returns `Optional[float]` (None on failure). `FilterService` gains `blur_mode`/`blur_relative_percent` params and uses OR logic. `GridView` wires `BlurController` and a new toolbar button. `BlurSettingsDialog` reads/writes `SettingsDB` instead of `settings.json`. `LoupeView` resolves threshold dynamically from `SettingsDB`.

**Tech Stack:** OpenCV, PySide6 QThread/Signal, SQLite via PhotoRepository, SettingsDB (existing)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `app/core/blur_service.py` | `compute_score` returns `Optional[float]`; None on unreadable |
| Modify | `app/core/blur_worker.py` | Skip `update_blur_score` when score is None |
| Modify | `app/core/filter_service.py` | OR logic; `blur_mode` + `blur_relative_percent` params |
| Modify | `app/db/photo_repository.py` | Add `get_unanalyzed_ids()` |
| Modify | `app/ui/blur_settings_dialog.py` | Accept `SettingsDB` injection; drop JSON file I/O |
| Modify | `app/ui/grid_view.py` | Wire blur filter + BlurController + toolbar button + SettingsDB param |
| Modify | `app/ui/loupe_view.py` | `_update_blur_label` reads SettingsDB; supports relative mode |
| Modify | `app/ui/filter_panel.py` | Accept `settings` param; pass to BlurSettingsDialog |
| Modify | `app/ui/main_window.py` | Pass SettingsDB to GridView + BlurSettingsDialog; trigger blur after import |
| Modify | `tests/core/test_blur_service.py` | Add None-return test |
| Modify | `tests/core/test_filter_service.py` | OR logic + relative mode tests |
| Modify | `tests/db/test_photo_repository.py` | `get_unanalyzed_ids` tests |

---

## Task 1: BlurService returns Optional[float]

**Files:**
- Modify: `app/core/blur_service.py`
- Modify: `app/core/blur_worker.py`
- Modify: `tests/core/test_blur_service.py`

- [ ] **Step 1: Write failing test**

Add to `tests/core/test_blur_service.py`:
```python
def test_compute_score_returns_none_for_missing_file(tmp_path):
    from app.core.blur_service import BlurService
    svc = BlurService()
    result = svc.compute_score(str(tmp_path), "nonexistent.jpg")
    assert result is None

def test_compute_score_returns_none_for_unreadable_raw(tmp_path):
    from app.core.blur_service import BlurService
    # Write a file that is not a valid image
    p = tmp_path / "shot.CR2"
    p.write_bytes(b"not a real raw file")
    svc = BlurService()
    result = svc.compute_score(str(tmp_path), "shot.CR2")
    assert result is None
```

- [ ] **Step 2: Run tests — confirm FAIL**

```
pytest tests/core/test_blur_service.py::test_compute_score_returns_none_for_missing_file tests/core/test_blur_service.py::test_compute_score_returns_none_for_unreadable_raw -v
```
Expected: FAIL — both return `0.0`, not `None`

- [ ] **Step 3: Update BlurService.compute_score return type**

Replace `app/core/blur_service.py` entirely:
```python
import os
from typing import List, Optional

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


class BlurService:
    def compute_score(self, root_path: str, relative_path: str) -> Optional[float]:
        """Return Laplacian variance of image. Higher = sharper. Returns None on failure."""
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            img = cv2.imread(abs_path)
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return None

    def is_blurry_fixed(self, score: float, threshold: float) -> bool:
        """True if score is below threshold (fixed mode)."""
        return score < threshold

    def relative_threshold(self, scores: List[float], bottom_percent: float) -> float:
        """Return threshold so photos at/below the bottom_percent percentile are blurry."""
        if not scores:
            return 0.0
        sorted_scores = sorted(scores)
        idx = max(0, int(len(sorted_scores) * bottom_percent / 100.0) - 1)
        return sorted_scores[idx] + 1e-9
```

- [ ] **Step 4: Update BlurWorker to skip None scores**

Replace `_run_inner` in `app/core/blur_worker.py`:
```python
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
                    if score is not None:
                        repo.update_blur_score(photo_id, score)
                        self.photo_blur_updated.emit(photo_id, score)
                except Exception:
                    pass
                self.progress.emit(i + 1, total)
        finally:
            conn.close()
```

- [ ] **Step 5: Run tests — confirm PASS**

```
pytest tests/core/test_blur_service.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/core/blur_service.py app/core/blur_worker.py tests/core/test_blur_service.py
git commit -m "fix: BlurService returns None on unreadable files; BlurWorker skips None scores"
```

---

## Task 2: PhotoRepository.get_unanalyzed_ids()

**Files:**
- Modify: `app/db/photo_repository.py`
- Modify: `tests/db/test_photo_repository.py`

- [ ] **Step 1: Write failing test**

Add to `tests/db/test_photo_repository.py`:
```python
def test_get_unanalyzed_ids_returns_only_null_blur(db_conn):
    repo = PhotoRepository(db_conn)
    pid1 = repo.insert(Photo(id=None, relative_path="a.jpg", filename="a.jpg", file_size=1))
    pid2 = repo.insert(Photo(id=None, relative_path="b.jpg", filename="b.jpg", file_size=1))
    pid3 = repo.insert(Photo(id=None, relative_path="c.jpg", filename="c.jpg", file_size=1))
    repo.update_blur_score(pid2, 50.0)
    result = repo.get_unanalyzed_ids()
    assert pid1 in result
    assert pid3 in result
    assert pid2 not in result

def test_get_unanalyzed_ids_empty_when_all_analyzed(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="x.jpg", filename="x.jpg", file_size=1))
    repo.update_blur_score(pid, 99.0)
    assert repo.get_unanalyzed_ids() == []
```

- [ ] **Step 2: Run tests — confirm FAIL**

```
pytest tests/db/test_photo_repository.py::test_get_unanalyzed_ids_returns_only_null_blur tests/db/test_photo_repository.py::test_get_unanalyzed_ids_empty_when_all_analyzed -v
```
Expected: `AttributeError: 'PhotoRepository' object has no attribute 'get_unanalyzed_ids'`

- [ ] **Step 3: Add method to PhotoRepository**

In `app/db/photo_repository.py`, add after `get_path_mtime_map`:
```python
    def get_unanalyzed_ids(self) -> list[int]:
        """Return IDs of photos where blur_score IS NULL."""
        rows = self._conn.execute(
            "SELECT id FROM photos WHERE blur_score IS NULL"
        ).fetchall()
        return [int(r["id"]) for r in rows]
```

- [ ] **Step 4: Run tests — confirm PASS**

```
pytest tests/db/test_photo_repository.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/db/photo_repository.py tests/db/test_photo_repository.py
git commit -m "feat: add PhotoRepository.get_unanalyzed_ids()"
```

---

## Task 3: FilterService — OR logic + relative mode

**Files:**
- Modify: `app/core/filter_service.py`
- Modify: `tests/core/test_filter_service.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/core/test_filter_service.py`:
```python
def _insert_with_blur(repo, path, blur_score):
    from app.core.models import Photo
    pid = repo.insert(Photo(id=None, relative_path=path, filename=path, file_size=1))
    if blur_score is not None:
        repo.update_blur_score(pid, blur_score)
    return pid

def test_blur_filter_or_logic_blurry_and_sharp(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)
    pid_blurry = _insert_with_blur(repo, "b.jpg", 10.0)
    pid_sharp  = _insert_with_blur(repo, "s.jpg", 500.0)
    # Selecting both blurry+sharp should return both (OR), not empty (AND-exclusion)
    results = svc.filter(blur=["blurry", "sharp"], blur_fixed_threshold=100.0)
    ids = [p.id for p in results]
    assert pid_blurry in ids
    assert pid_sharp in ids

def test_blur_filter_or_logic_unanalyzed_and_sharp(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)
    pid_none  = _insert_with_blur(repo, "n.jpg", None)
    pid_sharp = _insert_with_blur(repo, "s.jpg", 500.0)
    results = svc.filter(blur=["unanalyzed", "sharp"], blur_fixed_threshold=100.0)
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_sharp in ids

def test_blur_filter_relative_mode(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)
    pid_low  = _insert_with_blur(repo, "low.jpg", 5.0)
    pid_mid  = _insert_with_blur(repo, "mid.jpg", 50.0)
    pid_high = _insert_with_blur(repo, "hi.jpg", 500.0)
    # bottom 40% of [5.0, 50.0, 500.0] → idx=0 → threshold=5.0+eps → only 5.0 is blurry
    results = svc.filter(
        blur=["blurry"],
        blur_mode="relative",
        blur_relative_percent=40.0,
    )
    ids = [p.id for p in results]
    assert pid_low in ids
    assert pid_mid not in ids
    assert pid_high not in ids
```

- [ ] **Step 2: Run tests — confirm FAIL**

```
pytest tests/core/test_filter_service.py::test_blur_filter_or_logic_blurry_and_sharp tests/core/test_filter_service.py::test_blur_filter_or_logic_unanalyzed_and_sharp tests/core/test_filter_service.py::test_blur_filter_relative_mode -v
```
Expected: first two fail (returns empty), third fails (TypeError — unexpected kwarg)

- [ ] **Step 3: Replace FilterService**

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
        blur_mode: str = "fixed",
        blur_fixed_threshold: float = 100.0,
        blur_relative_percent: float = 20.0,
    ) -> List[Photo]:
        all_photos = self._photos.get_all()
        if not statuses and not colors and not blur:
            return all_photos

        # Compute effective threshold for blur filtering
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
git commit -m "fix: FilterService blur uses OR logic and supports relative mode"
```

---

## Task 4: BlurSettingsDialog uses SettingsDB

**Files:**
- Modify: `app/ui/blur_settings_dialog.py`

*(No unit test — dialog is UI; tested via smoke test. SettingsDB persistence covered by existing SettingsDB tests.)*

- [ ] **Step 1: Replace BlurSettingsDialog**

Replace `app/ui/blur_settings_dialog.py` entirely:
```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal

from app.db.settings_db import SettingsDB


class BlurSettingsDialog(QDialog):
    settings_changed = Signal(str, float)  # mode, effective_threshold

    def __init__(self, settings: SettingsDB, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("模糊偵測設定")
        self.setFixedSize(320, 200)
        self.setStyleSheet("background:#1e1e1e; color:#e8e8e8;")

        mode = self._settings.get("blur_mode", "fixed")
        fixed_threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        rel_percent = int(self._settings.get("blur_relative_percent", 20))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["fixed (固定閾值)", "relative (相對底部%)"])
        self._mode_combo.setCurrentIndex(0 if mode == "fixed" else 1)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        layout.addLayout(mode_row)

        self._fixed_row = QHBoxLayout()
        self._fixed_row.addWidget(QLabel("閾值 (Laplacian):"))
        self._fixed_spin = QSpinBox()
        self._fixed_spin.setRange(1, 10000)
        self._fixed_spin.setValue(int(fixed_threshold))
        self._fixed_row.addWidget(self._fixed_spin)
        layout.addLayout(self._fixed_row)

        self._rel_row = QHBoxLayout()
        self._rel_row.addWidget(QLabel("底部 %:"))
        self._rel_spin = QSpinBox()
        self._rel_spin.setRange(1, 99)
        self._rel_spin.setValue(rel_percent)
        self._rel_row.addWidget(self._rel_spin)
        layout.addLayout(self._rel_row)

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
        self._settings.set("blur_mode", mode)
        self._settings.set("blur_fixed_threshold", fixed_val)
        self._settings.set("blur_relative_percent", rel_val)
        threshold = fixed_val if mode == "fixed" else float(rel_val)
        self.settings_changed.emit(mode, threshold)
        self.accept()
```

- [ ] **Step 2: Commit**

```bash
git add app/ui/blur_settings_dialog.py
git commit -m "fix: BlurSettingsDialog reads/writes SettingsDB instead of settings.json"
```

---

## Task 5: LoupeView — SettingsDB + relative mode

**Files:**
- Modify: `app/ui/loupe_view.py`

- [ ] **Step 1: Add `settings` parameter to LoupeView.__init__**

In `app/ui/loupe_view.py`, update `__init__` signature (line ~107):
```python
    def __init__(self, photo_ids, current_index, folder_path,
                 photo_repo, tag_repo, tag_svc,
                 filter_svc=None,
                 initial_statuses: Optional[list[str]] = None,
                 initial_colors: Optional[list[str]] = None,
                 settings=None,
                 parent=None):
```

Add after `self._filter_svc = filter_svc`:
```python
        self._settings = settings  # SettingsDB instance, may be None
```

- [ ] **Step 2: Replace _update_blur_label**

Replace the entire `_update_blur_label` method:
```python
    def _update_blur_label(self):
        from app.utils.theme import BLUR_BLURRY, BLUR_SHARP, BLUR_UNKNOWN
        if not self._ids:
            return
        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        score = photo.blur_score if photo else None
        if score is None:
            self._blur_label.setText("Blur: —")
            self._blur_label.setStyleSheet(
                f"color:{BLUR_UNKNOWN}; font-size:13px; background:transparent; padding:4px;"
            )
            return

        threshold = self._resolve_blur_threshold()
        color = BLUR_BLURRY if score < threshold else BLUR_SHARP
        self._blur_label.setText(f"Blur: {score:.1f}")
        self._blur_label.setStyleSheet(
            f"color:{color}; font-size:13px; background:transparent; padding:4px;"
        )

    def _resolve_blur_threshold(self) -> float:
        """Read blur threshold from SettingsDB, handling relative mode."""
        if self._settings is None:
            return 100.0
        mode = self._settings.get("blur_mode", "fixed")
        fixed = float(self._settings.get("blur_fixed_threshold", 100.0))
        if mode != "relative":
            return fixed
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        all_photos = self._photo_repo.get_all()
        scores = [p.blur_score for p in all_photos if p.blur_score is not None]
        if not scores:
            return fixed
        from app.core.blur_service import BlurService
        return BlurService().relative_threshold(scores, percent)
```

- [ ] **Step 3: Commit**

```bash
git add app/ui/loupe_view.py
git commit -m "fix: LoupeView blur label reads SettingsDB and supports relative mode"
```

---

## Task 6: GridView — blur wiring + toolbar button

**Files:**
- Modify: `app/ui/grid_view.py`

- [ ] **Step 1: Add `settings` parameter to GridView.__init__**

Update `GridView.__init__` signature:
```python
    def __init__(self, folder_path, photo_repo, tag_repo,
                 thumb_svc, tag_svc, filter_svc, settings, parent=None):
```

Add after `self._filter_svc = filter_svc`:
```python
        self._settings = settings  # SettingsDB instance
        self._current_blur = None
        self._blur_ctrl = None
```

Remove any existing `self._current_blur = None` line to avoid duplication.

- [ ] **Step 2: Add "⊙ 分析模糊" toolbar button**

In the top bar section, after `self._refresh_btn` widget is added (`tb.addWidget(self._refresh_btn)`), add:
```python
        self._analyse_btn = QPushButton("⊙  分析模糊")
        self._analyse_btn.setCursor(Qt.PointingHandCursor)
        self._analyse_btn.setToolTip("分析尚未計算模糊分數的照片")
        self._analyse_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
            f" border:1px solid #333; border-radius:3px; padding:3px 10px;"
            f" font-size:10px; }}"
            f"QPushButton:hover:!disabled {{ background:#2a2a2a; color:#ddd;"
            f" border-color:#555; }}"
            f"QPushButton:disabled {{ color:{TEXT_MUTED}; border-color:#222; }}"
        )
        self._analyse_btn.clicked.connect(self._on_analyse_clicked)
        tb.addWidget(self._analyse_btn)
```

- [ ] **Step 3: Update _on_filter_changed to accept blur + read SettingsDB**

Replace:
```python
    def _on_filter_changed(self, statuses, colors):
        self._refresh(statuses or None, colors or None)
```
With:
```python
    def _on_filter_changed(self, statuses, colors, blur):
        self._current_blur = blur or None
        mode = self._settings.get("blur_mode", "fixed")
        threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        self._refresh(
            statuses or None, colors or None, blur or None,
            blur_mode=mode, blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )
```

- [ ] **Step 4: Update _refresh to pass blur params**

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
    def _refresh(self, statuses=None, colors=None, blur=None,
                 blur_mode="fixed", blur_fixed_threshold=100.0,
                 blur_relative_percent=20.0):
        self._current_statuses = statuses
        self._current_colors = colors
        self._current_blur = blur
        photos = self._filter_svc.filter(
            statuses=statuses, colors=colors, blur=blur,
            blur_mode=blur_mode, blur_fixed_threshold=blur_fixed_threshold,
            blur_relative_percent=blur_relative_percent,
        )
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)
```

- [ ] **Step 5: Update _on_loupe to pass blur**

Replace the `photos = self._filter_svc.filter(...)` call inside `_on_loupe`:
```python
        mode = self._settings.get("blur_mode", "fixed")
        threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        photos = self._filter_svc.filter(
            statuses=self._current_statuses,
            colors=self._current_colors,
            blur=self._current_blur,
            blur_mode=mode,
            blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )
```

Also update the `LoupeView(...)` constructor call to pass `settings=self._settings`:
```python
        loupe = LoupeView(
            photo_ids, photo_ids.index(photo_id),
            self._folder, self._photo_repo,
            self._tag_repo, self._tag_svc,
            filter_svc=self._filter_svc,
            initial_statuses=self._current_statuses,
            initial_colors=self._current_colors,
            settings=self._settings,
        )
```

- [ ] **Step 6: Update _on_loupe_filter_changed to accept blur**

Replace:
```python
    def _on_loupe_filter_changed(self, statuses: list, colors: list):
        """Filter changes inside Loupe propagate back to the grid + panel."""
        self._filter_panel.set_filter(statuses, colors)
        self._refresh(statuses or None, colors or None)
```
With:
```python
    def _on_loupe_filter_changed(self, statuses: list, colors: list):
        """Filter changes inside Loupe propagate back to the grid + panel."""
        self._filter_panel.set_filter(statuses, colors)
        mode = self._settings.get("blur_mode", "fixed")
        threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        self._refresh(
            statuses or None, colors or None, self._current_blur,
            blur_mode=mode, blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )
```

- [ ] **Step 7: Add start_blur_analysis, reanalyze_missing_blur, _on_photo_blur_updated, _on_analyse_clicked**

Add these methods to `GridView`:
```python
    def start_blur_analysis(self, db_path: str):
        """Full re-analysis of all photos. Called after import completes."""
        import sqlite3 as _sq
        from app.core.blur_worker import BlurController
        conn = _sq.connect(db_path)
        conn.row_factory = _sq.Row
        from app.db.photo_repository import PhotoRepository as _PR
        repo = _PR(conn)
        photo_ids = [p.id for p in repo.get_all()]
        conn.close()
        if not photo_ids:
            return
        self._start_blur_controller(db_path, photo_ids)

    def reanalyze_missing_blur(self, db_path: str):
        """Analyse only photos with blur_score IS NULL."""
        import sqlite3 as _sq
        from app.db.photo_repository import PhotoRepository as _PR
        conn = _sq.connect(db_path)
        conn.row_factory = _sq.Row
        repo = _PR(conn)
        photo_ids = repo.get_unanalyzed_ids()
        conn.close()
        if not photo_ids:
            return
        self._start_blur_controller(db_path, photo_ids)

    def _start_blur_controller(self, db_path: str, photo_ids: list):
        from app.core.blur_worker import BlurController
        if self._blur_ctrl is not None:
            return
        self._analyse_btn.setEnabled(False)
        self._blur_ctrl = BlurController(self._folder, db_path, photo_ids)
        self._blur_ctrl.photo_blur_updated.connect(self._on_photo_blur_updated)
        self._blur_ctrl.finished.connect(self._on_blur_finished)
        self._blur_ctrl.start()

    def _on_photo_blur_updated(self, photo_id: int, score: float):
        self._grid.update_item_tag(photo_id)

    def _on_blur_finished(self):
        self._blur_ctrl = None
        self._analyse_btn.setEnabled(True)

    def _on_analyse_clicked(self):
        from app.ui.main_window import _get_db_path_for_grid
        # db_path is passed in via start_blur_analysis; store it on first call
        if hasattr(self, "_db_path"):
            self.reanalyze_missing_blur(self._db_path)
```

> **Note:** `_on_analyse_clicked` needs `self._db_path`. This is set in Task 7 (MainWindow passes db_path to GridView).

- [ ] **Step 8: Add _db_path attribute storage**

In `GridView.__init__`, after `self._blur_ctrl = None`, add:
```python
        self._db_path: str = ""
```

Replace `_on_analyse_clicked`:
```python
    def _on_analyse_clicked(self):
        if self._db_path:
            self.reanalyze_missing_blur(self._db_path)
```

- [ ] **Step 9: Commit**

```bash
git add app/ui/grid_view.py
git commit -m "feat: wire blur filter, BlurController, and 'Analyse Blur' button in GridView"
```

---

## Task 7: MainWindow — pass SettingsDB + trigger blur

**Files:**
- Modify: `app/ui/main_window.py`

- [ ] **Step 1: Pass settings to GridView in _load_folder**

In `_load_folder`, replace:
```python
        self._grid_view = GridView(
            folder_path, photo_repo, tag_repo,
            thumb_svc, tag_svc, filter_svc,
        )
```
With:
```python
        self._grid_view = GridView(
            folder_path, photo_repo, tag_repo,
            thumb_svc, tag_svc, filter_svc,
            self._settings,
        )
```

After creating `self._grid_view`, set `_db_path` on it:
```python
        self._grid_view._db_path = db_path
```

- [ ] **Step 2: Update _on_import_finished to trigger blur analysis**

Replace:
```python
    def _on_import_finished(self):
        if self._grid_view is not None:
            self._grid_view.end_import()
        self._import_ctrl = None
```
With:
```python
    def _on_import_finished(self):
        if self._grid_view is not None:
            self._grid_view.end_import()
            self._grid_view.start_blur_analysis(self._db_path)
        self._import_ctrl = None
```

- [ ] **Step 3: Update FilterPanel _open_blur_settings call to pass SettingsDB**

`FilterPanel._open_blur_settings` currently instantiates `BlurSettingsDialog(self)` with no settings. Since `FilterPanel` doesn't own `SettingsDB`, the easiest fix is to pass settings through `GridView` → `FilterPanel`.

Update `FilterPanel.__init__` to accept an optional `settings` parameter:

In `app/ui/filter_panel.py`, update `FilterPanel.__init__`:
```python
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self._settings = settings
        ...
```

Update `_open_blur_settings`:
```python
    def _open_blur_settings(self):
        from app.ui.blur_settings_dialog import BlurSettingsDialog
        dlg = BlurSettingsDialog(self._settings, self)
        dlg.exec()
```

In `GridView.__init__`, update FilterPanel construction:
```python
        self._filter_panel = FilterPanel(settings=self._settings)
```

- [ ] **Step 4: Trigger re-open blur analysis for existing projects**

In `MainWindow._load_folder`, after the `else: self._start_scan()` block, add a call to analyse photos that already exist in DB but have no blur score:

```python
        # For existing projects, schedule blur analysis for unanalyzed photos
        if photo_repo.count() > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self._grid_view.reanalyze_missing_blur(db_path))
```

Place this AFTER `self._grid_view` is fully wired (after `import_cancel_requested.connect`), so:
```python
        self._grid_view.refresh_requested.connect(self._on_refresh_requested)
        self._grid_view.import_cancel_requested.connect(self._on_import_cancel_requested)

        # Analyse unscored photos from previous sessions
        if photo_repo.count() > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self._grid_view.reanalyze_missing_blur(db_path))
```

- [ ] **Step 5: Commit**

```bash
git add app/ui/main_window.py app/ui/filter_panel.py
git commit -m "feat: MainWindow passes SettingsDB to GridView; triggers blur after import and on re-open"
```

---

## Task 8: Full test suite + smoke test

**Files:**
- Run: `pytest`
- Run: `python main.py` (manual)

- [ ] **Step 1: Run full test suite**

```
pytest -v
```
Expected: all tests pass (target 55+). Fix any failures before proceeding.

- [ ] **Step 2: Manual smoke test**

```
python main.py
```

Verify all 6 items:
1. Open a folder with JPEG photos → import runs → blur analysis auto-starts (progress bar or ⊙ button disables)
2. Filter panel shows BLUR section with 模糊/清晰/未分析 checkboxes and ⚙ button
3. ⚙ opens BlurSettingsDialog, switching mode and threshold saves to SettingsDB (not settings.json)
4. Checking 模糊+清晰 simultaneously returns BOTH groups (OR logic), not empty
5. Open a photo in Loupe → `Blur: 123.4` appears top-right in green (sharp) or red (blurry)
6. ⊙ 分析模糊 button triggers re-analysis of unanalyzed photos only

Also verify RAW handling:
7. If any RAW files exist in the folder, they appear as "未分析" (—) in Loupe, not as blurry

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: blur detection phase 2 complete — Tasks 9-11 + 6 bug fixes"
```
