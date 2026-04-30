import os
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor

from app.core.recent_projects import RecentProject
from app.utils.theme import (
    ACCENT, BG_MAIN, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)


class _RecentRow(QFrame):
    """Clickable row for one recent project."""
    clicked = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, project: RecentProject, parent=None):
        super().__init__(parent)
        self._project = project
        exists = project.exists()
        self.setCursor(QCursor(Qt.PointingHandCursor if exists else Qt.ArrowCursor))
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(
            "QFrame { background: transparent; border-radius: 4px; padding: 0; }"
            "QFrame:hover { background: #1f1f1f; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(12)

        name_color = TEXT_PRIMARY if exists else TEXT_MUTED
        name = QLabel(project.name)
        name.setStyleSheet(
            f"color:{name_color}; font-size:13px; font-weight:500; background:transparent;"
        )
        path = QLabel(project.path)
        path.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:11px; background:transparent;"
        )
        path.setMinimumWidth(0)
        path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(name)
        col.addWidget(path)
        row.addLayout(col, stretch=1)

        if not exists:
            badge = QLabel("找不到")
            badge.setStyleSheet(
                "color:#c66; background:transparent; font-size:11px;"
                " border:1px solid #553; border-radius:3px; padding:2px 6px;"
            )
            row.addWidget(badge)

        remove = QPushButton("移除")
        remove.setCursor(Qt.PointingHandCursor)
        remove.setStyleSheet(
            f"color:{TEXT_MUTED}; background:transparent; border:none;"
            f" font-size:11px; padding:2px 6px;"
            f"QPushButton:hover {{ color:#fff; }}"
        )
        remove.clicked.connect(self._on_remove)
        row.addWidget(remove)

    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton
                and self._project.exists()
                and not self._on_remove_button(event.pos())):
            self.clicked.emit(self._project.path)
            event.accept()
            return
        super().mousePressEvent(event)

    def _on_remove_button(self, _pos) -> bool:
        # The "移除" button is a child QPushButton; Qt will deliver the press
        # to it directly. We never reach here for those clicks, but keep this
        # hook for future use.
        return False

    def _on_remove(self):
        self.remove_requested.emit(self._project.path)


class WelcomeView(QWidget):
    folder_selected = Signal(str)
    recent_remove_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet(f"background:{BG_MAIN};")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("SwiftCull")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:40px; font-weight:300; letter-spacing:8px;"
        )
        layout.addWidget(title)

        sub = QLabel("Photo Culling  ·  Local  ·  Fast")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:12px; letter-spacing:3px;"
        )
        layout.addWidget(sub)

        layout.addSpacing(24)

        drop_hint = QLabel("將資料夾拖放到此處")
        drop_hint.setAlignment(Qt.AlignCenter)
        drop_hint.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px;"
            f" border: 1px dashed #333; border-radius:8px;"
            f" padding: 28px 64px;"
        )
        layout.addWidget(drop_hint)

        layout.addSpacing(12)

        self._btn = QPushButton("開啟資料夾")
        self._btn.setFixedWidth(160)
        self._btn.setFixedHeight(36)
        self._btn.setStyleSheet(
            f"background:{ACCENT}; color:white; border:none; border-radius:4px;"
            f" font-size:13px; font-weight:500;"
            f" QPushButton:hover {{ background:#ff8c3a; }}"
        )
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._on_open_folder)

        btn_wrapper = QWidget()
        bw = QVBoxLayout(btn_wrapper)
        bw.setContentsMargins(0, 0, 0, 0)
        bw.addWidget(self._btn, alignment=Qt.AlignCenter)
        layout.addWidget(btn_wrapper)

        layout.addSpacing(20)

        # ---- recent projects ------------------------------------------------
        self._recent_header = QLabel("最近專案")
        self._recent_header.setAlignment(Qt.AlignCenter)
        self._recent_header.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:11px; letter-spacing:2px;"
        )
        layout.addWidget(self._recent_header)

        self._recent_scroll = QScrollArea()
        self._recent_scroll.setWidgetResizable(True)
        self._recent_scroll.setFrameShape(QFrame.NoFrame)
        self._recent_scroll.setStyleSheet("background:transparent;")
        self._recent_scroll.setMaximumHeight(220)
        self._recent_scroll.setMaximumWidth(560)

        self._recent_container = QWidget()
        self._recent_container.setStyleSheet("background:transparent;")
        self._recent_layout = QVBoxLayout(self._recent_container)
        self._recent_layout.setContentsMargins(0, 4, 0, 4)
        self._recent_layout.setSpacing(2)
        self._recent_layout.setAlignment(Qt.AlignTop)
        self._recent_scroll.setWidget(self._recent_container)

        recent_wrapper = QWidget()
        rw = QHBoxLayout(recent_wrapper)
        rw.setContentsMargins(0, 0, 0, 0)
        rw.addStretch()
        rw.addWidget(self._recent_scroll)
        rw.addStretch()
        layout.addWidget(recent_wrapper)

        self.set_recent_projects([])

    # --- public API --------------------------------------------------------

    def set_recent_projects(self, projects: List[RecentProject]):
        # Clear children
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not projects:
            self._recent_header.hide()
            self._recent_scroll.hide()
            return

        self._recent_header.show()
        self._recent_scroll.show()
        for project in projects:
            row = _RecentRow(project)
            row.clicked.connect(self.folder_selected)
            row.remove_requested.connect(self.recent_remove_requested)
            self._recent_layout.addWidget(row)

    # --- internal ----------------------------------------------------------

    def _on_open_folder(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "選擇照片資料夾")
        if folder:
            self.folder_selected.emit(folder)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.folder_selected.emit(path)
                break
