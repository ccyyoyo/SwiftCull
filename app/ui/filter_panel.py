from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton
from PySide6.QtCore import Signal

STATUSES = ["pick", "reject", "maybe", "untagged"]
COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]

class FilterPanel(QWidget):
    filter_changed = Signal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self._status_checks: dict[str, QCheckBox] = {}
        self._color_checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("篩選"))
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

    def _emit_filter(self):
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        colors = [c for c, cb in self._color_checks.items() if cb.isChecked()]
        self.filter_changed.emit(statuses, colors)

    def _clear_all(self):
        for cb in list(self._status_checks.values()) + list(self._color_checks.values()):
            cb.setChecked(False)
