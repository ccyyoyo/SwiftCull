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
               (relative_path, filename, file_size, mtime, shot_at, imported_at,
                width, height, camera_model, lens_model, iso, aperture,
                shutter_speed, focal_length)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (photo.relative_path, photo.filename, photo.file_size, photo.mtime,
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

    def get_id_by_relative_path(self, relative_path: str) -> Optional[int]:
        row = self._conn.execute(
            "SELECT id FROM photos WHERE relative_path=?", (relative_path,)
        ).fetchone()
        return int(row["id"]) if row else None

    def update_metadata(self, photo_id: int, fields: dict) -> None:
        """Partial UPDATE of EXIF/dimension/file fields. Ignores unknown columns."""
        allowed = {
            "shot_at", "width", "height", "camera_model", "lens_model",
            "iso", "aperture", "shutter_speed", "focal_length",
            "file_size", "mtime",
        }
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        cols = ", ".join(f"{k}=?" for k in clean)
        self._conn.execute(
            f"UPDATE photos SET {cols} WHERE id=?",
            (*clean.values(), photo_id),
        )
        self._conn.commit()

    def update_blur_score(self, photo_id: int, score: float) -> None:
        self._conn.execute(
            "UPDATE photos SET blur_score=? WHERE id=?", (score, photo_id)
        )
        self._conn.commit()

    def update_exposure_scores(
        self,
        photo_id: int,
        mean_brightness: float,
        overexposed_fraction: float,
        underexposed_fraction: float,
    ) -> None:
        self._conn.execute(
            "UPDATE photos SET exposure_mean=?, exposure_overexposed=?, exposure_underexposed=? WHERE id=?",
            (mean_brightness, overexposed_fraction, underexposed_fraction, photo_id),
        )
        self._conn.commit()

    def update_noise_score(self, photo_id: int, score: float) -> None:
        self._conn.execute(
            "UPDATE photos SET noise_score=? WHERE id=?", (score, photo_id)
        )
        self._conn.commit()

    def get_noise_unanalyzed_ids(self) -> list[int]:
        """Return IDs of photos where noise_score IS NULL."""
        rows = self._conn.execute(
            "SELECT id FROM photos WHERE noise_score IS NULL"
        ).fetchall()
        return [int(r["id"]) for r in rows]

    def get_path_mtime_map(self) -> dict[str, Optional[float]]:
        """Cheap fetch for scan comparisons: relative_path -> mtime."""
        rows = self._conn.execute(
            "SELECT relative_path, mtime FROM photos"
        ).fetchall()
        return {r["relative_path"]: r["mtime"] for r in rows}

    def get_unanalyzed_ids(self) -> list[int]:
        """Return IDs of photos where blur_score IS NULL."""
        rows = self._conn.execute(
            "SELECT id FROM photos WHERE blur_score IS NULL"
        ).fetchall()
        return [int(r["id"]) for r in rows]

    def get_exposure_unanalyzed_ids(self) -> list[int]:
        """Return IDs where any exposure analysis field is NULL."""
        rows = self._conn.execute(
            "SELECT id FROM photos WHERE exposure_mean IS NULL"
            " OR exposure_overexposed IS NULL"
            " OR exposure_underexposed IS NULL"
        ).fetchall()
        return [int(r["id"]) for r in rows]

    def update_phash_hash(self, photo_id: int, hash_str: str) -> None:
        self._conn.execute(
            "UPDATE photos SET phash_hash=? WHERE id=?", (hash_str, photo_id)
        )
        self._conn.commit()

    def get_phash_unanalyzed_ids(self) -> list[int]:
        """Return IDs where phash_hash IS NULL."""
        rows = self._conn.execute(
            "SELECT id FROM photos WHERE phash_hash IS NULL"
        ).fetchall()
        return [int(r["id"]) for r in rows]

    def get_all_phash_hashes(self) -> dict[int, str]:
        """Return {photo_id: hash_str} for all photos that have a pHash."""
        rows = self._conn.execute(
            "SELECT id, phash_hash FROM photos WHERE phash_hash IS NOT NULL"
        ).fetchall()
        return {int(r["id"]): r["phash_hash"] for r in rows}

    def update_horizon_skew(self, photo_id: int, skew_angle: float) -> None:
        self._conn.execute(
            "UPDATE photos SET horizon_skew=?, horizon_analyzed=1 WHERE id=?",
            (skew_angle, photo_id),
        )
        self._conn.commit()

    def mark_horizon_no_result(self, photo_id: int) -> None:
        """Mark photo as analyzed even though no horizon line was found.
        Prevents re-processing on every button click."""
        self._conn.execute(
            "UPDATE photos SET horizon_analyzed=1 WHERE id=?", (photo_id,)
        )
        self._conn.commit()

    def get_horizon_unanalyzed_ids(self) -> list[int]:
        """Return IDs of photos not yet attempted for horizon analysis."""
        rows = self._conn.execute(
            "SELECT id FROM photos WHERE horizon_analyzed = 0"
        ).fetchall()
        return [int(r["id"]) for r in rows]

    def clear_horizon_skew(self, photo_id: int) -> None:
        """Reset horizon analysis so the photo will be re-processed."""
        self._conn.execute(
            "UPDATE photos SET horizon_skew=NULL, horizon_analyzed=0 WHERE id=?",
            (photo_id,),
        )
        self._conn.commit()

    def clear_exposure_scores(self, photo_id: int) -> None:
        """Clear stored exposure fields so the photo will be re-analyzed."""
        self._conn.execute(
            "UPDATE photos SET exposure_mean=NULL, exposure_overexposed=NULL,"
            " exposure_underexposed=NULL WHERE id=?",
            (photo_id,),
        )
        self._conn.commit()

    def get_all(self) -> List[Photo]:
        rows = self._conn.execute(
            "SELECT * FROM photos ORDER BY shot_at, filename"
        ).fetchall()
        return [self._row_to_photo(r) for r in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM photos").fetchone()
        return int(row["n"]) if row else 0

    def _row_to_photo(self, row) -> Photo:
        keys = row.keys()
        return Photo(
            id=row["id"],
            relative_path=row["relative_path"],
            filename=row["filename"],
            file_size=row["file_size"],
            mtime=row["mtime"] if "mtime" in keys else None,
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
            blur_score=row["blur_score"] if "blur_score" in row.keys() else None,
            exposure_mean=row["exposure_mean"] if "exposure_mean" in row.keys() else None,
            exposure_overexposed=row["exposure_overexposed"] if "exposure_overexposed" in row.keys() else None,
            exposure_underexposed=row["exposure_underexposed"] if "exposure_underexposed" in row.keys() else None,
            phash_hash=row["phash_hash"] if "phash_hash" in row.keys() else None,
            noise_score=row["noise_score"] if "noise_score" in row.keys() else None,
            horizon_skew=row["horizon_skew"] if "horizon_skew" in row.keys() else None,
            horizon_analyzed=bool(row["horizon_analyzed"]) if "horizon_analyzed" in row.keys() else False,
        )
