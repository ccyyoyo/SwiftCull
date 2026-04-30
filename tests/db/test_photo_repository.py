from app.db.photo_repository import PhotoRepository
from app.core.models import Photo

def test_insert_and_get_by_id(db_conn):
    repo = PhotoRepository(db_conn)
    photo = Photo(id=None, relative_path="a/b.jpg", filename="b.jpg", file_size=100)
    photo_id = repo.insert(photo)
    result = repo.get_by_id(photo_id)
    assert result.relative_path == "a/b.jpg"
    assert result.id == photo_id

def test_get_all_returns_inserted(db_conn):
    repo = PhotoRepository(db_conn)
    repo.insert(Photo(id=None, relative_path="p1.jpg", filename="p1.jpg", file_size=10))
    repo.insert(Photo(id=None, relative_path="p2.jpg", filename="p2.jpg", file_size=20))
    results = repo.get_all()
    assert len(results) == 2

def test_insert_duplicate_path_raises(db_conn):
    import pytest as pt
    repo = PhotoRepository(db_conn)
    repo.insert(Photo(id=None, relative_path="dup.jpg", filename="dup.jpg", file_size=1))
    with pt.raises(Exception):
        repo.insert(Photo(id=None, relative_path="dup.jpg", filename="dup.jpg", file_size=1))

def test_get_id_by_relative_path(db_conn):
    repo = PhotoRepository(db_conn)
    photo_id = repo.insert(Photo(id=None, relative_path="x/y.jpg", filename="y.jpg", file_size=1))
    assert repo.get_id_by_relative_path("x/y.jpg") == photo_id
    assert repo.get_id_by_relative_path("missing.jpg") is None

def test_update_metadata_sets_fields(db_conn):
    repo = PhotoRepository(db_conn)
    photo_id = repo.insert(Photo(id=None, relative_path="m.jpg", filename="m.jpg", file_size=1))
    repo.update_metadata(photo_id, {
        "width": 1920,
        "height": 1080,
        "iso": 400,
        "camera_model": "Sony A7",
        "shot_at": "2024:01:01 12:00:00",
        "ignored_field": "should not crash",
    })
    photo = repo.get_by_id(photo_id)
    assert photo.width == 1920
    assert photo.height == 1080
    assert photo.iso == 400
    assert photo.camera_model == "Sony A7"
    assert photo.shot_at == "2024:01:01 12:00:00"

def test_update_metadata_partial_keeps_others(db_conn):
    repo = PhotoRepository(db_conn)
    photo_id = repo.insert(Photo(id=None, relative_path="p.jpg", filename="p.jpg", file_size=1,
                                  iso=200, width=100, height=200))
    repo.update_metadata(photo_id, {"iso": 800})
    photo = repo.get_by_id(photo_id)
    assert photo.iso == 800
    assert photo.width == 100
    assert photo.height == 200

def test_update_metadata_empty_is_noop(db_conn):
    repo = PhotoRepository(db_conn)
    photo_id = repo.insert(Photo(id=None, relative_path="n.jpg", filename="n.jpg", file_size=1))
    repo.update_metadata(photo_id, {})
    repo.update_metadata(photo_id, {"unknown": 1})

def test_count_returns_row_total(db_conn):
    repo = PhotoRepository(db_conn)
    assert repo.count() == 0
    for i in range(5):
        repo.insert(Photo(id=None, relative_path=f"c{i}.jpg",
                          filename=f"c{i}.jpg", file_size=1))
    assert repo.count() == 5

def test_update_blur_score(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.core.models import Photo
    repo = PhotoRepository(db_conn)
    photo = Photo(id=None, relative_path="a.jpg", filename="a.jpg", file_size=100)
    pid = repo.insert(photo)
    repo.update_blur_score(pid, 42.5)
    p = repo.get_by_id(pid)
    assert abs(p.blur_score - 42.5) < 0.001

def test_blur_score_defaults_none(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.core.models import Photo
    repo = PhotoRepository(db_conn)
    photo = Photo(id=None, relative_path="b.jpg", filename="b.jpg", file_size=100)
    pid = repo.insert(photo)
    p = repo.get_by_id(pid)
    assert p.blur_score is None


def test_insert_persists_mtime(db_conn):
    repo = PhotoRepository(db_conn)
    photo_id = repo.insert(Photo(
        id=None, relative_path="t.jpg", filename="t.jpg",
        file_size=1, mtime=1700000000.5,
    ))
    photo = repo.get_by_id(photo_id)
    assert photo.mtime == 1700000000.5


def test_update_metadata_can_update_mtime_and_size(db_conn):
    repo = PhotoRepository(db_conn)
    photo_id = repo.insert(Photo(
        id=None, relative_path="u.jpg", filename="u.jpg",
        file_size=1, mtime=1.0,
    ))
    repo.update_metadata(photo_id, {"mtime": 2.0, "file_size": 999})
    photo = repo.get_by_id(photo_id)
    assert photo.mtime == 2.0
    assert photo.file_size == 999


def test_get_path_mtime_map(db_conn):
    repo = PhotoRepository(db_conn)
    repo.insert(Photo(id=None, relative_path="m1.jpg", filename="m1.jpg",
                      file_size=1, mtime=10.0))
    repo.insert(Photo(id=None, relative_path="m2.jpg", filename="m2.jpg",
                      file_size=1, mtime=20.0))
    repo.insert(Photo(id=None, relative_path="m3.jpg", filename="m3.jpg",
                      file_size=1))  # mtime defaults to None
    m = repo.get_path_mtime_map()
    assert m == {"m1.jpg": 10.0, "m2.jpg": 20.0, "m3.jpg": None}


def test_get_path_mtime_map_empty_db(db_conn):
    repo = PhotoRepository(db_conn)
    assert repo.get_path_mtime_map() == {}
