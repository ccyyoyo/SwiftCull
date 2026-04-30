"""Right-bottom toast notification.

Used to surface "found N new / M modified files" style events without
interrupting the culling workflow. Toasts are non-modal, can be dismissed,
and reposition themselves to the parent's bottom-right corner on resize.

The toast is just a styled `QFrame` parented to the main window; it does
not steal focus or eat keyboard input.
"""

from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.utils.messages import format_scan_message
from app.utils.theme import (
    ACCENT, BG_PANEL, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
)

_MARGIN_PX = 16


class Toast(QFrame):
    """Floating right-bottom notification with optional confirm/dismiss buttons."""

    def __init__(
        self,
        parent: QWidget,
        message: str,
        *,
        confirm_label: Optional[str] = None,
        dismiss_label: str = "忽略",
        on_confirm: Optional[Callable[[], None]] = None,
        on_dismiss: Optional[Callable[[], None]] = None,
        auto_dismiss_ms: int = 0,
    ):
        super().__init__(parent)
        self._on_confirm = on_confirm
        self._on_dismiss = on_dismiss
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#Toast {{ background:{BG_PANEL}; border:1px solid {BORDER};"
            f" border-radius:6px; }}"
            f"#Toast QLabel {{ color:{TEXT_PRIMARY}; }}"
        )
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        self._msg = QLabel(message)
        self._msg.setWordWrap(True)
        self._msg.setFont(QFont("Segoe UI", 10))
        outer.addWidget(self._msg)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        btn_row.addStretch()

        self._dismiss_btn = QPushButton(dismiss_label)
        self._dismiss_btn.setCursor(Qt.PointingHandCursor)
        self._dismiss_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_SECONDARY};"
            f" border:1px solid {BORDER}; border-radius:3px;"
            f" padding:3px 10px; font-size:10px; }}"
            f"QPushButton:hover {{ color:{TEXT_PRIMARY}; border-color:#555; }}"
        )
        self._dismiss_btn.clicked.connect(self._handle_dismiss)
        btn_row.addWidget(self._dismiss_btn)

        if confirm_label is not None:
            self._confirm_btn = QPushButton(confirm_label)
            self._confirm_btn.setCursor(Qt.PointingHandCursor)
            self._confirm_btn.setStyleSheet(
                f"QPushButton {{ background:{ACCENT}; color:white;"
                f" border:1px solid {ACCENT}; border-radius:3px;"
                f" padding:3px 12px; font-size:10px; font-weight:600; }}"
                f"QPushButton:hover {{ background:#ff8a3a; border-color:#ff8a3a; }}"
            )
            self._confirm_btn.clicked.connect(self._handle_confirm)
            btn_row.addWidget(self._confirm_btn)

        outer.addLayout(btn_row)

        self.adjustSize()
        self._reposition()
        if parent is not None:
            parent.installEventFilter(self)

        if auto_dismiss_ms > 0:
            QTimer.singleShot(auto_dismiss_ms, self._handle_dismiss)

    def show_at_corner(self):
        self._reposition()
        self.show()
        self.raise_()

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(0, parent.width() - self.width() - _MARGIN_PX)
        y = max(0, parent.height() - self.height() - _MARGIN_PX)
        self.move(x, y)

    def eventFilter(self, obj, event):
        # When the parent resizes, follow the bottom-right corner.
        if obj is self.parentWidget() and event.type() in (
            event.Type.Resize, event.Type.Show, event.Type.Move
        ):
            self._reposition()
        return super().eventFilter(obj, event)

    def _handle_confirm(self):
        cb = self._on_confirm
        self._teardown()
        if cb is not None:
            cb()

    def _handle_dismiss(self):
        cb = self._on_dismiss
        self._teardown()
        if cb is not None:
            cb()

    def _teardown(self):
        parent = self.parentWidget()
        if parent is not None:
            parent.removeEventFilter(self)
        self.hide()
        self.deleteLater()


def show_scan_toast(
    parent: QWidget,
    new_count: int,
    modified_count: int,
    on_confirm: Callable[[], None],
    on_dismiss: Optional[Callable[[], None]] = None,
) -> Toast:
    """Convenience: build a toast for "N new / M modified" scan results."""
    toast = Toast(
        parent,
        format_scan_message(new_count, modified_count),
        confirm_label="匯入",
        dismiss_label="忽略",
        on_confirm=on_confirm,
        on_dismiss=on_dismiss,
    )
    toast.show_at_corner()
    return toast
