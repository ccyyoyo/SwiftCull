import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QStackedWidget

from app.ui.main_window import MainWindow
from app.ui.welcome_view import WelcomeView


def test_main_window_starts_on_welcome_view(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    try:
        window.show()
        app.processEvents()

        stack = window.findChild(QStackedWidget)
        assert stack is not None
        assert isinstance(stack.currentWidget(), WelcomeView)
        assert window.windowTitle() == "SwiftCull"
    finally:
        window.close()
        app.processEvents()
