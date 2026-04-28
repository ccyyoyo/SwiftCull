from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QSlider, QLabel, QGridLayout
)
from PySide6.QtCore import Signal, Qt
from app.ui.thumbnail_item import ThumbnailItem

class ThumbnailGrid(QWidget):
    photo_double_clicked = Signal(int)
    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_size = 160
        self._items: dict[int, ThumbnailItem] = {}
        self._selected: set[int] = set()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self._size_slider = QSlider(Qt.Horizontal)
        self._size_slider.setRange(80, 320)
        self._size_slider.setValue(self._thumb_size)
        self._size_slider.setMaximumWidth(200)
        self._size_slider.valueChanged.connect(self._on_size_changed)
        toolbar.addWidget(QLabel("縮圖大小"))
        toolbar.addWidget(self._size_slider)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(4)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

    def load_photos(self, photos, tag_repo, thumb_svc, folder_path: str):
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._items.clear()
        self._selected.clear()

        cols = max(1, (self._scroll.width() or 800) // (self._thumb_size + 12))
        for idx, photo in enumerate(photos):
            import os
            tag = tag_repo.get_by_photo_id(photo.id)
            abs_path = os.path.join(folder_path, photo.relative_path)
            try:
                thumb_path = thumb_svc.get_thumbnail(abs_path, self._thumb_size)
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
            self._items[photo.id] = item
            self._grid.addWidget(item, idx // cols, idx % cols)

    def _on_item_selection(self, photo_id: int, multi: bool):
        if not multi:
            for pid, item in self._items.items():
                item.set_selected(False)
            self._selected.clear()
        if photo_id in self._selected:
            self._selected.discard(photo_id)
            self._items[photo_id].set_selected(False)
        else:
            self._selected.add(photo_id)
            self._items[photo_id].set_selected(True)
        self.selection_changed.emit(list(self._selected))

    def _on_size_changed(self, value: int):
        self._thumb_size = value
