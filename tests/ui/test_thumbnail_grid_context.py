import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
import sys


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a


def _make_grid(app):
    from app.ui.thumbnail_grid import ThumbnailGrid
    grid = ThumbnailGrid()
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
