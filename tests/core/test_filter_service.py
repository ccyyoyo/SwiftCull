from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.tag_service import TagService
from app.core.filter_service import FilterService
from app.core.models import Photo

def _insert_photo(db_conn, rel_path):
    return PhotoRepository(db_conn).insert(
        Photo(id=None, relative_path=rel_path, filename=rel_path, file_size=1)
    )

def test_filter_by_status_pick(db_conn):
    p1 = _insert_photo(db_conn, "f1.jpg")
    p2 = _insert_photo(db_conn, "f2.jpg")
    p3 = _insert_photo(db_conn, "f3.jpg")
    tag_svc = TagService(TagRepository(db_conn))
    tag_svc.set_status(p1, "pick")
    tag_svc.set_status(p2, "reject")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter(statuses=["pick"])
    ids = {p.id for p in result}
    assert p1 in ids
    assert p2 not in ids
    assert p3 not in ids

def test_filter_untagged_returns_no_tag_photos(db_conn):
    p1 = _insert_photo(db_conn, "u1.jpg")
    p2 = _insert_photo(db_conn, "u2.jpg")
    TagService(TagRepository(db_conn)).set_status(p2, "pick")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter(statuses=["untagged"])
    ids = {p.id for p in result}
    assert p1 in ids
    assert p2 not in ids

def test_filter_by_color(db_conn):
    p1 = _insert_photo(db_conn, "c1.jpg")
    p2 = _insert_photo(db_conn, "c2.jpg")
    TagService(TagRepository(db_conn)).set_color(p1, "red")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter(colors=["red"])
    ids = {p.id for p in result}
    assert p1 in ids
    assert p2 not in ids

def test_no_filter_returns_all(db_conn):
    for i in range(3):
        _insert_photo(db_conn, f"all{i}.jpg")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter()
    assert len(result) == 3
