import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from app.db.connection import get_connection
from app.db.photo_repository import PhotoRepository
from app.ui.export_dialog import ExportDialog
from app.ui.filter_panel import FilterPanel
from app.ui.grid_view import GridView
from app.ui.loupe_view import LoupeView

from .conftest import (
    find_required,
    wait_for_blur_finished,
    wait_for_exposure_finished,
)


pytestmark = [pytest.mark.smoke, pytest.mark.gui]


def _grid_view(window) -> GridView:
    grid = window._grid_view
    assert isinstance(grid, GridView)
    return grid


def _photo_ids(window):
    return [p.id for p in window._photo_repo.get_all()]


def test_load_folder_imports_photos(loaded_main_window):
    window = loaded_main_window
    grid = _grid_view(window)

    assert os.path.exists(window._db_path)
    assert window._photo_repo.count() == 3
    assert grid._grid.objectName() == "grid_thumbnail_grid"
    assert len(grid._grid._photos) == 3


def test_filter_pick_checkbox_filters_grid(loaded_main_window, qtbot):
    window = loaded_main_window
    grid = _grid_view(window)
    first_id = _photo_ids(window)[0]
    grid._tag_svc.set_status(first_id, "pick")
    grid._refresh()

    panel = find_required(grid, "grid_filter_panel", FilterPanel)
    pick_filter = find_required(panel, "filter_status_pick")
    clear_filter = find_required(panel, "filter_clear_button", QPushButton)

    qtbot.mouseClick(pick_filter, Qt.LeftButton)
    qtbot.waitUntil(lambda: len(grid._grid._photos) == 1, timeout=3000)
    assert grid._grid._photos[0].id == first_id

    qtbot.mouseClick(clear_filter, Qt.LeftButton)
    qtbot.waitUntil(lambda: len(grid._grid._photos) == 3, timeout=3000)


def test_select_all_and_deselect_all_buttons(loaded_main_window, qtbot):
    grid = _grid_view(loaded_main_window)
    select_all = find_required(grid, "grid_select_all_button", QPushButton)
    deselect_all = find_required(grid, "grid_deselect_all_button", QPushButton)
    selection_label = find_required(grid, "grid_selection_label", QLabel)

    qtbot.mouseClick(select_all, Qt.LeftButton)
    qtbot.waitUntil(lambda: len(grid._selected_ids) == 3, timeout=3000)
    assert selection_label.isVisible()

    qtbot.mouseClick(deselect_all, Qt.LeftButton)
    qtbot.waitUntil(lambda: len(grid._selected_ids) == 0, timeout=3000)
    assert not selection_label.isVisible()


def test_blur_button_writes_blur_scores(loaded_main_window, qtbot):
    window = loaded_main_window
    grid = _grid_view(window)
    button = find_required(grid, "grid_analyze_blur_button", QPushButton)

    window._photo_repo._conn.execute("UPDATE photos SET blur_score=NULL")
    window._photo_repo._conn.commit()

    qtbot.mouseClick(button, Qt.LeftButton)
    wait_for_blur_finished(window, qtbot)

    scores = [p.blur_score for p in window._photo_repo.get_all()]
    assert any(score is not None for score in scores)


def test_exposure_button_writes_exposure_scores(loaded_main_window, qtbot):
    window = loaded_main_window
    grid = _grid_view(window)
    button = find_required(grid, "grid_analyze_exposure_button", QPushButton)

    for photo_id in _photo_ids(window):
        window._photo_repo.clear_exposure_scores(photo_id)

    qtbot.mouseClick(button, Qt.LeftButton)
    wait_for_exposure_finished(window, qtbot)

    photos = window._photo_repo.get_all()
    assert any(p.exposure_mean is not None for p in photos)
    assert any(p.exposure_overexposed is not None for p in photos)
    assert any(p.exposure_underexposed is not None for p in photos)


def test_export_dialog_exports_picked_photo(loaded_main_window, tmp_path, qtbot):
    window = loaded_main_window
    first = window._photo_repo.get_all()[0]
    window._grid_view._tag_svc.set_status(first.id, "pick")

    dest = tmp_path / "exported"
    dialog = ExportDialog(
        window._folder_path,
        window._photo_repo,
        window._grid_view._tag_repo,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dest_input = find_required(dialog, "export_destination_input")
    start = find_required(dialog, "export_start_button", QPushButton)
    result = find_required(dialog, "export_result_label", QLabel)

    dest_input.setText(str(dest))
    qtbot.mouseClick(start, Qt.LeftButton)
    qtbot.waitUntil(lambda: result.isVisible(), timeout=10000)

    assert (dest / first.filename).exists()
    dialog.close()


def test_loupe_keyboard_tagging_and_close(loaded_main_window, qtbot):
    window = loaded_main_window
    grid = _grid_view(window)
    photo_ids = _photo_ids(window)
    first_id = photo_ids[0]

    loupe = LoupeView(
        photo_ids,
        0,
        window._folder_path,
        window._photo_repo,
        grid._tag_repo,
        grid._tag_svc,
        filter_svc=grid._filter_svc,
        settings=grid._settings,
    )
    qtbot.addWidget(loupe)
    loupe.show()
    qtbot.waitExposed(loupe)

    qtbot.keyClick(loupe, Qt.Key_P)
    tag = grid._tag_repo.get_by_photo_id(first_id)
    assert tag is not None and tag.status == "pick"

    assert loupe.findChild(QLabel, "loupe_blur_label") is not None
    assert loupe.findChild(QLabel, "loupe_exposure_label") is not None

    with qtbot.waitSignal(loupe.closed, timeout=3000):
        qtbot.keyClick(loupe, Qt.Key_Escape)


def test_project_db_can_be_reopened_after_gui_import(loaded_main_window):
    window = loaded_main_window
    conn = get_connection(window._db_path)
    try:
        repo = PhotoRepository(conn)
        assert repo.count() == 3
    finally:
        conn.close()
