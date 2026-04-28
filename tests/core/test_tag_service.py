from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.tag_service import TagService
from app.core.models import Photo

def _insert_photo(db_conn):
    return PhotoRepository(db_conn).insert(
        Photo(id=None, relative_path="t.jpg", filename="t.jpg", file_size=1)
    )

def test_set_status_pick(db_conn):
    photo_id = _insert_photo(db_conn)
    svc = TagService(TagRepository(db_conn))
    svc.set_status(photo_id, "pick")
    tag = TagRepository(db_conn).get_by_photo_id(photo_id)
    assert tag.status == "pick"

def test_set_status_reject_clears_pick(db_conn):
    photo_id = _insert_photo(db_conn)
    svc = TagService(TagRepository(db_conn))
    svc.set_status(photo_id, "pick")
    svc.set_status(photo_id, "reject")
    tag = TagRepository(db_conn).get_by_photo_id(photo_id)
    assert tag.status == "reject"

def test_set_color(db_conn):
    photo_id = _insert_photo(db_conn)
    svc = TagService(TagRepository(db_conn))
    svc.set_color(photo_id, "red")
    tag = TagRepository(db_conn).get_by_photo_id(photo_id)
    assert tag.color == "red"

def test_set_status_invalid_raises(db_conn):
    import pytest
    photo_id = _insert_photo(db_conn)
    svc = TagService(TagRepository(db_conn))
    with pytest.raises(ValueError):
        svc.set_status(photo_id, "invalid")

def test_batch_set_status(db_conn):
    p_repo = PhotoRepository(db_conn)
    ids = [
        p_repo.insert(Photo(id=None, relative_path=f"b{i}.jpg", filename=f"b{i}.jpg", file_size=1))
        for i in range(3)
    ]
    svc = TagService(TagRepository(db_conn))
    svc.batch_set_status(ids, "maybe")
    t_repo = TagRepository(db_conn)
    for pid in ids:
        assert t_repo.get_by_photo_id(pid).status == "maybe"
