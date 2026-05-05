# pytest-qt / QTest GUI Smoke Test Plan

**Date:** 2026-05-05  
**Scope:** Automated GUI smoke tests that interact with SwiftCull like a user through Qt widgets.  
**Primary tool:** `pytest-qt` (`qtbot`) plus PySide6 `QTest` where lower-level events are needed.

## Goal

Build a maintainable GUI smoke suite that can:

- Launch `MainWindow`.
- Load a temporary photo folder without using a native file dialog.
- Click and type through Qt widgets.
- Verify visible UI state, emitted signals, database effects, and exported files.
- Run locally and in CI with `python -m pytest -q -m smoke`.

This is not a pixel-perfect visual regression suite. It is a workflow smoke suite for catching broken wiring, signal signature drift, missing widgets, thread regressions, and obvious user-facing crashes.

## Architecture Choice

Use three layers:

1. **Widget-level GUI smoke**
   - Instantiate widgets directly.
   - Use `qtbot.mouseClick`, `qtbot.keyClick`, `qtbot.waitSignal`, and `qtbot.waitUntil`.
   - Fastest and most stable.

2. **MainWindow workflow smoke**
   - Instantiate `MainWindow`.
   - Call `window._load_folder(test_folder)` as the test seam instead of automating the OS folder picker.
   - Click actual SwiftCull controls after the folder is loaded.

3. **Optional packaged-app smoke later**
   - Only after widget tests are stable.
   - Candidate tools: Squish or pywinauto.
   - Not part of the first implementation pass.

## Testability Requirements

Add stable selectors before writing broad GUI smoke tests. Text labels are currently mojibake-prone in some environments and may change with localization, so tests should not find widgets by button text.

Required `objectName` values:

### `WelcomeView`

- `welcome_open_folder_button`
- `welcome_recent_projects_container`

### `GridView`

- `grid_refresh_button`
- `grid_analyze_blur_button`
- `grid_analyze_exposure_button`
- `grid_split_preview_button`
- `grid_export_button`
- `grid_select_all_button`
- `grid_deselect_all_button`
- `grid_selection_label`
- `grid_import_progress`
- `grid_import_label`
- `grid_thumbnail_grid`
- `grid_filter_panel`

### `FilterPanel`

- `filter_toggle_button`
- `filter_clear_button`
- `filter_status_pick`
- `filter_status_reject`
- `filter_status_maybe`
- `filter_status_untagged`
- `filter_color_red`
- `filter_color_orange`
- `filter_color_yellow`
- `filter_color_green`
- `filter_color_blue`
- `filter_color_purple`
- `filter_blur_blurry`
- `filter_blur_sharp`
- `filter_blur_unanalyzed`
- `filter_exposure_overexposed`
- `filter_exposure_underexposed`
- `filter_exposure_black_frame`
- `filter_exposure_normal`
- `filter_exposure_unanalyzed`

### `LoupeView`

- `loupe_image_label`
- `loupe_status_label`
- `loupe_blur_label`
- `loupe_exposure_label`
- `loupe_status_pick_button`
- `loupe_status_reject_button`
- `loupe_status_maybe_button`
- `loupe_status_clear_button`
- `loupe_close_button`

### `ExportDialog`

- `export_pick_checkbox`
- `export_reject_checkbox`
- `export_maybe_checkbox`
- `export_untagged_checkbox`
- `export_destination_input`
- `export_browse_button`
- `export_count_label`
- `export_result_label`
- `export_cancel_button`
- `export_start_button`

## Pytest Setup

Add `pytest.ini`:

```ini
[pytest]
markers =
    smoke: fast workflow smoke tests for release confidence
    gui: tests that instantiate Qt widgets
qt_api = pyside6
```

Prefer fixtures over per-test setup:

- `isolated_app_env`: sets `LOCALAPPDATA` and `APPDATA` to `tmp_path`.
- `sample_photo_folder`: creates 3-5 deterministic JPEGs with Pillow.
- `shown_main_window`: creates `MainWindow`, calls `qtbot.addWidget(window)`, shows it, and waits until exposed.
- `loaded_main_window`: calls `window._load_folder(str(sample_photo_folder))`, waits for import and initial blur analysis to settle.

Example fixture shape:

```python
@pytest.fixture
def isolated_app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return tmp_path
```

## First Smoke Test Set

### Smoke 1: MainWindow opens on Welcome

Existing test: `tests/ui/test_app_smoke.py`

Convert to:

- Use `qtbot` instead of manual `QApplication`.
- Mark with `@pytest.mark.smoke` and `@pytest.mark.gui`.
- Assert `QStackedWidget.currentWidget()` is `WelcomeView`.

### Smoke 2: Load folder through MainWindow test seam

Scenario:

1. Create temp folder with 3 JPEGs.
2. Launch `MainWindow`.
3. Call `window._load_folder(folder)`.
4. Wait until import finishes and grid has 3 photos.
5. Assert project DB exists under isolated `LOCALAPPDATA`.
6. Assert `PhotoRepository.count() == 3`.

This validates:

- `MainWindow -> GridView` construction.
- project directory creation.
- scan/import path.
- thumbnail path does not crash.

### Smoke 3: FilterPanel click updates GridView

Scenario:

1. Load 3 photos.
2. Programmatically tag one photo as `pick`.
3. Refresh grid.
4. Click `filter_status_pick`.
5. Wait until grid displays only the picked photo.
6. Click `filter_clear_button`.
7. Wait until all photos return.

This validates:

- custom checkbox click handling.
- `filter_changed` signal shape.
- `GridView._on_filter_changed`.
- `FilterService` integration from UI.

### Smoke 4: Selection buttons work through UI clicks

Scenario:

1. Load 3 photos.
2. Click `grid_select_all_button`.
3. Assert selection label is visible and selected count is 3.
4. Click `grid_deselect_all_button`.
5. Assert selection label is hidden or selection count is 0.

This validates:

- `GridView` status bar wiring.
- `ThumbnailGrid.select_all`.
- `ThumbnailGrid.clear_selection`.
- `selection_changed` propagation.

### Smoke 5: Blur and exposure analysis buttons

Scenario:

1. Load 3 JPEGs.
2. Clear blur/exposure values in DB for at least one photo.
3. Click `grid_analyze_blur_button`.
4. Wait until button is enabled again.
5. Assert at least one `blur_score` is not null.
6. Click `grid_analyze_exposure_button`.
7. Wait until button is enabled again.
8. Assert exposure fields are not null.

This validates:

- button click wiring.
- `BlurController` / `ExposureController` lifecycle.
- thread completion signal.
- DB writes.

### Smoke 6: Loupe opens and keyboard tagging works

Scenario:

1. Load photos.
2. Open loupe using `GridView._on_loupe(photo_id)` for the first pass, or double-click a thumbnail once item selectors are stable.
3. Use `qtbot.keyClick(loupe, Qt.Key_P)`.
4. Assert DB tag for active photo is `pick`.
5. Assert `loupe_blur_label` and `loupe_exposure_label` exist and do not crash during update.
6. Press `Esc`.
7. Assert loupe closes.

This validates:

- Loupe construction.
- keyboard shortcuts.
- tag propagation.
- blur/exposure label code paths.

### Smoke 7: Export picked photos

Recommended first implementation avoids native dialogs:

1. Load photos.
2. Tag one photo as `pick`.
3. Instantiate `ExportDialog` directly with repo objects.
4. Set destination input to a temp export folder.
5. Click `export_start_button`.
6. Assert exported file exists.
7. Assert result label reports completion.

Later, this can be promoted to a `GridView` click by monkeypatching `ExportDialog.exec`.

This validates:

- export UI wiring.
- `ExportService`.
- tag filter to file copy/move path.

## Implementation Tasks

### Task 1: Add test markers and selector names

- [ ] Add `pytest.ini` with `smoke`, `gui`, and `qt_api = pyside6`.
- [ ] Add `objectName` values to `WelcomeView`.
- [ ] Add `objectName` values to `GridView`.
- [ ] Add `objectName` values to `FilterPanel`.
- [ ] Add `objectName` values to `LoupeView`.
- [ ] Add `objectName` values to `ExportDialog`.
- [ ] Run `python -m pytest -q`.

### Task 2: Convert existing UI smoke to pytest-qt

- [ ] Update `tests/ui/test_app_smoke.py` to use `qtbot`.
- [ ] Mark it with `@pytest.mark.smoke` and `@pytest.mark.gui`.
- [ ] Keep the test focused on startup only.
- [ ] Run `python -m pytest -q tests/ui/test_app_smoke.py`.

### Task 3: Add shared GUI smoke fixtures

- [ ] Create `tests/smoke/conftest.py` or extend `tests/conftest.py`.
- [ ] Add `isolated_app_env`.
- [ ] Add `sample_photo_folder`.
- [ ] Add `shown_main_window`.
- [ ] Add helper `find_required(widget, object_name, cls=None)`.
- [ ] Add helper `wait_for_no_import(window, qtbot)`.

### Task 4: Add MainWindow load-folder smoke

- [ ] Create `tests/smoke/test_main_window_workflow.py`.
- [ ] Add `test_load_folder_imports_photos`.
- [ ] Verify DB path and count.
- [ ] Verify grid widget exists and loaded count is 3.
- [ ] Run `python -m pytest -q -m smoke`.

### Task 5: Add filter and selection smoke

- [ ] Add `test_filter_pick_checkbox_filters_grid`.
- [ ] Add `test_select_all_and_deselect_all_buttons`.
- [ ] Avoid text-based selectors.
- [ ] Run `python -m pytest -q -m smoke`.

### Task 6: Add analysis smoke

- [ ] Add `test_blur_button_writes_blur_scores`.
- [ ] Add `test_exposure_button_writes_exposure_scores`.
- [ ] Use `qtbot.waitUntil` with a timeout.
- [ ] Ensure controllers are stopped in teardown.
- [ ] Run `python -m pytest -q -m smoke`.

### Task 7: Add Loupe smoke

- [ ] Add `test_loupe_keyboard_tagging_and_close`.
- [ ] Start by calling `GridView._on_loupe(photo_id)` directly.
- [ ] Later replace with actual double-click once thumbnail item lookup is stable.
- [ ] Run `python -m pytest -q -m smoke`.

### Task 8: Add ExportDialog smoke

- [ ] Add `test_export_dialog_exports_picked_photo`.
- [ ] Set destination path directly.
- [ ] Click start button.
- [ ] Verify exported file exists.
- [ ] Run `python -m pytest -q -m smoke`.

### Task 9: CI command and docs

- [ ] Document `python -m pytest -q -m smoke`.
- [ ] Add a full local pre-release command: `python -m pytest -q`.
- [ ] Add troubleshooting notes for Qt platform/headless failures.

## Stability Rules

- Do not locate controls by visible text.
- Do not depend on exact pixel positions unless testing canvas/grid hit detection.
- Avoid native OS dialogs in smoke tests; use seams or monkeypatches.
- Keep test images small and deterministic.
- Prefer DB/state assertions over screenshots.
- Use screenshots only for debugging failures, not as baseline assertions.
- Every test that starts a worker must wait for completion or explicitly stop it.

## CI Notes

For Windows CI, these tests should run with a normal desktop-capable runner. If a runner has no display, set the Qt platform explicitly only after verifying PySide6 supports the target environment:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q -m smoke
```

Some visual widgets may behave differently offscreen. If that happens, keep service-level smoke in CI and run GUI smoke on a Windows runner with an interactive desktop.

## Definition of Done

- `python -m pytest -q -m smoke` passes.
- `python -m pytest -q` passes.
- Smoke tests cover startup, folder load/import, filter click, selection click, blur analysis, exposure analysis, loupe keyboard tagging, and export.
- GUI tests use stable `objectName` selectors.
- No test relies on user machine `%LOCALAPPDATA%` or `%APPDATA%`.
