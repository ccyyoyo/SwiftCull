import os
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from PySide6.QtGui import QPixmap, QKeyEvent
from PySide6.QtCore import Signal, Qt

class LoupeView(QWidget):
    closed = Signal()

    def __init__(self, photo_ids, current_index, folder_path,
                 photo_repo, tag_repo, tag_svc, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        self._ids = photo_ids
        self._idx = current_index
        self._folder = folder_path
        self._photo_repo = photo_repo
        self._tag_repo = tag_repo
        self._tag_svc = tag_svc

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setStyleSheet("background: black;")
        layout.addWidget(self._img_label, stretch=1)

        self._toolbar = QWidget()
        self._toolbar.setStyleSheet("background: rgba(0,0,0,180); color: white;")
        tb_layout = QHBoxLayout(self._toolbar)
        for label, status in [("P  Pick", "pick"), ("R  Reject", "reject"), ("M  Maybe", "maybe")]:
            btn = QPushButton(label)
            btn.setStyleSheet("color: white; background: #333; padding: 6px 16px;")
            btn.clicked.connect(lambda checked, s=status: self._set_status(s))
            tb_layout.addWidget(btn)
        tb_layout.addStretch()
        close_btn = QPushButton("關閉 (Esc)")
        close_btn.setStyleSheet("color: white; background: #555; padding: 6px 16px;")
        close_btn.clicked.connect(self.close)
        tb_layout.addWidget(close_btn)
        layout.addWidget(self._toolbar)

        self._load_current()

    def _load_current(self):
        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        abs_path = os.path.join(self._folder, photo.relative_path)
        pix = QPixmap(abs_path)
        if not pix.isNull():
            screen = self.screen()
            if screen:
                geo = screen.geometry()
                pix = pix.scaled(geo.width(), geo.height() - 60,
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img_label.setPixmap(pix)

    def _set_status(self, status: str):
        photo_id = self._ids[self._idx]
        self._tag_svc.set_status(photo_id, status)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_P:
            self._set_status("pick")
        elif key == Qt.Key_R:
            self._set_status("reject")
        elif key == Qt.Key_M:
            self._set_status("maybe")
        elif key == Qt.Key_Left and self._idx > 0:
            self._idx -= 1
            self._load_current()
        elif key == Qt.Key_Right and self._idx < len(self._ids) - 1:
            self._idx += 1
            self._load_current()
        elif key == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
