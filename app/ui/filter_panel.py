from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton
from PySide6.QtCore import Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect

STATUSES = ["pick", "reject", "maybe", "untagged"]
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

PANEL_WIDTH = 180

class FilterPanel(QWidget):
    filter_changed = Signal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._status_checks: dict[str, QCheckBox] = {}
        self._color_checks: dict[str, QCheckBox] = {}
        self._collapsed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("篩選")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        layout.addWidget(QLabel("標記狀態"))
        for s in STATUSES:
            cb = QCheckBox(s)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[s] = cb
            layout.addWidget(cb)

        layout.addWidget(QLabel("顏色標籤"))
        for c in COLORS:
            cb = QCheckBox(c)
            cb.stateChanged.connect(self._emit_filter)
            self._color_checks[c] = cb
            layout.addWidget(cb)

        clear_btn = QPushButton("清除篩選")
        clear_btn.clicked.connect(self._clear_all)
        layout.addWidget(clear_btn)
        layout.addStretch()

        self.setFixedWidth(PANEL_WIDTH)

        # auto-hide: collapse when mouse leaves
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(800)
        self._hide_timer.timeout.connect(self._collapse)

        self._anim = QPropertyAnimation(self, b"minimumWidth")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _emit_filter(self):
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors)

    def _clear_all(self):
        for cb in list(self._status_checks.values()) + list(self._color_checks.values()):
            cb.setChecked(False)

    def enterEvent(self, event):
        self._hide_timer.stop()
        self._expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hide_timer.start()
        super().leaveEvent(event)

    def _expand(self):
        if not self._collapsed:
            return
        self._collapsed = False
        self._anim.stop()
        self._anim.setStartValue(self.minimumWidth())
        self._anim.setEndValue(PANEL_WIDTH)
        self.setMaximumWidth(PANEL_WIDTH)
        self._anim.start()
        for child in self.children():
            if hasattr(child, "show"):
                child.show()

    def _collapse(self):
        # only collapse if no filter is active
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        if statuses or colors:
            return
        self._collapsed = True
        self._anim.stop()
        self._anim.setStartValue(self.minimumWidth())
        self._anim.setEndValue(8)
        self.setMaximumWidth(8)
        self._anim.start()
