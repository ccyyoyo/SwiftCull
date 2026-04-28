from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QSizePolicy
)
from PySide6.QtCore import Signal

STATUSES = ["pick", "reject", "maybe", "untagged"]
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

PANEL_WIDTH = 180

class FilterPanel(QWidget):
    filter_changed = Signal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._status_checks: dict[str, QCheckBox] = {}
        self._color_checks: dict[str, QCheckBox] = {}

        # fixed width always — content hides, panel stays same width
        self.setFixedWidth(PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # toggle button — always at top
        self._toggle_btn = QPushButton("«")
        self._toggle_btn.setToolTip("收合篩選欄")
        self._toggle_btn.setFixedHeight(24)
        self._toggle_btn.clicked.connect(self._toggle)
        root.addWidget(self._toggle_btn)

        # collapsible content
        self._content = QWidget()
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)

        cl.addWidget(QLabel("標記狀態"))
        for s in STATUSES:
            cb = QCheckBox(s)
            cb.stateChanged.connect(self._emit_filter)
            self._status_checks[s] = cb
            cl.addWidget(cb)

        cl.addWidget(QLabel("顏色標籤"))
        for c in COLORS:
            cb = QCheckBox(c)
            cb.stateChanged.connect(self._emit_filter)
            self._color_checks[c] = cb
            cl.addWidget(cb)

        clear_btn = QPushButton("清除篩選")
        clear_btn.clicked.connect(self._clear_all)
        cl.addWidget(clear_btn)
        cl.addStretch()

        root.addWidget(self._content)

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle_btn.setText("«" if self._expanded else "»")
        self._toggle_btn.setToolTip("收合篩選欄" if self._expanded else "展開篩選欄")

    def _emit_filter(self):
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors)

    def _clear_all(self):
        for cb in list(self._status_checks.values()) + list(self._color_checks.values()):
            cb.setChecked(False)
