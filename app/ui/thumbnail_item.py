from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen
from PySide6.QtCore import Signal, Qt, QRect
from app.utils.theme import (
    BG_ITEM, BORDER, BORDER_SEL,
    STATUS_ICON, STATUS_COLOR, COLOR_DOT,
    TEXT_SECONDARY,
)

class ThumbnailItem(QWidget):
    double_clicked = Signal(int)
    selection_changed = Signal(int, str)   # modifier: 'ctrl'|'shift'|'none'

    def __init__(self, photo_id: int, filename: str, thumb_path: str,
                 status=None, color=None, size=128, parent=None):
        super().__init__(parent)
        self.photo_id = photo_id
        self._selected = False
        self._hovered = False
        self._status = status
        self._color = color
        self._size = size
        self._filename = filename
        self._pixmap = None

        # compact: no extra margin, image fills cell
        self.setFixedSize(size + 4, size + 4)
        self.setMouseTracking(True)

        if thumb_path:
            pix = QPixmap(thumb_path)
            if not pix.isNull():
                self._pixmap = pix.scaled(
                    size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_status(self, status):
        self._status = status
        self.update()

    def set_color(self, color):
        self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # background
        p.fillRect(0, 0, w, h, QColor(BG_ITEM))

        # image centered
        if self._pixmap:
            img_w = self._pixmap.width()
            img_h = self._pixmap.height()
            x = (w - img_w) // 2
            y = (h - img_h) // 2
            p.drawPixmap(x, y, self._pixmap)

        # hover: filename overlay at bottom
        if self._hovered or self._selected:
            overlay = QColor(0, 0, 0, 160)
            p.fillRect(0, h - 22, w, 22, overlay)
            p.setPen(QColor("#cccccc"))
            font = QFont("Segoe UI", 8)
            p.setFont(font)
            p.drawText(QRect(4, h - 22, w - 8, 20), Qt.AlignVCenter | Qt.AlignLeft,
                       self._filename)

        # status badge — bottom-right circle with icon
        if self._status and self._status in STATUS_ICON:
            badge_r = 10
            bx = w - badge_r - 4
            by = 4
            p.setBrush(QColor(STATUS_COLOR[self._status]))
            p.setPen(Qt.NoPen)
            p.drawEllipse(bx, by, badge_r * 2, badge_r * 2)
            p.setPen(QColor("#000000"))
            font = QFont("Segoe UI", 8, QFont.Bold)
            p.setFont(font)
            p.drawText(QRect(bx, by, badge_r * 2, badge_r * 2),
                       Qt.AlignCenter, STATUS_ICON[self._status])

        # color dot — bottom-left
        if self._color and self._color in COLOR_DOT:
            p.setBrush(QColor(COLOR_DOT[self._color]))
            p.setPen(Qt.NoPen)
            p.drawEllipse(4, 4, 10, 10)

        # selection border
        if self._selected:
            pen = QPen(QColor(BORDER_SEL), 3)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(1, 1, w - 3, h - 3)
        elif self._hovered:
            pen = QPen(QColor("#555555"), 1)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(0, 0, w - 1, h - 1)

        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

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
