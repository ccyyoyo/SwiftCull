from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtCore import Signal, Qt

STATUS_COLORS = {
    "pick": QColor("#00CC00"),
    "reject": QColor("#CC0000"),
    "maybe": QColor("#FFAA00"),
}
COLOR_MAP = {
    "red": "#FF4444", "orange": "#FF8800", "yellow": "#FFDD00",
    "green": "#44AA44", "blue": "#4488FF", "purple": "#AA44FF",
}

class ThumbnailItem(QWidget):
    double_clicked = Signal(int)
    # modifier: 'ctrl', 'shift', or 'none'
    selection_changed = Signal(int, str)

    def __init__(self, photo_id: int, filename: str, thumb_path: str,
                 status=None, color=None, size=128, parent=None):
        super().__init__(parent)
        self.photo_id = photo_id
        self._selected = False
        self._status = status
        self._color = color
        self._size = size
        self.setFixedSize(size + 8, size + 28)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setFixedSize(size, size)

        if thumb_path:
            pix = QPixmap(thumb_path)
            if not pix.isNull():
                self._img_label.setPixmap(
                    pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        self._name_label = QLabel(filename)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setMaximumWidth(size)
        self._name_label.setStyleSheet("font-size: 10px;")

        layout.addWidget(self._img_label)
        layout.addWidget(self._name_label)
        self._update_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def set_status(self, status):
        self._status = status
        self._update_style()

    def set_color(self, color):
        self._color = color
        self._update_style()

    def _update_style(self):
        border = "3px solid #4488FF" if self._selected else "1px solid #555"
        self.setStyleSheet(f"ThumbnailItem {{ border: {border}; border-radius: 3px; }}")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self._status and self._status in STATUS_COLORS:
            painter.setBrush(STATUS_COLORS[self._status])
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.width() - 16, 4, 12, 12)
        if self._color and self._color in COLOR_MAP:
            painter.setBrush(QColor(COLOR_MAP[self._color]))
            painter.setPen(Qt.NoPen)
            painter.drawRect(4, 4, 10, 10)
        painter.end()

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.photo_id)

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier:
            modifier = "shift"
        elif event.modifiers() & Qt.ControlModifier:
            modifier = "ctrl"
        else:
            modifier = "none"
        self.selection_changed.emit(self.photo_id, modifier)
