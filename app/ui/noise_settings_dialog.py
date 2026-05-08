from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDoubleSpinBox
)

from app.db.settings_db import SettingsDB


class NoiseSettingsDialog(QDialog):
    def __init__(self, settings: SettingsDB, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("雜訊偵測設定")
        self.setFixedSize(280, 130)
        self.setStyleSheet("background:#1e1e1e; color:#e8e8e8;")

        fixed_threshold = float(self._settings.get("noise_fixed_threshold", 0.5))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("閾值 (SNR log10):"))
        self._fixed_spin = QDoubleSpinBox()
        self._fixed_spin.setRange(0.001, 10.0)
        self._fixed_spin.setDecimals(3)
        self._fixed_spin.setSingleStep(0.05)
        self._fixed_spin.setValue(fixed_threshold)
        threshold_row.addWidget(self._fixed_spin)
        layout.addLayout(threshold_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("確定")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _on_ok(self):
        self._settings.set("noise_fixed_threshold", self._fixed_spin.value())
        self.accept()
