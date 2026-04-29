import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal

_SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "SwiftCull", "settings.json"
)


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    try:
        existing = _load_settings()
        existing.update(data)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass


class BlurSettingsDialog(QDialog):
    settings_changed = Signal(str, float)   # mode, threshold_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模糊偵測設定")
        self.setFixedSize(320, 200)
        self.setStyleSheet("background:#1e1e1e; color:#e8e8e8;")

        settings = _load_settings()
        self._mode = settings.get("blur_mode", "fixed")
        self._fixed_threshold = float(settings.get("blur_fixed_threshold", 100.0))
        self._relative_percent = int(settings.get("blur_relative_percent", 20))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["fixed (固定閾值)", "relative (相對底部%)"])
        self._mode_combo.setCurrentIndex(0 if self._mode == "fixed" else 1)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        layout.addLayout(mode_row)

        self._fixed_row = QHBoxLayout()
        self._fixed_row.addWidget(QLabel("閾值 (Laplacian):"))
        self._fixed_spin = QSpinBox()
        self._fixed_spin.setRange(1, 10000)
        self._fixed_spin.setValue(int(self._fixed_threshold))
        self._fixed_row.addWidget(self._fixed_spin)
        layout.addLayout(self._fixed_row)

        self._rel_row = QHBoxLayout()
        self._rel_row.addWidget(QLabel("底部 %:"))
        self._rel_spin = QSpinBox()
        self._rel_spin.setRange(1, 99)
        self._rel_spin.setValue(self._relative_percent)
        self._rel_row.addWidget(self._rel_spin)
        layout.addLayout(self._rel_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("確定")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._on_mode_changed(self._mode_combo.currentIndex())

    def _on_mode_changed(self, idx: int):
        is_fixed = idx == 0
        for i in range(self._fixed_row.count()):
            w = self._fixed_row.itemAt(i).widget()
            if w:
                w.setVisible(is_fixed)
        for i in range(self._rel_row.count()):
            w = self._rel_row.itemAt(i).widget()
            if w:
                w.setVisible(not is_fixed)

    def _on_ok(self):
        mode = "fixed" if self._mode_combo.currentIndex() == 0 else "relative"
        fixed_val = float(self._fixed_spin.value())
        rel_val = self._rel_spin.value()
        _save_settings({
            "blur_mode": mode,
            "blur_fixed_threshold": fixed_val,
            "blur_relative_percent": rel_val,
        })
        threshold = fixed_val if mode == "fixed" else float(rel_val)
        self.settings_changed.emit(mode, threshold)
        self.accept()
