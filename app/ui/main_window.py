import os
import json
from pathlib import Path
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
        _settings_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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

        # restore last session
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
        from app.core.import_service import ImportService
        from app.core.thumbnail_service import ThumbnailService
        from app.core.tag_service import TagService
        from app.core.filter_service import FilterService
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
        import_svc = ImportService()
        thumb_svc = ThumbnailService(cache_dir)
        tag_svc = TagService(tag_repo)
        filter_svc = FilterService(photo_repo, tag_repo)

        # import new files only (skip duplicates)
        paths = import_svc.scan_folder(folder_path)
        for rel in paths:
            try:
                photo = import_svc.build_photo(folder_path, rel)
                photo_repo.insert(photo)
            except Exception:
                pass  # duplicate relative_path — already imported

        _save_settings({"last_folder": folder_path})

        self._grid_view = GridView(
            folder_path, photo_repo, tag_repo,
            thumb_svc, tag_svc, filter_svc
        )
        self._stack.addWidget(self._grid_view)
        self._stack.setCurrentWidget(self._grid_view)
