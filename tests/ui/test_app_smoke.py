import pytest

from PySide6.QtWidgets import QStackedWidget

from app.ui.main_window import MainWindow
from app.ui.welcome_view import WelcomeView


@pytest.mark.smoke
@pytest.mark.gui
def test_main_window_starts_on_welcome_view(tmp_path, monkeypatch, qtbot):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    window = MainWindow()
    qtbot.addWidget(window)
    try:
        window.show()
        qtbot.waitExposed(window)

        stack = window.findChild(QStackedWidget)
        assert stack is not None
        assert isinstance(stack.currentWidget(), WelcomeView)
        assert window.windowTitle() == "SwiftCull"
    finally:
        window.close()
