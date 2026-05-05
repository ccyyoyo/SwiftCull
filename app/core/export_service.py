import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.core.models import Photo


@dataclass
class ExportResult:
    succeeded: int = 0
    failed: list = field(default_factory=list)  # list of (relative_path, reason)


class ExportService:
    def collect_by_status(
        self, photo_repo, tag_repo, statuses: List[Optional[str]]
    ) -> List[Photo]:
        """Return photos whose tag status is in `statuses`.
        Pass None in the list to include untagged photos.
        """
        all_photos = photo_repo.get_all()
        result = []
        for photo in all_photos:
            tag = tag_repo.get_by_photo_id(photo.id)
            status = tag.status if tag else None
            if status in statuses:
                result.append(photo)
        return result

    def execute(
        self,
        photos: List[Photo],
        src_root: str,
        dest_dir: str,
        mode: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> ExportResult:
        """Copy or move photos to dest_dir. mode must be 'copy' or 'move'.

        on_progress(done, total) is called before each file and once at the end.
        Duplicate filenames in dest_dir get a numeric suffix (_2, _3, …).
        """
        result = ExportResult()
        total = len(photos)
        os.makedirs(dest_dir, exist_ok=True)
        for i, photo in enumerate(photos):
            if on_progress:
                on_progress(i, total)
            src = os.path.join(src_root, photo.relative_path)
            dest_path = self._resolve_dest(dest_dir, photo.filename)
            try:
                if mode == "copy":
                    shutil.copy2(src, dest_path)
                else:
                    shutil.move(src, dest_path)
                result.succeeded += 1
            except Exception as exc:
                result.failed.append((photo.relative_path, str(exc)))
        if on_progress:
            on_progress(total, total)
        return result

    def _resolve_dest(self, dest_dir: str, filename: str) -> str:
        dest = os.path.join(dest_dir, filename)
        if not os.path.exists(dest):
            return dest
        name, ext = os.path.splitext(filename)
        i = 2
        while True:
            candidate = os.path.join(dest_dir, f"{name}_{i}{ext}")
            if not os.path.exists(candidate):
                return candidate
            i += 1
