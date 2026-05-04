import sqlite3
import pytest
from app.db.connection import init_db
from app.db.photo_repository import PhotoRepository
from app.core.models import Photo


def _make_repo(tmp_path):
    db_path = tmp_path / "project.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return PhotoRepository(conn), conn


def _insert_photo(repo, relative_path="a.jpg"):
    from datetime import datetime, timezone
    p = Photo(
        id=None, relative_path=relative_path, filename=relative_path,
        file_size=100, mtime=None, shot_at=None,
        imported_at=datetime.now(timezone.utc).isoformat(),
        width=None, height=None, camera_model=None, lens_model=None,
        iso=None, aperture=None, shutter_speed=None, focal_length=None,
        blur_score=None, exposure_mean=None, exposure_overexposed=None,
        exposure_underexposed=None,
    )
    return repo.insert(p)


def test_get_exposure_unanalyzed_ids_returns_all_when_no_scores(tmp_path):
    repo, _ = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    ids = repo.get_exposure_unanalyzed_ids()
    assert pid in ids


def test_get_exposure_unanalyzed_ids_excludes_analyzed(tmp_path):
    repo, _ = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    repo.update_exposure_scores(pid, 128.0, 0.0, 0.0)
    ids = repo.get_exposure_unanalyzed_ids()
    assert pid not in ids


def test_get_exposure_unanalyzed_ids_includes_partially_null(tmp_path):
    repo, conn = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    # Set only mean, leave over/under NULL
    conn.execute("UPDATE photos SET exposure_mean=128.0 WHERE id=?", (pid,))
    conn.commit()
    ids = repo.get_exposure_unanalyzed_ids()
    assert pid in ids


def test_clear_exposure_scores_sets_all_null(tmp_path):
    repo, _ = _make_repo(tmp_path)
    pid = _insert_photo(repo)
    repo.update_exposure_scores(pid, 128.0, 0.01, 0.02)
    repo.clear_exposure_scores(pid)
    photo = repo.get_by_id(pid)
    assert photo.exposure_mean is None
    assert photo.exposure_overexposed is None
    assert photo.exposure_underexposed is None
