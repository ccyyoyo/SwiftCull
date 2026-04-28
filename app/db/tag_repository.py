import sqlite3
from datetime import datetime, timezone
from typing import Optional
from app.core.models import Tag

class TagRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert(self, tag: Tag) -> None:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_by_photo_id(tag.photo_id)
        if existing is None:
            self._conn.execute(
                "INSERT INTO tags (photo_id, status, color, updated_at) VALUES (?,?,?,?)",
                (tag.photo_id, tag.status, tag.color, now)
            )
        else:
            self._conn.execute(
                "UPDATE tags SET status=?, color=?, updated_at=? WHERE photo_id=?",
                (tag.status if tag.status is not None else existing.status,
                 tag.color if tag.color is not None else existing.color,
                 now, tag.photo_id)
            )
        self._conn.commit()

    def get_by_photo_id(self, photo_id: int) -> Optional[Tag]:
        row = self._conn.execute(
            "SELECT * FROM tags WHERE photo_id=?", (photo_id,)
        ).fetchone()
        if row is None:
            return None
        return Tag(
            id=row["id"],
            photo_id=row["photo_id"],
            status=row["status"],
            color=row["color"],
            updated_at=row["updated_at"],
        )
