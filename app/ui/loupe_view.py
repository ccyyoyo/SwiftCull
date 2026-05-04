import os
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QApplication
)
from PySide6.QtGui import QPixmap, QKeyEvent, QWheelEvent
from PySide6.QtCore import Signal, Qt, QTimer

from app.core.preview_loader import load_preview_bytes
from app.ui.filter_panel import (
    STATUSES as _ALL_STATUSES,
    COLORS as _ALL_COLORS,
    _StatusCheckBox,
    _ColorDotCheckBox,
)

COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]
COLOR_HEX = {
    "red": "#FF4444", "orange": "#FF8800", "yellow": "#FFDD00",
    "green": "#44AA44", "blue": "#4488FF", "purple": "#AA44FF",
}


class _LoupeFilterBar(QWidget):
    """Compact horizontal filter strip for the top of the Loupe view."""
    filter_changed = Signal(list, list)  # statuses, colors

    def __init__(
        self,
        initial_statuses: Optional[list[str]] = None,
        initial_colors: Optional[list[str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background: rgba(0,0,0,200); color: white;")
        self.setMouseTracking(True)
        self._status_checks: dict[str, _StatusCheckBox] = {}
        self._color_checks: dict[str, _ColorDotCheckBox] = {}
        self._suppress = False  # mute signals during programmatic toggles

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 12, 4)
        row.setSpacing(8)

        title = QLabel("篩選")
        title.setStyleSheet("color: #aaa; font-size: 10px; letter-spacing: 1px;")
        row.addWidget(title)

        for s in _ALL_STATUSES:
            cb = _StatusCheckBox(s)
            cb.setMinimumWidth(72)
            if initial_statuses and s in initial_statuses:
                cb.setChecked(True)
            cb.stateChanged.connect(self._emit)
            self._status_checks[s] = cb
            row.addWidget(cb)

        sep = QLabel("·")
        sep.setStyleSheet("color: #555;")
        row.addSpacing(4)
        row.addWidget(sep)
        row.addSpacing(4)

        for c in _ALL_COLORS:
            cb = _ColorDotCheckBox(c)
            cb.setMinimumWidth(56)
            if initial_colors and c in initial_colors:
                cb.setChecked(True)
            cb.stateChanged.connect(self._emit)
            self._color_checks[c] = cb
            row.addWidget(cb)

        clear_btn = QPushButton("清除")
        clear_btn.setStyleSheet(
            "color: #ddd; background: #333; padding: 2px 10px;"
            " border: 1px solid #444; border-radius: 3px; font-size: 10px;"
        )
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all)
        row.addStretch()
        row.addWidget(clear_btn)

    def _emit(self):
        if self._suppress:
            return
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors)

    def _clear_all(self):
        self._suppress = True
        try:
            for cb in self._status_checks.values():
                cb.setChecked(False)
            for cb in self._color_checks.values():
                cb.setChecked(False)
        finally:
            self._suppress = False
        self._emit()

class LoupeView(QWidget):
    closed = Signal()
    tag_changed = Signal(int)   # emitted with photo_id when status/color changes
    filter_changed = Signal(list, list)  # mirrors top-bar changes back to GridView

    def __init__(self, photo_ids, current_index, folder_path,
                 photo_repo, tag_repo, tag_svc,
                 filter_svc=None,
                 initial_statuses: Optional[list[str]] = None,
                 initial_colors: Optional[list[str]] = None,
                 initial_blur: Optional[list[str]] = None,
                 settings=None,
                 parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        self.setMouseTracking(True)
        self._ids = list(photo_ids)
        self._idx = current_index
        self._folder = folder_path
        self._photo_repo = photo_repo
        self._tag_repo = tag_repo
        self._tag_svc = tag_svc
        self._filter_svc = filter_svc
        self._settings = settings  # SettingsDB instance, may be None
        self._statuses = list(initial_statuses) if initial_statuses else []
        self._colors = list(initial_colors) if initial_colors else []
        self._blur = list(initial_blur) if initial_blur else []
        self._zoom = 1.0
        self._base_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setStyleSheet("background: black;")
        self._img_label.setMouseTracking(True)
        layout.addWidget(self._img_label, stretch=1)

        # --- status indicator ---
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "color: white; font-size: 18px; font-weight: bold;"
            " background: transparent; padding: 4px;"
        )
        self._status_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        # overlay it on top-left using absolute positioning
        self._status_label.setParent(self)
        self._status_label.move(16, 16)
        self._status_label.resize(200, 36)
        self._status_label.raise_()

        # --- blur score overlay (top-right) ---
        self._blur_label = QLabel("")
        self._blur_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._blur_label.setStyleSheet(
            "color: #aaa; font-size: 13px; background: transparent; padding: 4px;"
        )
        self._blur_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._blur_label.setParent(self)
        self._blur_label.resize(200, 30)
        self._blur_label.raise_()

        # --- bottom toolbar (auto-hide) ---
        self._toolbar = QWidget(self)
        self._toolbar.setStyleSheet("background: rgba(0,0,0,200); color: white;")
        self._toolbar.setMouseTracking(True)
        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)

        for label, status in [("P  Pick", "pick"), ("R  Reject", "reject"), ("M  Maybe", "maybe")]:
            btn = QPushButton(label)
            btn.setStyleSheet("color: white; background: #333; padding: 6px 16px;")
            btn.clicked.connect(lambda checked, s=status: self._set_status(s))
            tb_layout.addWidget(btn)

        clear_status_btn = QPushButton("U  清除")
        clear_status_btn.setStyleSheet("color: white; background: #444; padding: 6px 12px;")
        clear_status_btn.setToolTip("清除標記 (U)")
        clear_status_btn.clicked.connect(self._clear_status)
        tb_layout.addWidget(clear_status_btn)

        tb_layout.addSpacing(16)

        # color buttons
        for c in COLORS:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"background: {COLOR_HEX[c]}; border-radius: 4px;")
            btn.setToolTip(c)
            btn.clicked.connect(lambda checked, col=c: self._set_color(col))
            tb_layout.addWidget(btn)

        # clear color
        clear_color_btn = QPushButton("✕ 顏色")
        clear_color_btn.setStyleSheet("color: white; background: #444; padding: 4px 8px;")
        clear_color_btn.clicked.connect(lambda: self._set_color(None))
        tb_layout.addWidget(clear_color_btn)

        tb_layout.addStretch()
        close_btn = QPushButton("關閉 (Esc)")
        close_btn.setStyleSheet("color: white; background: #555; padding: 6px 16px;")
        close_btn.clicked.connect(self.close)
        tb_layout.addWidget(close_btn)

        # auto-hide timer (shared by top + bottom bars)
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(2000)
        self._hide_timer.timeout.connect(self._hide_chrome)
        self._chrome_visible = True

        # --- top filter bar (auto-hide) -----------------------------------
        self._top_bar = _LoupeFilterBar(
            initial_statuses=self._statuses,
            initial_colors=self._colors,
            parent=self,
        )
        self._top_bar.filter_changed.connect(self._on_filter_changed)

        self._empty_label = QLabel("沒有符合篩選的照片")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(
            "background: black; color: #888; font-size: 14px;"
        )
        self._empty_label.setParent(self)
        self._empty_label.hide()

        self._load_current()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_chrome()
        self._blur_label.move(self.width() - 210, 16)

    def _position_chrome(self):
        bottom_h = 56
        top_h = 40
        self._toolbar.setGeometry(0, self.height() - bottom_h, self.width(), bottom_h)
        self._top_bar.setGeometry(0, 0, self.width(), top_h)
        self._empty_label.setGeometry(0, top_h, self.width(),
                                      self.height() - top_h - bottom_h)

    def showEvent(self, event):
        super().showEvent(event)
        self._position_chrome()
        self._top_bar.show()
        self._top_bar.raise_()
        self._toolbar.show()
        self._toolbar.raise_()
        self._hide_timer.start()

    def _show_chrome(self):
        self._top_bar.show()
        self._top_bar.raise_()
        self._toolbar.show()
        self._toolbar.raise_()
        self._chrome_visible = True
        self._hide_timer.start()

    def _hide_chrome(self):
        # don't hide while the user is hovering one of the bars
        if self._top_bar.underMouse() or self._toolbar.underMouse():
            self._hide_timer.start()
            return
        self._top_bar.hide()
        self._toolbar.hide()
        self._chrome_visible = False

    def mouseMoveEvent(self, event):
        y = event.pos().y()
        if y < 60 or y > self.height() - 80:
            self._show_chrome()
        super().mouseMoveEvent(event)

    def _load_current(self):
        self._zoom = 1.0
        if not self._ids:
            self._img_label.clear()
            self._img_label.hide()
            self._empty_label.show()
            self._empty_label.raise_()
            self._status_label.setText("")
            return
        self._empty_label.hide()
        self._img_label.show()
        self._idx = max(0, min(self._idx, len(self._ids) - 1))
        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        abs_path = os.path.join(self._folder, photo.relative_path)

        if not os.path.exists(abs_path):
            self._base_pixmap = None
            self._img_label.clear()
            self._img_label.setText(
                "✕ 原檔不存在\n\n"
                f"{photo.relative_path}\n\n"
                "請檢查檔案是否被移動或刪除"
            )
            self._img_label.setStyleSheet(
                "background: black; color: #c66; font-size: 14px;"
                " padding: 24px;"
            )
            self._update_status_label()
            return

        self._base_pixmap = self._load_pixmap(abs_path)
        if self._base_pixmap is None or self._base_pixmap.isNull():
            self._img_label.clear()
            self._img_label.setText("無法載入預覽")
            self._img_label.setStyleSheet(
                "background: black; color: #888; font-size: 14px;"
            )
        else:
            self._img_label.setStyleSheet("background: black;")
            self._apply_zoom()
        self._update_status_label()
        self._update_blur_label()

    def _on_filter_changed(self, statuses: list, colors: list):
        self._statuses = list(statuses)
        self._colors = list(colors)
        self.filter_changed.emit(self._statuses, self._colors)
        if self._filter_svc is None:
            return

        prev_id = self._ids[self._idx] if self._ids else None
        mode, threshold, percent = self._blur_settings()
        new_photos = self._filter_svc.filter(
            statuses=self._statuses or None,
            colors=self._colors or None,
            blur=self._blur or None,
            blur_mode=mode,
            blur_fixed_threshold=threshold,
            blur_relative_percent=percent,
        )
        new_ids = [p.id for p in new_photos]

        if prev_id is not None and prev_id in new_ids:
            self._idx = new_ids.index(prev_id)
        else:
            self._idx = 0
        self._ids = new_ids
        self._load_current()

    def _load_pixmap(self, abs_path: str) -> QPixmap:
        data = load_preview_bytes(abs_path)
        pix = QPixmap()
        if data:
            pix.loadFromData(data)
        return pix

    def _apply_zoom(self):
        if self._base_pixmap is None or self._base_pixmap.isNull():
            return
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            base_w = int(geo.width() * self._zoom)
            base_h = int((geo.height() - 60) * self._zoom)
        else:
            base_w = int(1920 * self._zoom)
            base_h = int(1020 * self._zoom)
        pix = self._base_pixmap.scaled(
            base_w, base_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._img_label.setPixmap(pix)

    def _update_status_label(self):
        if not self._ids:
            self._status_label.setText("")
            return
        photo_id = self._ids[self._idx]
        tag = self._tag_repo.get_by_photo_id(photo_id)
        status = tag.status if tag else None
        color = tag.color if tag else None
        status_text = {"pick": "✓ Pick", "reject": "✕ Reject", "maybe": "? Maybe"}.get(status, "")
        color_dot = f" ●" if color else ""
        self._status_label.setText(status_text + color_dot)
        if color:
            self._status_label.setStyleSheet(
                f"color: {COLOR_HEX.get(color, 'white')}; font-size: 18px;"
                f" font-weight: bold; background: transparent; padding: 4px;"
            )
        else:
            self._status_label.setStyleSheet(
                "color: white; font-size: 18px; font-weight: bold;"
                " background: transparent; padding: 4px;"
            )

    def _update_blur_label(self):
        from app.utils.theme import BLUR_BLURRY, BLUR_SHARP, BLUR_UNKNOWN
        if not self._ids:
            self._blur_label.setText("")
            return
        photo_id = self._ids[self._idx]
        photo = self._photo_repo.get_by_id(photo_id)
        score = photo.blur_score if photo else None
        if score is None:
            self._blur_label.setText("Blur: —")
            self._blur_label.setStyleSheet(
                f"color:{BLUR_UNKNOWN}; font-size:13px; background:transparent; padding:4px;"
            )
            return

        threshold = self._resolve_blur_threshold()
        color = BLUR_BLURRY if score < threshold else BLUR_SHARP
        self._blur_label.setText(f"Blur: {score:.1f}")
        self._blur_label.setStyleSheet(
            f"color:{color}; font-size:13px; background:transparent; padding:4px;"
        )

    def _resolve_blur_threshold(self) -> float:
        mode, fixed, percent = self._blur_settings()
        if mode != "relative":
            return fixed
        all_photos = self._photo_repo.get_all()
        scores = [p.blur_score for p in all_photos if p.blur_score is not None]
        if not scores:
            return fixed
        from app.core.blur_service import BlurService
        return BlurService().relative_threshold(scores, percent)

    def _blur_settings(self):
        if self._settings is None:
            return "fixed", 100.0, 20.0
        mode = self._settings.get("blur_mode", "fixed")
        fixed = float(self._settings.get("blur_fixed_threshold", 100.0))
        percent = float(self._settings.get("blur_relative_percent", 20.0))
        return mode, fixed, percent

    def _current_photo_id(self) -> Optional[int]:
        if not self._ids:
            return None
        return self._ids[self._idx]

    def _set_status(self, status: str):
        photo_id = self._current_photo_id()
        if photo_id is None:
            return
        self._tag_svc.set_status(photo_id, status)
        self._update_status_label()
        self.tag_changed.emit(photo_id)

    def _clear_status(self):
        photo_id = self._current_photo_id()
        if photo_id is None:
            return
        self._tag_svc.clear_status(photo_id)
        self._update_status_label()
        self.tag_changed.emit(photo_id)

    def _set_color(self, color):
        photo_id = self._current_photo_id()
        if photo_id is None:
            return
        self._tag_svc.set_color(photo_id, color)
        self._update_status_label()
        self.tag_changed.emit(photo_id)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_P:
            self._set_status("pick")
        elif key == Qt.Key_R:
            self._set_status("reject")
        elif key == Qt.Key_M:
            self._set_status("maybe")
        elif key == Qt.Key_U:
            self._clear_status()
        elif key == Qt.Key_Left and self._idx > 0:
            self._idx -= 1
            self._load_current()
        elif key == Qt.Key_Right and self._idx < len(self._ids) - 1:
            self._idx += 1
            self._load_current()
        elif key == Qt.Key_Escape:
            self.close()
        else:
            self._show_chrome()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl + 滾輪 → 縮放
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom = min(self._zoom * 1.15, 8.0)
            else:
                self._zoom = max(self._zoom / 1.15, 0.1)
            self._apply_zoom()
        else:
            # 滾輪上 → 上一張，滾輪下 → 下一張
            # 若縮放不是 100%，先回到 100% 再換張
            delta = event.angleDelta().y()
            if abs(self._zoom - 1.0) > 0.01:
                self._zoom = 1.0
                self._apply_zoom()
            elif delta > 0 and self._idx > 0:
                self._idx -= 1
                self._load_current()
            elif delta < 0 and self._idx < len(self._ids) - 1:
                self._idx += 1
                self._load_current()
        event.accept()

    def closeEvent(self, event):
        self._hide_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
