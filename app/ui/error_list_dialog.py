from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSizePolicy
)
from PySide6.QtCore import Qt
from app.utils.theme import BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY, REJECT_CLR


class ErrorListDialog(QDialog):
    def __init__(self, errors: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("匯入失敗清單")
        self.setModal(True)
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        header = QLabel(f"<span style='color:{REJECT_CLR};font-size:18px'>⚠</span>"
                        f"  <span style='font-size:13px'>{len(errors)} 個檔案讀取失敗</span>")
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        hint = QLabel("這些檔案被略過，未匯入到專案。可能原因：檔案損壞、格式不支援、無法讀取。")
        hint.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background:{BG_DEEP}; border:1px solid #2a2a2a;"
            f" border-radius:3px; padding:4px; }}"
            f"QListWidget::item {{ padding:4px 6px; border-bottom:1px solid #1a1a1a; }}"
            f"QListWidget::item:selected {{ background:{BG_PANEL}; color:{TEXT_PRIMARY}; }}"
        )
        self._list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        for rel, reason in errors:
            text = f"{rel}\n    └ {reason}"
            it = QListWidgetItem(text)
            it.setToolTip(f"{rel}\n{reason}")
            self._list.addItem(it)
        layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("關閉")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


def show_errors(errors: list[tuple[str, str]], parent=None):
    if not errors:
        return
    dlg = ErrorListDialog(errors, parent)
    dlg.exec()
