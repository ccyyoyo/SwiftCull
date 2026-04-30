from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen
from PySide6.QtCore import Signal, Qt, QRect
from app.utils.theme import (
    BG_ITEM, BORDER, BORDER_SEL,
    STATUS_ICON, STATUS_COLOR, COLOR_DOT,
    TEXT_SECONDARY,
)

class ThumbnailItem(QWidget):
    double_clicked = Signal(int)
    selection_changed = Signal(int, str)

    def __init__(self, photo_id: int, filename: str,
                 status=None, color=None, size=128, parent=None):
        super().__init__(parent)
        self.photo_id = photo_id
        self._selected = False
        self._hovered = False
        self._status = status
        self._color = color
        self._size = size
        self._filename = filename
        self._pixmap: QPixmap | None = None
        self._thumb_requested = False
        self._missing = False

        self._label_h = 20
        self.setFixedSize(size + 4, size + 4 + self._label_h)
        self.setMouseTracking(True)

    def has_thumbnail(self) -> bool:
        return self._pixmap is not None

    def is_thumb_requested(self) -> bool:
        return self._thumb_requested

    def mark_thumb_requested(self):
        self._thumb_requested = True

    def reset_thumb(self):
        self._pixmap = None
        self._thumb_requested = False
        self.update()

    def set_thumbnail_pixmap(self, pix: QPixmap):
        if pix is None or pix.isNull():
            return
        self._pixmap = pix.scaled(
            self._size, self._size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_status(self, status):
        self._status = status
        self.update()

    def set_color(self, color):
        self._color = color
        self.update()

    def set_missing(self, missing: bool):
        if self._missing == missing:
            return
        self._missing = missing
        if missing:
            self.setToolTip("原檔不存在")
        else:
            self.setToolTip("")
        self.update()

    def is_missing(self) -> bool:
        return self._missing

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_ITEM))

        img_zone_h = h - self._label_h
        if self._pixmap:
            img_w = self._pixmap.width()
            img_h = self._pixmap.height()
            x = (w - img_w) // 2
            y = (img_zone_h - img_h) // 2
            p.drawPixmap(x, y, self._pixmap)
        else:
            placeholder = QColor("#1a1a1a")
            p.fillRect(2, 2, w - 4, img_zone_h - 4, placeholder)
            p.setPen(QColor("#3a3a3a"))
            p.setFont(QFont("Segoe UI", 16))
            p.drawText(QRect(0, 0, w, img_zone_h),
                       Qt.AlignCenter, "·")

        # missing-file dim overlay sits *above* the thumbnail but *below*
        # the filename row so the name stays legible.
        if self._missing:
            p.fillRect(2, 2, w - 4, img_zone_h - 4, QColor(0, 0, 0, 140))

        # filename label area at bottom — always visible
        p.fillRect(0, img_zone_h, w, self._label_h, QColor(0, 0, 0, 180))
        label_color = "#777777" if self._missing else "#aaaaaa"
        p.setPen(QColor(label_color))
        font = QFont("Segoe UI", 8)
        p.setFont(font)
        p.drawText(QRect(4, img_zone_h, w - 8, self._label_h),
                   Qt.AlignVCenter | Qt.AlignLeft, self._filename)

        # missing badge — a small red pill across the top edge
        if self._missing:
            badge_h = 18
            badge_w = min(74, w - 12)
            bx = (w - badge_w) // 2
            by = max(4, img_zone_h // 2 - badge_h // 2)
            p.setBrush(QColor(170, 50, 50, 220))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(bx, by, badge_w, badge_h, 4, 4)
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.drawText(QRect(bx, by, badge_w, badge_h),
                       Qt.AlignCenter, "✕ 找不到原檔")

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
