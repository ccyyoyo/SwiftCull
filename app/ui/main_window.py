import os
import json
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget

from app.ui.welcome_view import WelcomeView


def _settings_path() -> Path:
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    p = Path(app_data) / "SwiftCull"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def _load_settings() -> dict:
    try:
        return json.loads(_settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    try:
        _settings_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SwiftCull")
        self.resize(1280, 800)
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._welcome = WelcomeView()
        self._welcome.folder_selected.connect(self._on_folder_selected)
        self._stack.addWidget(self._welcome)
        self._stack.setCurrentWidget(self._welcome)

        self._import_ctrl = None
        self._scan_ctrl = None
        self._toast = None
        self._grid_view = None
        self._photo_repo = None
        self._folder_path: str = ""
        self._db_path: str = ""
        self._cache_dir: str = ""

        settings = _load_settings()
        last_folder = settings.get("last_folder", "")
        if last_folder and os.path.isdir(last_folder):
            self._load_folder(last_folder)

    def _on_folder_selected(self, folder_path: str):
        self._load_folder(folder_path)

    def _load_folder(self, folder_path: str):
        from app.db.connection import get_connection, init_db
        from app.db.photo_repository import PhotoRepository
        from app.db.tag_repository import TagRepository
        from app.core.thumbnail_service import ThumbnailService
        from app.core.tag_service import TagService
        from app.core.filter_service import FilterService
        from app.core.import_service import ImportService
        from app.ui.grid_view import GridView

        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        project_name = os.path.basename(folder_path)
        project_dir = os.path.join(local_app_data, "SwiftCull", "projects", project_name)
        os.makedirs(project_dir, exist_ok=True)
        db_path = os.path.join(project_dir, "project.db")
        cache_dir = os.path.join(project_dir, "cache")

        conn = get_connection(db_path)
        init_db(conn)
        photo_repo = PhotoRepository(conn)
        tag_repo = TagRepository(conn)
        thumb_svc = ThumbnailService(cache_dir)
        tag_svc = TagService(tag_repo)
        filter_svc = FilterService(photo_repo, tag_repo)

        _save_settings({"last_folder": folder_path})

        self._grid_view = GridView(
            folder_path, photo_repo, tag_repo,
            thumb_svc, tag_svc, filter_svc,
        )
        self._grid_view.refresh_requested.connect(self._on_refresh_requested)
        self._stack.addWidget(self._grid_view)
        self._stack.setCurrentWidget(self._grid_view)

        self._photo_repo = photo_repo
        self._folder_path = folder_path
        self._db_path = db_path
        self._cache_dir = cache_dir

        # Decide what to do on open:
        #   * Empty DB (first-time import) -> import everything immediately.
        #   * Non-empty DB (re-open) -> background scan, then toast if changes.
        if photo_repo.count() == 0:
            new_paths = ImportService().scan_folder(folder_path)
            if new_paths:
                self._start_import(new_paths=new_paths, modified_paths=[])
        else:
            self._start_scan()

    # ---- scan ----------------------------------------------------------

    def _start_scan(self):
        from app.core.scan_worker import ScanController
        if self._scan_ctrl is not None:
            return
        if not self._folder_path or not self._db_path:
            return
        self._dismiss_toast()
        self._scan_ctrl = ScanController(self._folder_path, self._db_path)
        self._scan_ctrl.finished.connect(self._on_scan_finished)
        self._scan_ctrl.start()

    def _on_scan_finished(self, result):
        self._scan_ctrl = None
        if self._grid_view is not None:
            self._grid_view.scan_finished()
        if result is None or not result.has_changes:
            return
        if self._grid_view is None:
            return
        from app.ui.toast import show_scan_toast
        new_paths = list(result.new_paths)
        modified_paths = list(result.modified_paths)
        self._dismiss_toast()
        self._toast = show_scan_toast(
            self._grid_view,
            len(new_paths),
            len(modified_paths),
            on_confirm=lambda: self._on_toast_confirmed(new_paths, modified_paths),
            on_dismiss=self._on_toast_dismissed,
        )

    def _dismiss_toast(self):
        if self._toast is not None:
            self._toast.hide()
            self._toast.deleteLater()
            self._toast = None

    def _on_toast_confirmed(self, new_paths, modified_paths):
        self._toast = None
        self._start_import(new_paths=new_paths, modified_paths=modified_paths)

    def _on_toast_dismissed(self):
        self._toast = None

    # ---- import --------------------------------------------------------

    def _start_import(self, new_paths: list, modified_paths: list):
        from app.core.import_worker import ImportController
        if self._import_ctrl is not None:
            return
        if self._grid_view is None or not self._folder_path or not self._db_path:
            return
        if not new_paths and not modified_paths:
            return
        self._grid_view.clear_import_errors()
        total = len(new_paths) + len(modified_paths)
        self._grid_view.begin_import(total)
        self._import_ctrl = ImportController(
            self._folder_path, self._db_path,
            new_paths=new_paths,
            modified_paths=modified_paths,
            cache_dir=self._cache_dir,
        )
        self._import_ctrl.photo_imported.connect(self._grid_view.on_photo_imported)
        self._import_ctrl.photo_updated.connect(self._on_photo_updated)
        self._import_ctrl.progress.connect(self._grid_view.update_import_progress)
        self._import_ctrl.error.connect(self._grid_view.add_import_error)
        self._import_ctrl.finished.connect(self._on_import_finished)
        self._import_ctrl.start()

    def _on_photo_updated(self, photo_id: int):
        if self._grid_view is not None:
            self._grid_view.on_photo_updated(photo_id)

    def _on_refresh_requested(self):
        # Manual "重新掃描" button: re-run the scan, but always notify (toast)
        # so the user keeps control over whether to import.
        self._start_scan()

    def _on_import_finished(self):
        if self._grid_view is not None:
            self._grid_view.end_import()
        self._import_ctrl = None

    def closeEvent(self, event):
        self._dismiss_toast()
        if self._scan_ctrl is not None:
            self._scan_ctrl.wait(2000)
        if self._import_ctrl is not None:
            self._import_ctrl.cancel()
            self._import_ctrl.wait(3000)
        super().closeEvent(event)
