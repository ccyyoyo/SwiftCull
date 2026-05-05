from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QWidget


@pytest.fixture
def isolated_app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return tmp_path


@pytest.fixture
def sample_photo_folder(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    colors = [
        (32, 64, 96),
        (180, 160, 120),
        (245, 245, 245),
    ]
    for idx, color in enumerate(colors, start=1):
        img = Image.new("RGB", (96, 72), color)
        img.save(folder / f"photo_{idx}.jpg", "JPEG")
    return folder


@pytest.fixture
def shown_main_window(isolated_app_env, qtbot):
    from app.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    yield window
    window.close()


@pytest.fixture
def loaded_main_window(shown_main_window, sample_photo_folder, qtbot):
    shown_main_window._load_folder(str(sample_photo_folder))
    wait_for_import_finished(shown_main_window, qtbot)
    wait_for_blur_finished(shown_main_window, qtbot)
    return shown_main_window


def find_required(parent: QWidget, object_name: str, cls=None):
    widget = parent.findChild(cls or QWidget, object_name)
    assert widget is not None, f"Missing required widget: {object_name}"
    return widget


def wait_for_import_finished(window, qtbot, expected_count=3):
    qtbot.waitUntil(
        lambda: (
            window._import_ctrl is None
            and window._photo_repo is not None
            and window._photo_repo.count() == expected_count
        ),
        timeout=10000,
    )


def wait_for_blur_finished(window, qtbot):
    qtbot.waitUntil(
        lambda: (
            window._grid_view is not None
            and window._grid_view._blur_ctrl is None
        ),
        timeout=10000,
    )


def wait_for_exposure_finished(window, qtbot):
    qtbot.waitUntil(
        lambda: (
            window._grid_view is not None
            and window._grid_view._exposure_ctrl is None
        ),
        timeout=10000,
    )
