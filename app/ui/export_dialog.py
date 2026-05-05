from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QCheckBox,
    QVBoxLayout,
)

from app.core.export_service import ExportResult, ExportService
from app.core.models import Photo
from app.utils.theme import MAYBE_CLR, PICK_CLR, TEXT_SECONDARY


class _ExportWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(object)  # ExportResult

    def __init__(self, photos, src_root, dest_dir, mode, parent=None):
        super().__init__(parent)
        self._photos = photos
        self._src_root = src_root
        self._dest_dir = dest_dir
        self._mode = mode

    def run(self):
        svc = ExportService()
        result = svc.execute(
            self._photos,
            self._src_root,
            self._dest_dir,
            self._mode,
            on_progress=lambda done, total: self.progress.emit(done, total),
        )
        self.finished.emit(result)


class ExportDialog(QDialog):
    def __init__(self, folder_path: str, photo_repo, tag_repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("匯出照片")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._folder = folder_path
        self._photo_repo = photo_repo
        self._tag_repo = tag_repo
        self._worker: Optional[_ExportWorker] = None
        self._photos: List[Photo] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ---- status checkboxes ----
        status_group = QGroupBox("匯出哪些照片")
        sg = QHBoxLayout(status_group)
        self._chk_pick = QCheckBox("Pick")
        self._chk_pick.setObjectName("export_pick_checkbox")
        self._chk_pick.setChecked(True)
        self._chk_reject = QCheckBox("Reject")
        self._chk_reject.setObjectName("export_reject_checkbox")
        self._chk_maybe = QCheckBox("Maybe")
        self._chk_maybe.setObjectName("export_maybe_checkbox")
        self._chk_none = QCheckBox("未標記")
        self._chk_none.setObjectName("export_untagged_checkbox")
        for chk in (self._chk_pick, self._chk_reject, self._chk_maybe, self._chk_none):
            chk.stateChanged.connect(self._update_count)
            sg.addWidget(chk)
        sg.addStretch()
        layout.addWidget(status_group)

        # ---- mode ----
        mode_group = QGroupBox("操作")
        mg = QHBoxLayout(mode_group)
        self._radio_copy = QRadioButton("複製")
        self._radio_copy.setChecked(True)
        self._radio_move = QRadioButton("移動")
        self._btn_grp = QButtonGroup(self)
        self._btn_grp.addButton(self._radio_copy)
        self._btn_grp.addButton(self._radio_move)
        for r in (self._radio_copy, self._radio_move):
            r.toggled.connect(self._update_count)
            mg.addWidget(r)
        mg.addStretch()
        layout.addWidget(mode_group)

        # ---- destination ----
        dest_group = QGroupBox("目標資料夾")
        dg = QHBoxLayout(dest_group)
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("選擇目標資料夾…")
        self._dest_edit.setObjectName("export_destination_input")
        self._dest_edit.textChanged.connect(self._update_count)
        browse_btn = QPushButton("瀏覽")
        browse_btn.setObjectName("export_browse_button")
        browse_btn.setFixedWidth(60)
        browse_btn.clicked.connect(self._browse)
        dg.addWidget(self._dest_edit)
        dg.addWidget(browse_btn)
        layout.addWidget(dest_group)

        # ---- count label ----
        self._count_label = QLabel("")
        self._count_label.setObjectName("export_count_label")
        self._count_label.setAlignment(Qt.AlignCenter)
        self._count_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:11px;")
        layout.addWidget(self._count_label)

        # ---- progress bar (hidden until running) ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # ---- result label (hidden until done) ----
        self._result_label = QLabel("")
        self._result_label.setObjectName("export_result_label")
        self._result_label.setAlignment(Qt.AlignCenter)
        self._result_label.hide()
        layout.addWidget(self._result_label)

        # ---- action buttons ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("export_cancel_button")
        self._cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton("開始匯出")
        self._ok_btn.setObjectName("export_start_button")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._start_export)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._ok_btn)
        layout.addLayout(btn_row)

        self._update_count()

    # ------------------------------------------------------------------

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇目標資料夾", "")
        if folder:
            self._dest_edit.setText(folder)

    def _selected_statuses(self) -> List[Optional[str]]:
        statuses: List[Optional[str]] = []
        if self._chk_pick.isChecked():
            statuses.append("pick")
        if self._chk_reject.isChecked():
            statuses.append("reject")
        if self._chk_maybe.isChecked():
            statuses.append("maybe")
        if self._chk_none.isChecked():
            statuses.append(None)
        return statuses

    def _update_count(self):
        statuses = self._selected_statuses()
        if not statuses:
            self._count_label.setText("請選擇至少一個狀態")
            self._ok_btn.setEnabled(False)
            return
        svc = ExportService()
        self._photos = svc.collect_by_status(self._photo_repo, self._tag_repo, statuses)
        n = len(self._photos)
        mode_word = "複製" if self._radio_copy.isChecked() else "移動"
        self._count_label.setText(f"共 {n} 張照片將被{mode_word}")
        dest = self._dest_edit.text().strip()
        self._ok_btn.setEnabled(n > 0 and bool(dest))

    def _start_export(self):
        dest = self._dest_edit.text().strip()
        if not dest or not self._photos:
            return

        mode = "copy" if self._radio_copy.isChecked() else "move"

        if mode == "move":
            box = QMessageBox(self)
            box.setWindowTitle("確認移動")
            box.setIcon(QMessageBox.Warning)
            box.setText(
                f"確定將 {len(self._photos)} 張照片移動到目標資料夾？\n"
                "原始位置的檔案將被移走。"
            )
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText("確認移動")
            box.button(QMessageBox.No).setText("取消")
            box.setDefaultButton(QMessageBox.No)
            if box.exec() != QMessageBox.Yes:
                return

        self._ok_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setRange(0, len(self._photos))
        self._progress_bar.setValue(0)
        self._progress_bar.show()

        self._worker = _ExportWorker(self._photos, self._folder, dest, mode, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int):
        self._progress_bar.setValue(done)

    def _on_finished(self, result: ExportResult):
        self._worker = None
        self._progress_bar.hide()
        mode_word = "複製" if self._radio_copy.isChecked() else "移動"
        n_ok = result.succeeded
        n_fail = len(result.failed)
        if n_fail == 0:
            msg = f"完成：{n_ok} 張已{mode_word}"
            color = PICK_CLR
        else:
            msg = f"完成：{n_ok} 張已{mode_word}，{n_fail} 張失敗"
            color = MAYBE_CLR
        self._result_label.setStyleSheet(f"color:{color}; font-size:11px;")
        self._result_label.setText(msg)
        self._result_label.show()
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("關閉")
        self._ok_btn.hide()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
        super().closeEvent(event)
