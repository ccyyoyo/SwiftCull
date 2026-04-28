from PySide6.QtWidgets import QWidget, QHBoxLayout
from app.ui.thumbnail_grid import ThumbnailGrid
from app.ui.filter_panel import FilterPanel

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
        self._selected_ids = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._filter_panel = FilterPanel()
        self._filter_panel.filter_changed.connect(self._on_filter_changed)
        layout.addWidget(self._filter_panel)

        self._grid = ThumbnailGrid()
        self._grid.photo_double_clicked.connect(self._on_loupe)
        self._grid.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self._grid, stretch=1)

        self._refresh()

    def _refresh(self, statuses=None, colors=None):
        photos = self._filter_svc.filter(statuses=statuses, colors=colors)
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)

    def _on_filter_changed(self, statuses, colors):
        self._refresh(statuses or None, colors or None)

    def _on_selection_changed(self, ids):
        self._selected_ids = ids

    def _on_loupe(self, photo_id: int):
        from app.ui.loupe_view import LoupeView
        photos = self._filter_svc.filter()
        photo_ids = [p.id for p in photos]
        if photo_id not in photo_ids:
            return
        loupe = LoupeView(
            photo_ids, photo_ids.index(photo_id),
            self._folder, self._photo_repo,
            self._tag_repo, self._tag_svc
        )
        loupe.showFullScreen()
        loupe.closed.connect(loupe.deleteLater)
