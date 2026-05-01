from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox,
    QPushButton, QSizePolicy, QHBoxLayout
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Signal, Qt, QRect
from app.utils.theme import (
    BG_PANEL, BG_HOVER, BORDER, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    STATUS_ICON, STATUS_COLOR, COLOR_DOT,
    PICK_CLR, REJECT_CLR, MAYBE_CLR,
    BLUR_BLURRY, BLUR_SHARP, BLUR_UNKNOWN,
)

STATUSES = ["pick", "reject", "maybe", "untagged"]
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

PANEL_WIDTH = 160
TAB_WIDTH = 28          # collapsed tab strip width


class _ColorDotCheckBox(QWidget):
    """Custom checkbox showing color dot + label."""
    stateChanged = Signal(int)

    def __init__(self, color_key: str, parent=None):
        super().__init__(parent)
        self._color_key = color_key
        self._checked = False
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool):
        self._checked = v
        self.update()
        self.stateChanged.emit(2 if v else 0)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.stateChanged.emit(2 if self._checked else 0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # dot
        dot_color = QColor(COLOR_DOT.get(self._color_key, "#888"))
        if self._checked:
            p.setBrush(dot_color)
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(dot_color, 1.5))
        p.drawEllipse(4, 5, 12, 12)
        # label
        p.setPen(QColor(TEXT_PRIMARY if self._checked else TEXT_SECONDARY))
        from PySide6.QtGui import QFont
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRect(22, 0, self.width() - 22, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._color_key)
        p.end()


class _StatusCheckBox(QWidget):
    """Custom checkbox showing status icon + label."""
    stateChanged = Signal(int)

    def __init__(self, status_key: str, parent=None):
        super().__init__(parent)
        self._key = status_key
        self._checked = False
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool):
        self._checked = v
        self.update()
        self.stateChanged.emit(2 if v else 0)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.stateChanged.emit(2 if self._checked else 0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        from PySide6.QtGui import QFont

        if self._key == "untagged":
            icon_color = QColor(TEXT_MUTED)
            icon_char = "—"
        else:
            icon_color = QColor(STATUS_COLOR.get(self._key, "#888"))
            icon_char = STATUS_ICON.get(self._key, "?")

        if self._checked:
            p.setBrush(icon_color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(2, 3, 16, 16)
            p.setPen(QColor("#000"))
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(icon_color, 1.5))
            p.drawEllipse(2, 3, 16, 16)
            p.setPen(icon_color)

        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRect(2, 3, 16, 16), Qt.AlignCenter, icon_char)

        p.setPen(QColor(TEXT_PRIMARY if self._checked else TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10))
        label = self._key.capitalize()
        p.drawText(QRect(24, 0, self.width() - 24, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, label)
        p.end()


class _CollapsedTab(QWidget):
    """Vertical tab shown when panel is collapsed. Click to expand."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(TAB_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("展開篩選面板")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # background
        p.fillRect(self.rect(), QColor(BG_PANEL))

        # right border line
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        # hover highlight strip
        p.fillRect(0, 0, self.width() - 1, self.height(), QColor(BG_PANEL))

        # draw rotated text "▶ FILTER" centered vertically
        p.save()
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(-90)
        font = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(font)
        p.setPen(QColor(TEXT_SECONDARY))
        text = "▶  FILTER"
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        p.drawText(int(-tw / 2), int(th / 3), text)
        p.restore()
        p.end()

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


class FilterPanel(QWidget):
    filter_changed = Signal(list, list, list)

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._expanded = True
        self._status_checks: dict[str, _StatusCheckBox] = {}
        self._color_checks: dict[str, _ColorDotCheckBox] = {}
        self._blur_checks: dict = {}

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"background:{BG_PANEL};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # collapsed tab (shown only when panel is collapsed)
        self._collapsed_tab = _CollapsedTab()
        self._collapsed_tab.clicked.connect(self._toggle)
        self._collapsed_tab.hide()
        root.addWidget(self._collapsed_tab)

        # expanded panel content
        self._panel_body = QWidget()
        self._panel_body.setFixedWidth(PANEL_WIDTH)
        self._panel_body.setStyleSheet(
            f"background:{BG_PANEL}; border-right:1px solid #2a2a2a;"
        )
        body_layout = QVBoxLayout(self._panel_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # header row with toggle
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(f"background:#1e1e1e; border-bottom:1px solid #2a2a2a;")
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(10, 0, 6, 0)
        title_lbl = QLabel("FILTER")
        title_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:10px; letter-spacing:2px; font-weight:600;"
        )
        hrow.addWidget(title_lbl)
        hrow.addStretch()
        self._toggle_btn = QPushButton("«")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_SECONDARY}; border:none;"
            f" font-size:14px; padding:0;"
        )
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        hrow.addWidget(self._toggle_btn)
        body_layout.addWidget(header)

        # content
        self._content = QWidget()
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(2)

        # status section
        sec1 = QLabel("STATUS")
        sec1.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec1)
        for s in STATUSES:
            cb = _StatusCheckBox(s)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[s] = cb
            cl.addWidget(cb)

        cl.addSpacing(8)

        # color section
        sec2 = QLabel("COLOR")
        sec2.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec2)
        for c in COLORS:
            cb = _ColorDotCheckBox(c)
            cb.stateChanged.connect(self._emit_filter)
            self._color_checks[c] = cb
            cl.addWidget(cb)

        cl.addSpacing(8)
        clear_btn = QPushButton("清除篩選")
        clear_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_SECONDARY}; border:1px solid #333;"
            f" border-radius:3px; padding:4px 8px; font-size:10px;"
        )
        clear_btn.clicked.connect(self._clear_all)
        cl.addWidget(clear_btn)

        cl.addSpacing(8)

        sec3 = QLabel("BLUR")
        sec3.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; letter-spacing:1px; margin-top:4px;"
        )
        cl.addWidget(sec3)

        blur_header_w = QWidget()
        blur_header_l = QHBoxLayout(blur_header_w)
        blur_header_l.setContentsMargins(0, 0, 0, 0)
        blur_header_l.setSpacing(4)
        blur_header_l.addStretch()
        gear_btn = QPushButton("⚙")
        gear_btn.setFixedSize(18, 18)
        gear_btn.setStyleSheet(
            f"background:transparent; color:{TEXT_MUTED}; border:none; font-size:11px; padding:0;"
        )
        gear_btn.setCursor(Qt.PointingHandCursor)
        gear_btn.setToolTip("模糊偵測設定")
        gear_btn.clicked.connect(self._open_blur_settings)
        blur_header_l.addWidget(gear_btn)
        cl.addWidget(blur_header_w)

        from PySide6.QtWidgets import QCheckBox as _QCB
        for blur_key, label in [("blurry", "模糊"), ("sharp", "清晰"), ("unanalyzed", "未分析")]:
            cb = _QCB(label)
            cb.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px;")
            cb.stateChanged.connect(self._emit_filter)
            self._blur_checks[blur_key] = cb
            cl.addWidget(cb)

        cl.addStretch()

        body_layout.addWidget(self._content)
        root.addWidget(self._panel_body)

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._collapsed_tab.hide()
            self._panel_body.show()
        else:
            self._panel_body.hide()
            self._collapsed_tab.show()

    def _emit_filter(self):
        if getattr(self, "_suppress", False):
            return
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        blur = [k for k, cb in self._blur_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors, blur)

    def _clear_all(self):
        for cb in (list(self._status_checks.values())
                   + list(self._color_checks.values())
                   + list(self._blur_checks.values())):
            cb.setChecked(False)

    def _open_blur_settings(self):
        from app.ui.blur_settings_dialog import BlurSettingsDialog
        if self._settings is None:
            return
        dlg = BlurSettingsDialog(self._settings, self)
        dlg.exec()

    def set_filter(self, statuses, colors):
        """Programmatically reflect external filter changes (e.g. from Loupe)
        without re-emitting filter_changed back to the caller."""
        wanted_s = set(statuses or [])
        wanted_c = set(colors or [])
        self._suppress = True
        try:
            for s, cb in self._status_checks.items():
                cb.setChecked(s in wanted_s)
            for c, cb in self._color_checks.items():
                cb.setChecked(c in wanted_c)
        finally:
            self._suppress = False
