import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QGridLayout, QPushButton, QSlider
)
from PySide6.QtCore import Signal, Qt
from app.ui.thumbnail_item import ThumbnailItem

# Three snap points: small=100, medium=160, large=240
_SNAP_SIZES = [100, 160, 240]

def _snap(value: int) -> int:
    return min(_SNAP_SIZES, key=lambda s: abs(s - value))

class ThumbnailGrid(QWidget):
    photo_double_clicked = Signal(int)
    selection_changed = Signal(list)
    batch_status_requested = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_size = 160
        self._items: dict[int, ThumbnailItem] = {}
        self._photos = []
        self._selected: set[int] = set()
        self._last_clicked_idx: int = -1
        self._tag_repo = None
        self._thumb_svc = None
        self._folder_path = ""
        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("縮圖"))
        # slider spans 0-2, maps to _SNAP_SIZES
        self._size_slider = QSlider(Qt.Horizontal)
        self._size_slider.setRange(0, 2)
        self._size_slider.setValue(1)          # default: 中
        self._size_slider.setTickPosition(QSlider.TicksBelow)
        self._size_slider.setTickInterval(1)
        self._size_slider.setFixedWidth(80)
        self._size_slider.valueChanged.connect(self._on_slider)
        toolbar.addWidget(self._size_slider)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(4)
        self._container.setLayout(self._grid)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

    def load_photos(self, photos, tag_repo, thumb_svc, folder_path: str):
        self._photos = photos
        self._tag_repo = tag_repo
        self._thumb_svc = thumb_svc
        self._folder_path = folder_path
        self._selected.clear()
        self._last_clicked_idx = -1
        self._rebuild_grid()
        self.selection_changed.emit([])

    def _rebuild_grid(self):
        # clear existing widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._items.clear()

        cols = max(1, (self._scroll.viewport().width() or 800) // (self._thumb_size + 12))
        for idx, photo in enumerate(self._photos):
            tag = self._tag_repo.get_by_photo_id(photo.id) if self._tag_repo else None
            abs_path = os.path.join(self._folder_path, photo.relative_path)
            try:
                thumb_path = self._thumb_svc.get_thumbnail(abs_path, self._thumb_size)
            except Exception:
                thumb_path = ""

            item = ThumbnailItem(
                photo.id, photo.filename, thumb_path,
                status=tag.status if tag else None,
                color=tag.color if tag else None,
                size=self._thumb_size,
            )
            item.double_clicked.connect(self.photo_double_clicked)
            item.selection_changed.connect(self._on_item_selection)
            if photo.id in self._selected:
                item.set_selected(True)
            self._items[photo.id] = item
            self._grid.addWidget(item, idx // cols, idx % cols)

    def update_item_tag(self, photo_id: int):
        """Refresh one thumbnail's status/color after tagging."""
        if photo_id not in self._items or self._tag_repo is None:
            return
        tag = self._tag_repo.get_by_photo_id(photo_id)
        self._items[photo_id].set_status(tag.status if tag else None)
        self._items[photo_id].set_color(tag.color if tag else None)

    def _on_item_selection(self, photo_id: int, modifier: str):
        """modifier: 'ctrl', 'shift', or 'none'"""
        photo_ids = [p.id for p in self._photos]
        clicked_idx = photo_ids.index(photo_id) if photo_id in photo_ids else -1

        if modifier == "shift" and self._last_clicked_idx >= 0 and clicked_idx >= 0:
            # range select
            lo = min(self._last_clicked_idx, clicked_idx)
            hi = max(self._last_clicked_idx, clicked_idx)
            for i in range(lo, hi + 1):
                pid = photo_ids[i]
                self._selected.add(pid)
                self._items[pid].set_selected(True)
        elif modifier == "ctrl":
            if photo_id in self._selected:
                self._selected.discard(photo_id)
                self._items[photo_id].set_selected(False)
            else:
                self._selected.add(photo_id)
                self._items[photo_id].set_selected(True)
            self._last_clicked_idx = clicked_idx
        else:
            # single click — clear others
            for pid, item in self._items.items():
                item.set_selected(False)
            self._selected.clear()
            self._selected.add(photo_id)
            self._items[photo_id].set_selected(True)
            self._last_clicked_idx = clicked_idx

        self.selection_changed.emit(list(self._selected))

    def _on_slider(self, value: int):
        self._thumb_size = _SNAP_SIZES[value]
        if self._tag_repo is not None:
            self._rebuild_grid()

    def keyPressEvent(self, event):
        key = event.key()
        if self._selected:
            selected_list = list(self._selected)
            if key == Qt.Key_P:
                self.batch_status_requested.emit(selected_list, "pick")
                return
            elif key == Qt.Key_R:
                self.batch_status_requested.emit(selected_list, "reject")
                return
            elif key == Qt.Key_M:
                self.batch_status_requested.emit(selected_list, "maybe")
                return
        # Space: open loupe on focused/single selected item
        if key == Qt.Key_Space and len(self._selected) == 1:
            self.photo_double_clicked.emit(list(self._selected)[0])
            return
        super().keyPressEvent(event)
