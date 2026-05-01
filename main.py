import os
import sys
import logging
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.utils.theme import APP_STYLESHEET

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

def main():
    try:
        log.info("Starting SwiftCull...")
        app = QApplication(sys.argv)
        log.info("QApplication created")
        app.setStyleSheet(APP_STYLESHEET)
        log.info("Stylesheet applied")
        window = MainWindow()
        log.info("MainWindow created")
        window.show()
        log.info("Window shown, entering event loop")
        test_quit_ms = os.environ.get("SWIFTCULL_TEST_QUIT_MS")
        if test_quit_ms:
            QTimer.singleShot(int(test_quit_ms), app.quit)
        sys.stdout.flush()
        sys.stderr.flush()
        exit_code = app.exec()
        log.info("Event loop exited with code: %d", exit_code)
        sys.exit(exit_code)
    except Exception as e:
        log.exception("Fatal error: %s", e)
        raise

if __name__ == "__main__":
    main()
