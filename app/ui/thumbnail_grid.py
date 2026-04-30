import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QGridLayout, QSlider
)
from PySide6.QtCore import (
    Signal, Qt, QObject, QRunnable, QThreadPool, QTimer
)
from PySide6.QtGui import QPixmap
from app.ui.thumbnail_item import ThumbnailItem
from app.utils.theme import BG_MAIN, BG_PANEL, TEXT_SECONDARY

_SNAP_SIZES = [100, 160, 240]


class _ThumbSignals(QObject):
    ready = Signal(int, str)
    failed = Signal(int)


class _ThumbRunnable(QRunnable):
    def __init__(self, photo_id: int, abs_path: str, size: int,
                 thumb_svc, signals: _ThumbSignals):
        super().__init__()
        self._photo_id = photo_id
        self._abs_path = abs_path
        self._size = size
        self._svc = thumb_svc
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            cache_path = self._svc.get_thumbnail(self._abs_path, self._size)
            self._signals.ready.emit(self._photo_id, cache_path)
        except Exception:
            self._signals.failed.emit(self._photo_id)


class ThumbnailGrid(QWidget):
    photo_double_clicked = Signal(int)
    selection_changed = Signal(list)
    batch_status_requested = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_size = 160
        self._items: dict[int, ThumbnailItem] = {}
        self._photos: list = []
        self._photo_by_id: dict[int, object] = {}
        self._selected: set[int] = set()
        self._last_clicked_idx: int = -1
        self._tag_repo = None
        self._thumb_svc = None
        self._folder_path = ""
        self._cols = 1

        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(max(2, min(8, os.cpu_count() or 4)))
        self._signals = _ThumbSignals()
        self._signals.ready.connect(self._on_thumb_ready)
        self._signals.failed.connect(self._on_thumb_failed)

        self._scroll_debounce = QTimer(self)
        self._scroll_debounce.setSingleShot(True)
        self._scroll_debounce.setInterval(40)
        self._scroll_debounce.timeout.connect(self._request_visible_thumbnails)

        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar_widget = QWidget()
        toolbar_widget.setFixedHeight(36)
        toolbar_widget.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid #2a2a2a;")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(10, 0, 10, 0)

        size_lbl = QLabel("SIZE")
        size_lbl.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px; letter-spacing:1px;")
        toolbar.addWidget(size_lbl)

        self._size_slider = QSlider(Qt.Horizontal)
        self._size_slider.setRange(0, 2)
        self._size_slider.setValue(1)
        self._size_slider.setTickPosition(QSlider.TicksBelow)
        self._size_slider.setTickInterval(1)
        self._size_slider.setFixedWidth(72)
        self._size_slider.valueChanged.connect(self._on_slider)
        toolbar.addWidget(self._size_slider)

        self._size_lbl = QLabel("M")
        self._size_lbl.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px; min-width:12px;")
        toolbar.addWidget(self._size_lbl)
        toolbar.addStretch()

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px;")
        toolbar.addWidget(self._count_lbl)
        root.addWidget(toolbar_widget)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._container.setStyleSheet(f"background:{BG_MAIN};")
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(2)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._container.setLayout(self._grid)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

        self._scroll.verticalScrollBar().valueChanged.connect(
            lambda _: self._scroll_debounce.start()
        )

    def load_photos(self, photos, tag_repo, thumb_svc, folder_path: str):
        self._photos = list(photos)
        self._photo_by_id = {p.id: p for p in self._photos}
        self._tag_repo = tag_repo
        self._thumb_svc = thumb_svc
        self._folder_path = folder_path
        self._selected.clear()
        self._last_clicked_idx = -1
        self._rebuild_grid()
        self.selection_changed.emit([])
        self._update_count()
        self._scroll_debounce.start()

    def add_photo(self, photo):
        if photo.id in self._items:
            return
        self._photos.append(photo)
        self._photo_by_id[photo.id] = photo
        idx = len(self._photos) - 1
        cols = self._cols if self._cols > 0 else 1
        item = self._make_item(photo)
        self._items[photo.id] = item
        self._grid.addWidget(item, idx // cols, idx % cols)
        self._update_count()
        self._scroll_debounce.start()

    def _make_item(self, photo) -> ThumbnailItem:
        tag = self._tag_repo.get_by_photo_id(photo.id) if self._tag_repo else None
        item = ThumbnailItem(
            photo.id, photo.filename,
            status=tag.status if tag else None,
            color=tag.color if tag else None,
            size=self._thumb_size,
        )
        item.double_clicked.connect(self.photo_double_clicked)
        item.selection_changed.connect(self._on_item_selection)
        if photo.id in self._selected:
            item.set_selected(True)
        return item

    def _rebuild_grid(self):
        while self._grid.count():
            it = self._grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._items.clear()

        cols = max(1, (self._scroll.viewport().width() or 800) // (self._thumb_size + 6))
        self._cols = cols
        for idx, photo in enumerate(self._photos):
            item = self._make_item(photo)
            self._items[photo.id] = item
            self._grid.addWidget(item, idx // cols, idx % cols)

    def _update_count(self):
        n = len(self._photos)
        self._count_lbl.setText(f"{n} photo{'s' if n != 1 else ''}")

    def update_item_tag(self, photo_id: int):
        if photo_id not in self._items or self._tag_repo is None:
            return
        tag = self._tag_repo.get_by_photo_id(photo_id)
        self._items[photo_id].set_status(tag.status if tag else None)
        self._items[photo_id].set_color(tag.color if tag else None)

    def refresh_item_thumbnail(self, photo_id: int):
        """Force re-fetch of a single tile's thumbnail (e.g. after modify)."""
        item = self._items.get(photo_id)
        if item is None:
            return
        item.reset_thumb()
        self._scroll_debounce.start()

    def _on_item_selection(self, photo_id: int, modifier: str):
        photo_ids = [p.id for p in self._photos]
        clicked_idx = photo_ids.index(photo_id) if photo_id in photo_ids else -1

        if modifier == "shift" and self._last_clicked_idx >= 0 and clicked_idx >= 0:
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
            for pid, item in self._items.items():
                item.set_selected(False)
            self._selected.clear()
            self._selected.add(photo_id)
            self._items[photo_id].set_selected(True)
            self._last_clicked_idx = clicked_idx

        self.selection_changed.emit(list(self._selected))

    def _on_slider(self, value: int):
        self._thumb_size = _SNAP_SIZES[value]
        self._size_lbl.setText(["S", "M", "L"][value])
        if self._tag_repo is not None:
            self._rebuild_grid()
            self._scroll_debounce.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._photos:
            new_cols = max(1, (self._scroll.viewport().width() or 800) // (self._thumb_size + 6))
            if new_cols != self._cols:
                self._cols = new_cols
                self._reflow()
        self._scroll_debounce.start()

    def _reflow(self):
        cols = self._cols
        for idx, photo in enumerate(self._photos):
            item = self._items.get(photo.id)
            if not item:
                continue
            self._grid.removeWidget(item)
            self._grid.addWidget(item, idx // cols, idx % cols)

    def _request_visible_thumbnails(self):
        if not self._items or self._thumb_svc is None:
            return
        scroll_y = self._scroll.verticalScrollBar().value()
        viewport_h = self._scroll.viewport().height()
        margin = self._thumb_size * 2
        visible_top = scroll_y - margin
        visible_bottom = scroll_y + viewport_h + margin

        for photo_id, item in self._items.items():
            if item.has_thumbnail() or item.is_thumb_requested():
                continue
            item_top = item.y()
            item_bottom = item_top + item.height()
            if item_bottom < visible_top or item_top > visible_bottom:
                continue
            photo = self._photo_by_id.get(photo_id)
            if not photo:
                continue
            item.mark_thumb_requested()
            abs_path = os.path.join(self._folder_path, photo.relative_path)
            runnable = _ThumbRunnable(
                photo_id, abs_path, self._thumb_size,
                self._thumb_svc, self._signals,
            )
            self._pool.start(runnable)

    def _on_thumb_ready(self, photo_id: int, cache_path: str):
        item = self._items.get(photo_id)
        if not item:
            return
        pix = QPixmap(cache_path)
        if not pix.isNull():
            item.set_thumbnail_pixmap(pix)

    def _on_thumb_failed(self, photo_id: int):
        pass

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
        if key == Qt.Key_Space and len(self._selected) == 1:
            self.photo_double_clicked.emit(list(self._selected)[0])
            return
        super().keyPressEvent(event)
