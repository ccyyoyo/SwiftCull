from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.models import Photo, Tag

def _insert_photo(db_conn):
    repo = PhotoRepository(db_conn)
    return repo.insert(Photo(id=None, relative_path="x.jpg", filename="x.jpg", file_size=1))

def test_upsert_creates_tag(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    repo.upsert(Tag(photo_id=photo_id, status="pick"))
    tag = repo.get_by_photo_id(photo_id)
    assert tag.status == "pick"

def test_upsert_updates_existing(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    repo.upsert(Tag(photo_id=photo_id, status="pick"))
    repo.upsert(Tag(photo_id=photo_id, status="reject"))
    tag = repo.get_by_photo_id(photo_id)
    assert tag.status == "reject"

def test_get_by_photo_id_returns_none_if_missing(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    assert repo.get_by_photo_id(photo_id) is None
