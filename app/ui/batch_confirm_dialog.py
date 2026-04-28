from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
)
from PySide6.QtCore import Qt

_dont_ask_again: dict[str, bool] = {}

class BatchConfirmDialog(QDialog):
    def __init__(self, count: int, status: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批次標記確認")
        self.setModal(True)
        layout = QVBoxLayout(self)
        label = QLabel(f"將 {count} 張照片標記為「{status}」？")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self._dont_ask = QCheckBox("之後不再詢問此操作")
        layout.addWidget(self._dont_ask)
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("確認")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def dont_ask_again(self) -> bool:
        return self._dont_ask.isChecked()


def confirm_batch(count: int, status: str, parent=None) -> bool:
    """Returns True if user confirms. Respects 'don't ask again'."""
    if _dont_ask_again.get(status, False):
        return True
    dlg = BatchConfirmDialog(count, status, parent)
    if dlg.exec() == QDialog.Accepted:
        if dlg.dont_ask_again():
            _dont_ask_again[status] = True
        return True
    return False
