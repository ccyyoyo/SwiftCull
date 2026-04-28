import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from app.utils.theme import ACCENT, BG_MAIN, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED

class WelcomeView(QWidget):
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet(f"background:{BG_MAIN};")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("SwiftCull")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:40px; font-weight:300; letter-spacing:8px;"
        )
        layout.addWidget(title)

        sub = QLabel("Photo Culling  ·  Local  ·  Fast")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:12px; letter-spacing:3px;"
        )
        layout.addWidget(sub)

        layout.addSpacing(32)

        drop_hint = QLabel("將資料夾拖放到此處")
        drop_hint.setAlignment(Qt.AlignCenter)
        drop_hint.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px;"
            f" border: 1px dashed #333; border-radius:8px;"
            f" padding: 32px 64px;"
        )
        layout.addWidget(drop_hint)

        layout.addSpacing(16)

        self._btn = QPushButton("開啟資料夾")
        self._btn.setFixedWidth(160)
        self._btn.setFixedHeight(36)
        self._btn.setStyleSheet(
            f"background:{ACCENT}; color:white; border:none; border-radius:4px;"
            f" font-size:13px; font-weight:500;"
            f" QPushButton:hover {{ background:#ff8c3a; }}"
        )
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._on_open_folder)

        btn_wrapper = QWidget()
        bw = QVBoxLayout(btn_wrapper)
        bw.setContentsMargins(0, 0, 0, 0)
        bw.addWidget(self._btn, alignment=Qt.AlignCenter)
        layout.addWidget(btn_wrapper)

    def _on_open_folder(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "選擇照片資料夾")
        if folder:
            self.folder_selected.emit(folder)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.folder_selected.emit(path)
                break
