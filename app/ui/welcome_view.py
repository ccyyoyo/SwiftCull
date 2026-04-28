import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt

class WelcomeView(QWidget):
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("SwiftCull")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: bold;")

        desc = QLabel("拖放照片資料夾，或點擊下方按鈕開始")
        desc.setAlignment(Qt.AlignCenter)

        self._btn = QPushButton("開啟資料夾")
        self._btn.setFixedWidth(200)
        self._btn.clicked.connect(self._on_open_folder)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(self._btn)

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
