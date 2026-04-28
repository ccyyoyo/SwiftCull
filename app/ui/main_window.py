import os
from PySide6.QtWidgets import QMainWindow, QStackedWidget
from app.ui.welcome_view import WelcomeView

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

        paths = import_svc.scan_folder(folder_path)
        for rel in paths:
            try:
                photo = import_svc.build_photo(folder_path, rel)
                photo_repo.insert(photo)
            except Exception:
                pass

        self._grid_view = GridView(
            folder_path, photo_repo, tag_repo,
            thumb_svc, tag_svc, filter_svc
        )
        self._stack.addWidget(self._grid_view)
        self._stack.setCurrentWidget(self._grid_view)
