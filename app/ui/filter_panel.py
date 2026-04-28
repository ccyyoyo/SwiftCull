from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal, QPropertyAnimation, QEasingCurve

STATUSES = ["pick", "reject", "maybe", "untagged"]
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

PANEL_EXPANDED = 180
PANEL_COLLAPSED = 32

class FilterPanel(QWidget):
    filter_changed = Signal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._status_checks: dict[str, QCheckBox] = {}
        self._color_checks: dict[str, QCheckBox] = {}

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(4, 4, 4, 4)
        self._root.setSpacing(4)

        # toggle button row
        toggle_row = QHBoxLayout()
        self._toggle_btn = QPushButton("◀ 篩選")
        self._toggle_btn.setFixedHeight(28)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(True)
        self._toggle_btn.clicked.connect(self._toggle)
        toggle_row.addWidget(self._toggle_btn)
        self._root.addLayout(toggle_row)

        # collapsible content widget
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        content_layout.addWidget(QLabel("標記狀態"))
        for s in STATUSES:
            cb = QCheckBox(s)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[s] = cb
            content_layout.addWidget(cb)

        content_layout.addWidget(QLabel("顏色標籤"))
        for c in COLORS:
            cb = QCheckBox(c)
            cb.stateChanged.connect(self._emit_filter)
            self._color_checks[c] = cb
            content_layout.addWidget(cb)

        clear_btn = QPushButton("清除篩選")
        clear_btn.clicked.connect(self._clear_all)
        content_layout.addWidget(clear_btn)
        content_layout.addStretch()

        self._root.addWidget(self._content)

        self.setFixedWidth(PANEL_EXPANDED)

        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _toggle(self):
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self):
        self._expanded = True
        self._toggle_btn.setText("◀ 篩選")
        self._toggle_btn.setChecked(True)
        self._content.show()
        self._anim.stop()
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(PANEL_EXPANDED)
        self.setMinimumWidth(PANEL_COLLAPSED)
        self._anim.start()

    def _collapse(self):
        self._expanded = False
        self._toggle_btn.setText("▶")
        self._toggle_btn.setChecked(False)
        self._content.hide()
        self._anim.stop()
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(PANEL_COLLAPSED)
        self.setMinimumWidth(0)
        self._anim.start()

    def _emit_filter(self):
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors)

    def _clear_all(self):
        for cb in list(self._status_checks.values()) + list(self._color_checks.values()):
            cb.setChecked(False)
