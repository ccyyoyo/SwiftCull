import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from app.core.models import Photo

class PhotoRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(self, photo: Photo) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """INSERT INTO photos
               (relative_path, filename, file_size, shot_at, imported_at,
                width, height, camera_model, lens_model, iso, aperture,
                shutter_speed, focal_length)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (photo.relative_path, photo.filename, photo.file_size,
             photo.shot_at, now, photo.width, photo.height,
             photo.camera_model, photo.lens_model, photo.iso,
             photo.aperture, photo.shutter_speed, photo.focal_length)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_by_id(self, photo_id: int) -> Optional[Photo]:
        row = self._conn.execute(
            "SELECT * FROM photos WHERE id=?", (photo_id,)
        ).fetchone()
        return self._row_to_photo(row) if row else None

    def get_all(self) -> List[Photo]:
        rows = self._conn.execute(
            "SELECT * FROM photos ORDER BY shot_at, filename"
        ).fetchall()
        return [self._row_to_photo(r) for r in rows]

    def _row_to_photo(self, row) -> Photo:
        return Photo(
            id=row["id"],
            relative_path=row["relative_path"],
            filename=row["filename"],
            file_size=row["file_size"],
            shot_at=row["shot_at"],
            imported_at=row["imported_at"],
            width=row["width"],
            height=row["height"],
            camera_model=row["camera_model"],
            lens_model=row["lens_model"],
            iso=row["iso"],
            aperture=row["aperture"],
            shutter_speed=row["shutter_speed"],
            focal_length=row["focal_length"],
        )
