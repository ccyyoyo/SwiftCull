# Batch Action UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-click context menu (with status and color submenus) and status-bar selection count + Select All / Deselect All controls so mouse users can trigger batch tagging.

**Architecture:** Two changes, each independent. (1) `ThumbnailGrid` gains a `contextMenuEvent`, a new `batch_color_requested` signal, plus `select_all()` and `clear_selection()` helpers. (2) `GridView` status bar gets a selection-count label and two buttons, wired to the new grid helpers; `GridView` also gets a `_on_batch_color()` handler that calls `tag_svc.set_color()` per photo.

**Tech Stack:** PySide6 (`QMenu`, `QAction`, `QPushButton`, `QLabel`), existing `TagService`, existing `batch_confirm_dialog`.

---

## File Map

| File | Change |
|------|--------|
| `app/ui/thumbnail_grid.py` | Add signal `batch_color_requested`, add `contextMenuEvent()`, add `select_all()`, add `clear_selection()` |
| `app/ui/grid_view.py` | Add selection label + buttons to status bar, update `_on_selection_changed()`, add `_on_batch_color()` |
| `app/core/tag_service.py` | Add `batch_set_color()` and `batch_clear_color()` methods |
| `tests/ui/test_thumbnail_grid_context.py` | New test file |
| `tests/core/test_tag_service_batch_color.py` | New test file |

---

## Task 1: Add `batch_set_color` and `batch_clear_color` to TagService

**Files:**
- Modify: `app/core/tag_service.py`
- Test: `tests/core/test_tag_service_batch_color.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_tag_service_batch_color.py`:

```python
import pytest
from unittest.mock import MagicMock, call
from app.core.tag_service import TagService


def _make_svc():
    repo = MagicMock()
    repo.get_by_photo_id.return_value = None
    return TagService(repo), repo


def test_batch_set_color_calls_set_color_for_each_id():
    svc, repo = _make_svc()
    tag1 = MagicMock(); tag1.color = None; tag1.status = None
    tag2 = MagicMock(); tag2.color = None; tag2.status = None
    repo.get_by_photo_id.side_effect = lambda pid: {1: tag1, 2: tag2}[pid]

    svc.batch_set_color([1, 2], "red")

    assert tag1.color == "red"
    assert tag2.color == "red"
    assert repo.upsert.call_count == 2


def test_batch_clear_color_sets_none():
    svc, repo = _make_svc()
    tag1 = MagicMock(); tag1.color = "blue"; tag1.status = "pick"
    repo.get_by_photo_id.return_value = tag1

    svc.batch_clear_color([1])

    assert tag1.color is None
    repo.upsert.assert_called_once()


def test_batch_set_color_invalid_raises():
    svc, _ = _make_svc()
    with pytest.raises(ValueError):
        svc.batch_set_color([1], "magenta")
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/core/test_tag_service_batch_color.py -v
```

Expected: `AttributeError: 'TagService' object has no attribute 'batch_set_color'`

- [ ] **Step 3: Read current TagService to find insertion point**

Open `app/core/tag_service.py` and locate `batch_clear_status` (around line 39). New methods go directly after it.

- [ ] **Step 4: Add `batch_set_color` and `batch_clear_color`**

In `app/core/tag_service.py`, after `batch_clear_status`:

```python
def batch_set_color(self, photo_ids: List[int], color: str) -> None:
    if color not in VALID_COLORS:
        raise ValueError(f"Invalid color: {color!r}")
    for photo_id in photo_ids:
        tag = self._get_or_create(photo_id)
        tag.color = color
        self._repo.upsert(tag)

def batch_clear_color(self, photo_ids: List[int]) -> None:
    for photo_id in photo_ids:
        tag = self._get_or_create(photo_id)
        tag.color = None
        self._repo.upsert(tag)
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/core/test_tag_service_batch_color.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```
git add app/core/tag_service.py tests/core/test_tag_service_batch_color.py
git commit -m "feat: add batch_set_color and batch_clear_color to TagService"
```

---

## Task 2: Add `batch_color_requested` signal, `select_all()`, `clear_selection()` to ThumbnailGrid

**Files:**
- Modify: `app/ui/thumbnail_grid.py`
- Test: `tests/ui/test_thumbnail_grid_context.py`

- [ ] **Step 1: Write failing tests**

Create `tests/ui/test_thumbnail_grid_context.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
import sys

@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a

def _make_grid(app):
    from app.ui.thumbnail_grid import ThumbnailGrid
    grid = ThumbnailGrid()
    # Inject fake photos
    photo_ids = [1, 2, 3]
    photos = [MagicMock(id=pid, filename=f"img{pid}.jpg", relative_path=f"img{pid}.jpg") for pid in photo_ids]
    tag_repo = MagicMock()
    tag_repo.get_by_photo_id.return_value = None
    thumb_svc = MagicMock()
    thumb_svc.get_thumbnail.return_value = ""
    grid.load_photos(photos, tag_repo, thumb_svc, "/fake")
    return grid, photo_ids


def test_select_all_selects_all_photos(app):
    grid, photo_ids = _make_grid(app)
    received = []
    grid.selection_changed.connect(received.append)

    grid.select_all()

    assert set(received[-1]) == set(photo_ids)


def test_clear_selection_empties_selection(app):
    grid, photo_ids = _make_grid(app)
    grid.select_all()
    received = []
    grid.selection_changed.connect(received.append)

    grid.clear_selection()

    assert received[-1] == []


def test_batch_color_requested_signal_exists(app):
    grid, _ = _make_grid(app)
    assert hasattr(grid, 'batch_color_requested')
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/ui/test_thumbnail_grid_context.py -v
```

Expected: `AttributeError: 'ThumbnailGrid' object has no attribute 'select_all'`

- [ ] **Step 3: Add signal and methods to ThumbnailGrid**

In `app/ui/thumbnail_grid.py`:

**At line 87** (after `batch_status_requested = Signal(list, str)`), add:
```python
batch_color_requested = Signal(list, str)
```

**After `clear_selection` — add both new methods at the end of the class** (before `keyPressEvent`):

```python
def select_all(self):
    all_ids = set(self._items.keys())
    self._set_selection(all_ids, emit=True)

def clear_selection(self):
    self._set_selection(set(), emit=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/ui/test_thumbnail_grid_context.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add app/ui/thumbnail_grid.py tests/ui/test_thumbnail_grid_context.py
git commit -m "feat: add batch_color_requested signal, select_all, clear_selection to ThumbnailGrid"
```

---

## Task 3: Add `contextMenuEvent` to ThumbnailGrid

**Files:**
- Modify: `app/ui/thumbnail_grid.py`

- [ ] **Step 1: Add imports at top of file**

In `app/ui/thumbnail_grid.py`, update the `PySide6.QtWidgets` import to include `QMenu`:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QGridLayout, QSlider, QRubberBand, QMenu,
)
```

- [ ] **Step 2: Add `contextMenuEvent` method to ThumbnailGrid**

Add after `clear_selection()` (before `keyPressEvent`):

```python
def contextMenuEvent(self, event):
    # Find which item was right-clicked
    pos_in_container = self._container.mapFrom(self, event.pos())
    clicked_id: int | None = None
    for pid, item in self._items.items():
        if item.geometry().contains(pos_in_container):
            clicked_id = pid
            break

    if clicked_id is None:
        return

    # If the clicked photo is not in selection, replace selection with it
    if clicked_id not in self._selected:
        self._set_selection({clicked_id}, emit=True)

    photo_ids = list(self._selected)
    n = len(photo_ids)

    menu = QMenu(self)
    menu.setStyleSheet(
        "QMenu { background:#212121; color:#e8e8e8; border:1px solid #333; }"
        "QMenu::item { padding:5px 24px 5px 12px; }"
        "QMenu::item:selected { background:#2d3a4a; }"
        "QMenu::separator { height:1px; background:#333; margin:3px 0; }"
        "QMenu::item:disabled { color:#555; }"
    )

    header = menu.addAction(f"標記 {n} 張照片")
    header.setEnabled(False)
    menu.addSeparator()

    # Status submenu
    status_menu = menu.addMenu("標記狀態")
    status_menu.setStyleSheet(menu.styleSheet())
    act_pick   = status_menu.addAction("✓  Pick")
    act_pick.setShortcut("P")
    act_reject = status_menu.addAction("✗  Reject")
    act_reject.setShortcut("R")
    act_maybe  = status_menu.addAction("?  Maybe")
    act_maybe.setShortcut("M")
    status_menu.addSeparator()
    act_clear_status = status_menu.addAction("清除狀態")
    act_clear_status.setShortcut("U")

    # Color submenu
    color_menu = menu.addMenu("顏色標籤")
    color_menu.setStyleSheet(menu.styleSheet())
    color_actions = {
        "red":    color_menu.addAction("🔴  紅"),
        "orange": color_menu.addAction("🟠  橙"),
        "yellow": color_menu.addAction("🟡  黃"),
        "green":  color_menu.addAction("🟢  綠"),
        "blue":   color_menu.addAction("🔵  藍"),
        "purple": color_menu.addAction("🟣  紫"),
    }
    color_menu.addSeparator()
    act_clear_color = color_menu.addAction("清除顏色")

    chosen = menu.exec(event.globalPos())

    if chosen == act_pick:
        self.batch_status_requested.emit(photo_ids, "pick")
    elif chosen == act_reject:
        self.batch_status_requested.emit(photo_ids, "reject")
    elif chosen == act_maybe:
        self.batch_status_requested.emit(photo_ids, "maybe")
    elif chosen == act_clear_status:
        self.batch_status_requested.emit(photo_ids, "clear")
    elif chosen == act_clear_color:
        self.batch_color_requested.emit(photo_ids, "clear")
    else:
        for color, act in color_actions.items():
            if chosen == act:
                self.batch_color_requested.emit(photo_ids, color)
                break
```

- [ ] **Step 3: Manual smoke test**

Run `python main.py`, open a folder, right-click a thumbnail. Verify:
- Menu shows "標記 1 張照片" as disabled header
- "標記狀態" submenu opens with Pick/Reject/Maybe/清除狀態
- "顏色標籤" submenu opens with 6 colors + 清除顏色
- Clicking Pick tags the photo (green ✓ badge appears)

- [ ] **Step 4: Commit**

```
git add app/ui/thumbnail_grid.py
git commit -m "feat: add right-click context menu to ThumbnailGrid"
```

---

## Task 4: Wire `batch_color_requested` in GridView

**Files:**
- Modify: `app/ui/grid_view.py`

- [ ] **Step 1: Connect signal in `__init__`**

In `app/ui/grid_view.py`, after line:
```python
self._grid.batch_status_requested.connect(self._on_batch_status)
```
Add:
```python
self._grid.batch_color_requested.connect(self._on_batch_color)
```

- [ ] **Step 2: Add `_on_batch_color` handler**

Add at the end of `GridView`, after `_on_batch_status`:

```python
def _on_batch_color(self, photo_ids: list, color: str):
    if not photo_ids:
        return
    if color == "clear":
        self._tag_svc.batch_clear_color(photo_ids)
    else:
        self._tag_svc.batch_set_color(photo_ids, color)
    for pid in photo_ids:
        self._grid.update_item_tag(pid)
```

- [ ] **Step 3: Manual smoke test**

Run `python main.py`, right-click a thumbnail → 顏色標籤 → 紅. Verify red dot appears bottom-left of thumbnail.

- [ ] **Step 4: Commit**

```
git add app/ui/grid_view.py
git commit -m "feat: wire batch_color_requested in GridView"
```

---

## Task 5: Add selection count label and Select All / Deselect All to status bar

**Files:**
- Modify: `app/ui/grid_view.py`

- [ ] **Step 1: Add widgets to status bar in `__init__`**

In `app/ui/grid_view.py`, locate the status bar section (around line 207):

```python
sb = QHBoxLayout(self._status_bar)
sb.setContentsMargins(10, 0, 10, 0)
sb.setSpacing(8)
sb.addStretch()
```

Replace with:

```python
sb = QHBoxLayout(self._status_bar)
sb.setContentsMargins(10, 0, 10, 0)
sb.setSpacing(8)

_btn_style = (
    f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
    f" border:1px solid #333; border-radius:3px; padding:1px 8px;"
    f" font-size:10px; }}"
    f"QPushButton:hover {{ background:#2a2a2a; color:#ddd; border-color:#555; }}"
)

self._select_all_btn = QPushButton("全選")
self._select_all_btn.setFixedHeight(18)
self._select_all_btn.setCursor(Qt.PointingHandCursor)
self._select_all_btn.setStyleSheet(_btn_style)
self._select_all_btn.clicked.connect(self._grid.select_all)
sb.addWidget(self._select_all_btn)

self._deselect_btn = QPushButton("取消全選")
self._deselect_btn.setFixedHeight(18)
self._deselect_btn.setCursor(Qt.PointingHandCursor)
self._deselect_btn.setStyleSheet(_btn_style)
self._deselect_btn.clicked.connect(self._grid.clear_selection)
self._deselect_btn.hide()
sb.addWidget(self._deselect_btn)

self._selection_label = QLabel("")
self._selection_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px;")
self._selection_label.hide()
sb.addWidget(self._selection_label)

sb.addStretch()
```

- [ ] **Step 2: Update `_on_selection_changed` to update status bar**

Replace the existing `_on_selection_changed` method:

```python
def _on_selection_changed(self, ids: list):
    self._selected_ids = ids
    n = len(ids)
    if n > 0:
        self._selection_label.setText(f"已選 {n} 張")
        self._selection_label.show()
        self._deselect_btn.show()
        self._select_all_btn.hide()
    else:
        self._selection_label.hide()
        self._deselect_btn.hide()
        self._select_all_btn.show()
    # update preview pane if split mode and single selection
    if self._split_mode and n == 1:
        photo = self._photo_repo.get_by_id(ids[0])
        if photo:
            abs_path = os.path.join(self._folder, photo.relative_path)
            self._preview.show_photo(abs_path, photo.filename)
    elif self._split_mode and n == 0:
        self._preview.clear()
```

- [ ] **Step 3: Manual smoke test**

Run `python main.py`, open a folder:
- Status bar shows "全選" button on the left
- Click "全選" → all thumbnails get blue border, label shows "已選 N 張", "取消全選" appears, "全選" hides
- Click "取消全選" → selection cleared, "全選" reappears
- Shift+Click several items → count updates live

- [ ] **Step 4: Commit**

```
git add app/ui/grid_view.py
git commit -m "feat: add selection count label and Select All / Deselect All to status bar"
```

---

## Task 6: Run full test suite

- [ ] **Step 1: Run all tests**

```
pytest -v
```

Expected: all previously passing tests still pass; new tests pass.

- [ ] **Step 2: Fix any regressions**

If tests fail, investigate before committing any fixes.

- [ ] **Step 3: Final smoke test**

Run `python main.py`. Verify end-to-end:
1. Select 3 photos with Shift+Click → "已選 3 張" shows in status bar
2. Right-click selected → "標記 3 張照片" header visible
3. 標記狀態 → Pick → confirmation dialog → confirm → all 3 get ✓ badge
4. Right-click → 顏色標籤 → 藍 → all 3 get blue dot
5. 取消全選 → label hides, "全選" reappears
6. 全選 → all thumbnails selected
7. Keyboard P → batch pick works as before
