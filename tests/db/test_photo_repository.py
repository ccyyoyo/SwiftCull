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
