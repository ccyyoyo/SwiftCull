import os
import logging
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

log = logging.getLogger(__name__)

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
    import_cancel_requested = Signal()

    def __init__(self, folder_path, photo_repo, tag_repo,
                 thumb_svc, tag_svc, filter_svc, settings, parent=None):
        log.info("GridView.__init__ starting")
        super().__init__(parent)
        self._folder = folder_path
        self._photo_repo = photo_repo
        self._tag_repo = tag_repo
        self._thumb_svc = thumb_svc
        self._tag_svc = tag_svc
        self._filter_svc = filter_svc
        self._settings = settings  # SettingsDB instance
        self._current_blur = None
        self._blur_ctrl = None
        self._db_path: str = ""
        self._selected_ids: list[int] = []
        self._current_statuses = None
        self._current_colors = None
        self._split_mode = False
        self._import_errors: list[tuple[str, str]] = []
        self._import_total = 0
        self._import_done = 0
        self._cancelling = False
        log.info("GridView.__init__ completed")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # left filter panel
        self._filter_panel = FilterPanel(settings=self._settings)
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

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setToolTip("取消匯入；已匯入的檔案會保留")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
            f" border:1px solid #444; border-radius:3px; padding:3px 10px;"
            f" font-size:10px; }}"
            f"QPushButton:hover:!disabled {{ color:#fff; border-color:{REJECT_CLR};"
            f" background:rgba(170,50,50,30); }}"
            f"QPushButton:disabled {{ color:{TEXT_MUTED}; border-color:#2a2a2a; }}"
        )
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._cancel_btn.hide()
        tb.addWidget(self._cancel_btn)

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

        self._analyse_btn = QPushButton("⊙  分析模糊")
        self._analyse_btn.setCursor(Qt.PointingHandCursor)
        self._analyse_btn.setToolTip("分析尚未計算模糊分數的照片")
        self._analyse_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
            f" border:1px solid #333; border-radius:3px; padding:3px 10px;"
            f" font-size:10px; }}"
            f"QPushButton:hover:!disabled {{ background:#2a2a2a; color:#ddd;"
            f" border-color:#555; }}"
            f"QPushButton:disabled {{ color:{TEXT_MUTED}; border-color:#222; }}"
        )
        self._analyse_btn.clicked.connect(self._on_analyse_clicked)
        tb.addWidget(self._analyse_btn)

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

    def _refresh(self, statuses=None, colors=None, blur=None,
                 blur_mode="fixed", blur_fixed_threshold=100.0,
                 blur_relative_percent=20.0):
        self._current_statuses = statuses
        self._current_colors = colors
        self._current_blur = blur
        photos = self._filter_svc.filter(
            statuses=statuses, colors=colors, blur=blur,
            blur_mode=blur_mode, blur_fixed_threshold=blur_fixed_threshold,
            blur_relative_percent=blur_relative_percent,
        )
        self._grid.load_photos(photos, self._tag_repo, self._thumb_svc, self._folder)

    def begin_import(self, total: int):
        self._import_total = total
        self._import_done = 0
        self._cancelling = False
        self._refresh_btn.setEnabled(False)
        self._import_progress.setRange(0, max(1, total))
        self._import_progress.setValue(0)
        self._import_progress.show()
        self._import_label.setText(f"匯入中 0 / {total}")
        self._import_label.show()
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("取消")
        self._cancel_btn.show()

    def update_import_progress(self, current: int, total: int):
        self._import_total = total
        self._import_done = current
        self._import_progress.setRange(0, max(1, total))
        self._import_progress.setValue(current)
        if self._cancelling:
            self._import_label.setText(f"取消中… {current} / {total}")
        else:
            self._import_label.setText(f"匯入中 {current} / {total}")

    def end_import(self):
        was_cancelling = self._cancelling
        done = self._import_done
        total = self._import_total
        self._import_progress.hide()
        self._import_label.hide()
        self._cancel_btn.hide()
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("取消")
        self._cancelling = False
        self._refresh_btn.setEnabled(True)
        if was_cancelling:
            self._show_cancelled_message(done, total)

    def _on_cancel_clicked(self):
        from PySide6.QtWidgets import QMessageBox
        if self._cancelling:
            return
        box = QMessageBox(self)
        box.setWindowTitle("取消匯入")
        box.setIcon(QMessageBox.Question)
        box.setText("確定取消匯入？")
        box.setInformativeText(
            f"已匯入 {self._import_done} / {self._import_total} 張。"
            "已匯入的檔案會保留。"
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText("取消匯入")
        box.button(QMessageBox.No).setText("繼續匯入")
        box.setDefaultButton(QMessageBox.No)
        if box.exec() != QMessageBox.Yes:
            return
        self._cancelling = True
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("取消中…")
        self._import_label.setText(
            f"取消中… {self._import_done} / {self._import_total}"
        )
        self.import_cancel_requested.emit()

    def _show_cancelled_message(self, done: int, total: int):
        try:
            from app.ui.toast import Toast
        except Exception:
            return
        toast = Toast(
            self,
            f"已取消匯入。完成 {done} / {total} 張，未處理的會在下次掃描時偵測。",
            confirm_label=None,
            dismiss_label="知道了",
            auto_dismiss_ms=6000,
        )
        toast.show_at_corner()

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

    def set_missing_paths(self, missing_relative_paths):
        """Sync the 'original file missing' overlay across all visible tiles."""
        self._grid.mark_missing(missing_relative_paths)

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

    def _on_filter_changed(self, statuses, colors, blur):
        self._current_blur = blur or None
        mode = self._settings.get("blur_mode", "fixed")
        threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        self._refresh(
            statuses or None, colors or None, blur or None,
            blur_mode=mode, blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )

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
        mode = self._settings.get("blur_mode", "fixed")
        threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        photos = self._filter_svc.filter(
            statuses=self._current_statuses,
            colors=self._current_colors,
            blur=self._current_blur,
            blur_mode=mode,
            blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )
        photo_ids = [p.id for p in photos]
        if photo_id not in photo_ids:
            return
        loupe = LoupeView(
            photo_ids, photo_ids.index(photo_id),
            self._folder, self._photo_repo,
            self._tag_repo, self._tag_svc,
            filter_svc=self._filter_svc,
            initial_statuses=self._current_statuses,
            initial_colors=self._current_colors,
            settings=self._settings,
        )
        loupe.tag_changed.connect(self._grid.update_item_tag)
        loupe.filter_changed.connect(self._on_loupe_filter_changed)
        loupe.showFullScreen()
        loupe.closed.connect(loupe.deleteLater)

    def _on_loupe_filter_changed(self, statuses: list, colors: list):
        """Filter changes inside Loupe propagate back to the grid + panel."""
        self._filter_panel.set_filter(statuses, colors)
        mode = self._settings.get("blur_mode", "fixed")
        threshold = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        self._refresh(
            statuses or None, colors or None, self._current_blur,
            blur_mode=mode, blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )

    def start_blur_analysis(self, db_path: str):
        """Full re-analysis of all photos. Called after import completes."""
        import sqlite3 as _sq
        conn = _sq.connect(db_path)
        conn.row_factory = _sq.Row
        from app.db.photo_repository import PhotoRepository as _PR
        repo = _PR(conn)
        photo_ids = [p.id for p in repo.get_all()]
        conn.close()
        if not photo_ids:
            return
        self._start_blur_controller(db_path, photo_ids)

    def reanalyze_missing_blur(self, db_path: str):
        """Analyse only photos with blur_score IS NULL."""
        log.info("reanalyze_missing_blur called")
        try:
            import sqlite3 as _sq
            conn = _sq.connect(db_path)
            conn.row_factory = _sq.Row
            from app.db.photo_repository import PhotoRepository as _PR
            repo = _PR(conn)
            photo_ids = repo.get_unanalyzed_ids()
            conn.close()
            log.info("Found %d unanalyzed photos", len(photo_ids))
            if not photo_ids:
                log.info("No unanalyzed photos, skipping blur analysis")
                return
            self._start_blur_controller(db_path, photo_ids)
        except Exception as e:
            log.exception("Error in reanalyze_missing_blur: %s", e)

    def _start_blur_controller(self, db_path: str, photo_ids: list):
        log.info("_start_blur_controller called with %d photos", len(photo_ids))
        try:
            from app.core.blur_worker import BlurController
            if self._blur_ctrl is not None:
                log.warning("Blur controller already running")
                return
            self._analyse_btn.setEnabled(False)
            self._blur_ctrl = BlurController(self._folder, db_path, photo_ids)
            self._blur_ctrl.photo_blur_updated.connect(self._on_photo_blur_updated)
            self._blur_ctrl.finished.connect(self._on_blur_finished)
            log.info("Starting BlurController")
            self._blur_ctrl.start()
            log.info("BlurController started")
        except Exception as e:
            log.exception("Error in _start_blur_controller: %s", e)

    def _on_photo_blur_updated(self, photo_id: int, score: float):
        self._grid.update_item_tag(photo_id)

    def _on_blur_finished(self):
        self._blur_ctrl = None
        self._analyse_btn.setEnabled(True)

    def _on_analyse_clicked(self):
        if self._db_path:
            self.reanalyze_missing_blur(self._db_path)
