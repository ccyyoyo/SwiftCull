import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from app.ui.thumbnail_grid import ThumbnailGrid
from app.ui.filter_panel import FilterPanel
from app.utils.theme import BG_DEEP, BG_PANEL, TEXT_SECONDARY, TEXT_MUTED, ACCENT, BORDER

class _PreviewPane(QWidget):
    """Right-side large image preview for split mode."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setStyleSheet(f"background:{BG_DEEP};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setStyleSheet(f"background:{BG_DEEP};")
        layout.addWidget(self._img_label, stretch=1)
        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignCenter)
        self._info_label.setFixedHeight(24)
        self._info_label.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:10px; background:{BG_PANEL};"
            f" border-top:1px solid #2a2a2a;"
        )
        layout.addWidget(self._info_label)

    def show_photo(self, abs_path: str, filename: str):
        pix = QPixmap(abs_path)
        if not pix.isNull():
            pix = pix.scaled(
                self._img_label.width() or 800,
                (self._img_label.height() or 600) - 4,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._img_label.setPixmap(pix)
        self._info_label.setText(filename)

    def clear(self):
        self._img_label.clear()
        self._info_label.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # re-scale on resize if pixmap exists
        if self._img_label.pixmap() and not self._img_label.pixmap().isNull():
            pix = self._img_label.pixmap().scaled(
                self._img_label.width(), self._img_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._img_label.setPixmap(pix)


class GridView(QWidget):
    def __init__(self, folder_path, photo_repo, tag_repo,
                 thumb_svc, tag_svc, filter_svc, parent=None):
        super().__init__(parent)
        self._folder = folder_path
        self._photo_repo = photo_repo
        self._tag_repo = tag_repo
        self._thumb_svc = thumb_svc
        self._tag_svc = tag_svc
        self._filter_svc = filter_svc
        self._selected_ids: list[int] = []
        self._current_statuses = None
        self._current_colors = None
        self._split_mode = False

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # left filter panel
        self._filter_panel = FilterPanel()
        self._filter_panel.filter_changed.connect(self._on_filter_changed)
        root.addWidget(self._filter_panel)

        # center: toolbar + splitter
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # top toolbar for split toggle
        self._top_bar = QWidget()
        self._top_bar.setFixedHeight(36)
        self._top_bar.setStyleSheet(
            f"background:{BG_PANEL}; border-bottom:1px solid #2a2a2a;"
        )
        tb = QHBoxLayout(self._top_bar)
        tb.setContentsMargins(10, 0, 10, 0)
        tb.addStretch()
        self._split_btn = QPushButton("⊟  分割預覽")
        self._split_btn.setCheckable(True)
        self._split_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_SECONDARY}; border:1px solid #333;"
            f" border-radius:3px; padding:3px 10px; font-size:10px;"
            f" QPushButton:checked {{ background:{ACCENT}; color:white; border-color:{ACCENT}; }}"
        )
        self._split_btn.clicked.connect(self._toggle_split)
        tb.addWidget(self._split_btn)
        center_layout.addWidget(self._top_bar)

        # splitter: thumbnail grid | preview pane
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setStyleSheet(
            "QSplitter::handle { background: #2a2a2a; width: 2px; }"
        )

        self._grid = ThumbnailGrid()
        self._grid.photo_double_clicked.connect(self._on_loupe)
        self._grid.selection_changed.connect(self._on_selection_changed)
        self._grid.batch_status_requested.connect(self._on_batch_status)
        self._splitter.addWidget(self._grid)

        self._preview = _PreviewPane()
        self._preview.hide()
        self._splitter.addWidget(self._preview)

        center_layout.addWidget(self._splitter, stretch=1)
        root.addWidget(center, stretch=1)

        self._refresh()

    def _toggle_split(self, checked: bool):
        self._split_mode = checked
        if checked:
            self._preview.show()
            total = self._splitter.width()
            self._splitter.setSizes([int(total * 0.35), int(total * 0.65)])
            self._split_btn.setText("⊠  關閉預覽")
        else:
            self._preview.hide()
            self._preview.clear()
            self._split_btn.setText("⊟  分割預覽")

    def _refresh(self, statuses=None, colors=None):
        self._current_statuses = statuses
        self._current_colors = colors
        photos = self._filter_svc.filter(statuses=statuses, colors=colors)
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)

    def _on_filter_changed(self, statuses, colors):
        self._refresh(statuses or None, colors or None)

    def _on_selection_changed(self, ids: list):
        self._selected_ids = ids
        # update preview pane if split mode and single selection
        if self._split_mode and len(ids) == 1:
            photo = self._photo_repo.get_by_id(ids[0])
            if photo:
                abs_path = os.path.join(self._folder, photo.relative_path)
                self._preview.show_photo(abs_path, photo.filename)
        elif self._split_mode and len(ids) == 0:
            self._preview.clear()

    def _on_batch_status(self, photo_ids: list, status: str):
        from app.ui.batch_confirm_dialog import confirm_batch
        if not photo_ids:
            return
        if len(photo_ids) > 1:
            if not confirm_batch(len(photo_ids), status, self):
                return
        self._tag_svc.batch_set_status(photo_ids, status)
        for pid in photo_ids:
            self._grid.update_item_tag(pid)

    def _on_loupe(self, photo_id: int):
        from app.ui.loupe_view import LoupeView
        photos = self._filter_svc.filter(
            statuses=self._current_statuses,
            colors=self._current_colors,
        )
        photo_ids = [p.id for p in photos]
        if photo_id not in photo_ids:
            return
        loupe = LoupeView(
            photo_ids, photo_ids.index(photo_id),
            self._folder, self._photo_repo,
            self._tag_repo, self._tag_svc
        )
        loupe.tag_changed.connect(self._grid.update_item_tag)
        loupe.showFullScreen()
        loupe.closed.connect(loupe.deleteLater)
