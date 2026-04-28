import os
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QApplication
)
from PySide6.QtGui import QPixmap, QKeyEvent
from PySide6.QtCore import Signal, Qt, QTimer, QPoint

COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]
COLOR_HEX = {
    "red": "#FF4444", "orange": "#FF8800", "yellow": "#FFDD00",
    "green": "#44AA44", "blue": "#4488FF", "purple": "#AA44FF",
}

class LoupeView(QWidget):
    closed = Signal()
    tag_changed = Signal(int)   # emitted with photo_id when status/color changes

    def __init__(self, photo_ids, current_index, folder_path,
                 photo_repo, tag_repo, tag_svc, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        self.setMouseTracking(True)
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
        self._img_label.setMouseTracking(True)
        layout.addWidget(self._img_label, stretch=1)

        # --- status indicator ---
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "color: white; font-size: 18px; font-weight: bold;"
            " background: transparent; padding: 4px;"
        )
        self._status_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        # overlay it on top-left using absolute positioning
        self._status_label.setParent(self)
        self._status_label.move(16, 16)
        self._status_label.resize(200, 36)
        self._status_label.raise_()

        # --- bottom toolbar (auto-hide) ---
        self._toolbar = QWidget(self)
        self._toolbar.setStyleSheet("background: rgba(0,0,0,200); color: white;")
        self._toolbar.setMouseTracking(True)
        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)

        for label, status in [("P  Pick", "pick"), ("R  Reject", "reject"), ("M  Maybe", "maybe")]:
            btn = QPushButton(label)
            btn.setStyleSheet("color: white; background: #333; padding: 6px 16px;")
            btn.clicked.connect(lambda checked, s=status: self._set_status(s))
            tb_layout.addWidget(btn)

        tb_layout.addSpacing(16)

        # color buttons
        for c in COLORS:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"background: {COLOR_HEX[c]}; border-radius: 4px;")
            btn.setToolTip(c)
            btn.clicked.connect(lambda checked, col=c: self._set_color(col))
            tb_layout.addWidget(btn)

        # clear color
        clear_color_btn = QPushButton("✕ 顏色")
        clear_color_btn.setStyleSheet("color: white; background: #444; padding: 4px 8px;")
        clear_color_btn.clicked.connect(lambda: self._set_color(None))
        tb_layout.addWidget(clear_color_btn)

        tb_layout.addStretch()
        close_btn = QPushButton("關閉 (Esc)")
        close_btn.setStyleSheet("color: white; background: #555; padding: 6px 16px;")
        close_btn.clicked.connect(self.close)
        tb_layout.addWidget(close_btn)

        # auto-hide timer
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(2000)
        self._hide_timer.timeout.connect(self._hide_toolbar)
        self._toolbar_visible = True

        self._load_current()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toolbar()

    def _position_toolbar(self):
        h = 56
        self._toolbar.setGeometry(0, self.height() - h, self.width(), h)

    def showEvent(self, event):
        super().showEvent(event)
        self._position_toolbar()
        self._toolbar.show()
        self._hide_timer.start()

    def _show_toolbar(self):
        self._toolbar.show()
        self._toolbar_visible = True
        self._hide_timer.start()

    def _hide_toolbar(self):
        self._toolbar.hide()
        self._toolbar_visible = False

    def mouseMoveEvent(self, event):
        # show toolbar when mouse near bottom
        if event.pos().y() > self.height() - 80:
            self._show_toolbar()
        super().mouseMoveEvent(event)

    def _load_current(self):
        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        abs_path = os.path.join(self._folder, photo.relative_path)
        pix = QPixmap(abs_path)
        screen = QApplication.primaryScreen()
        if not pix.isNull() and screen:
            geo = screen.geometry()
            pix = pix.scaled(geo.width(), geo.height() - 60,
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img_label.setPixmap(pix)
        self._update_status_label()

    def _update_status_label(self):
        photo_id = self._ids[self._idx]
        tag = self._tag_repo.get_by_photo_id(photo_id)
        status = tag.status if tag else None
        color = tag.color if tag else None
        status_text = {"pick": "✓ Pick", "reject": "✕ Reject", "maybe": "? Maybe"}.get(status, "")
        color_dot = f" ●" if color else ""
        self._status_label.setText(status_text + color_dot)
        if color:
            self._status_label.setStyleSheet(
                f"color: {COLOR_HEX.get(color, 'white')}; font-size: 18px;"
                f" font-weight: bold; background: transparent; padding: 4px;"
            )
        else:
            self._status_label.setStyleSheet(
                "color: white; font-size: 18px; font-weight: bold;"
                " background: transparent; padding: 4px;"
            )

    def _set_status(self, status: str):
        photo_id = self._ids[self._idx]
        self._tag_svc.set_status(photo_id, status)
        self._update_status_label()
        self.tag_changed.emit(photo_id)

    def _set_color(self, color):
        photo_id = self._ids[self._idx]
        self._tag_svc.set_color(photo_id, color)
        self._update_status_label()
        self.tag_changed.emit(photo_id)

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
        else:
            self._show_toolbar()

    def closeEvent(self, event):
        self._hide_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
