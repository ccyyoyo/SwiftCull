from typing import List, Optional
from app.db.tag_repository import TagRepository
from app.core.models import Tag

VALID_STATUSES = {"pick", "reject", "maybe"}
VALID_COLORS = {"red", "orange", "yellow", "green", "blue", "purple"}

class TagService:
    def __init__(self, tag_repo: TagRepository):
        self._repo = tag_repo

    def set_status(self, photo_id: int, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        tag = self._repo.get_by_photo_id(photo_id) or Tag(photo_id=photo_id)
        tag.status = status
        self._repo.upsert(tag)

    def clear_status(self, photo_id: int) -> None:
        tag = self._repo.get_by_photo_id(photo_id) or Tag(photo_id=photo_id)
        tag.status = None
        self._repo.upsert(tag)

    def set_color(self, photo_id: int, color: Optional[str]) -> None:
        if color is not None and color not in VALID_COLORS:
            raise ValueError(f"Invalid color: {color!r}")
        tag = self._repo.get_by_photo_id(photo_id) or Tag(photo_id=photo_id)
        tag.color = color
        self._repo.upsert(tag)

    def batch_set_status(self, photo_ids: List[int], status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        for pid in photo_ids:
            tag = self._repo.get_by_photo_id(pid) or Tag(photo_id=pid)
            tag.status = status
            self._repo.upsert(tag)

    def batch_clear_status(self, photo_ids: List[int]) -> None:
        for pid in photo_ids:
            tag = self._repo.get_by_photo_id(pid) or Tag(photo_id=pid)
            tag.status = None
            self._repo.upsert(tag)
