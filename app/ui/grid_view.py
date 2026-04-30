import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QLabel, QPushButton, QSizePolicy, QProgressBar
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, Signal
from app.ui.thumbnail_grid import ThumbnailGrid
from app.ui.filter_panel import FilterPanel
from app.utils.theme import (
    BG_DEEP, BG_PANEL, TEXT_SECONDARY, TEXT_MUTED, ACCENT, BORDER, REJECT_CLR
)

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
    refresh_requested = Signal()

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
        self._import_errors: list[tuple[str, str]] = []

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

        self._top_bar = QWidget()
        self._top_bar.setFixedHeight(36)
        self._top_bar.setStyleSheet(
            f"background:{BG_PANEL}; border-bottom:1px solid #2a2a2a;"
        )
        tb = QHBoxLayout(self._top_bar)
        tb.setContentsMargins(10, 0, 10, 0)

        self._import_label = QLabel("")
        self._import_label.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:10px;"
        )
        self._import_label.hide()
        tb.addWidget(self._import_label)
        tb.addStretch()

        self._import_progress = QProgressBar()
        self._import_progress.setFixedWidth(220)
        self._import_progress.setFixedHeight(14)
        self._import_progress.setTextVisible(False)
        self._import_progress.setStyleSheet(
            f"QProgressBar {{ background:#1e1e1e; border:1px solid #2a2a2a;"
            f" border-radius:3px; }}"
            f"QProgressBar::chunk {{ background:{ACCENT}; border-radius:2px; }}"
        )
        self._import_progress.hide()
        tb.addWidget(self._import_progress)

        self._refresh_btn = QPushButton("↻  重新掃描")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setToolTip("重新掃描資料夾，找出新增 / 修改的檔案")
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
            f" border:1px solid #333; border-radius:3px; padding:3px 10px;"
            f" font-size:10px; }}"
            f"QPushButton:hover:!disabled {{ background:#2a2a2a; color:#ddd;"
            f" border-color:#555; }}"
            f"QPushButton:disabled {{ color:{TEXT_MUTED}; border-color:#222; }}"
        )
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        tb.addWidget(self._refresh_btn)

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

        self._status_bar = QWidget()
        self._status_bar.setFixedHeight(22)
        self._status_bar.setStyleSheet(
            f"background:{BG_PANEL}; border-top:1px solid #2a2a2a;"
        )
        sb = QHBoxLayout(self._status_bar)
        sb.setContentsMargins(10, 0, 10, 0)
        sb.setSpacing(8)
        sb.addStretch()
        self._error_btn = QPushButton("")
        self._error_btn.setCursor(Qt.PointingHandCursor)
        self._error_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{REJECT_CLR};"
            f" border:none; padding:0 4px; font-size:11px; }}"
            f"QPushButton:hover {{ color:#ff7777; }}"
        )
        self._error_btn.clicked.connect(self._show_error_list)
        self._error_btn.hide()
        sb.addWidget(self._error_btn)
        center_layout.addWidget(self._status_bar)

        root.addWidget(center, stretch=1)

        self._refresh()

    def _toggle_split(self, checked: bool):
        self._split_mode = checked
        if checked:
            self._preview.show()
            total = self._splitter.width()
            self._splitter.setSizes([int(total * 0.55), int(total * 0.45)])
            self._split_btn.setText("⊠  關閉預覽")
            # restore preview for currently selected photo
            if len(self._selected_ids) == 1:
                photo = self._photo_repo.get_by_id(self._selected_ids[0])
                if photo:
                    abs_path = os.path.join(self._folder, photo.relative_path)
                    self._preview.show_photo(abs_path, photo.filename)
        else:
            self._preview.hide()
            self._preview.clear()
            self._split_btn.setText("⊟  分割預覽")

    def _refresh(self, statuses=None, colors=None):
        self._current_statuses = statuses
        self._current_colors = colors
        photos = self._filter_svc.filter(statuses=statuses, colors=colors)
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)

    def begin_import(self, total: int):
        self._refresh_btn.setEnabled(False)
        self._import_progress.setRange(0, max(1, total))
        self._import_progress.setValue(0)
        self._import_progress.show()
        self._import_label.setText(f"匯入中 0 / {total}")
        self._import_label.show()

    def update_import_progress(self, current: int, total: int):
        self._import_progress.setRange(0, max(1, total))
        self._import_progress.setValue(current)
        self._import_label.setText(f"匯入中 {current} / {total}")

    def end_import(self):
        self._import_progress.hide()
        self._import_label.hide()
        self._refresh_btn.setEnabled(True)

    def scan_finished(self):
        """Called after a background scan completes regardless of outcome.
        Re-enables the refresh button if no import has taken its place."""
        if self._import_progress.isVisible():
            return  # an import is in flight; end_import will re-enable later
        self._refresh_btn.setEnabled(True)

    def _on_refresh_clicked(self):
        self._refresh_btn.setEnabled(False)
        self.clear_import_errors()
        self.refresh_requested.emit()

    def on_photo_imported(self, photo):
        if self._current_statuses or self._current_colors:
            return
        self._grid.add_photo(photo)

    def on_photo_updated(self, photo_id: int):
        """A modified file just had its metadata refreshed; force the
        thumbnail to regenerate from the new on-disk content."""
        self._grid.refresh_item_thumbnail(photo_id)

    def add_import_error(self, rel_path: str, reason: str):
        self._import_errors.append((rel_path, reason))
        self._refresh_error_indicator()

    def clear_import_errors(self):
        self._import_errors.clear()
        self._refresh_error_indicator()

    def _refresh_error_indicator(self):
        n = len(self._import_errors)
        if n == 0:
            self._error_btn.hide()
            return
        self._error_btn.setText(f"⚠  {n} 個檔案讀取失敗")
        self._error_btn.show()

    def _show_error_list(self):
        from app.ui.error_list_dialog import ErrorListDialog
        if not self._import_errors:
            return
        ErrorListDialog(self._import_errors, self).exec()

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
        if status == "clear":
            self._tag_svc.batch_clear_status(photo_ids)
        else:
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
