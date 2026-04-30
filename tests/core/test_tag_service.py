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


def test_clear_status_actually_clears(db_conn):
    """Regression: TagRepository.upsert used to keep the prior status when
    asked to write None, making clear_status a silent no-op."""
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.set_status(photo_id, "pick")
    assert repo.get_by_photo_id(photo_id).status == "pick"

    svc.clear_status(photo_id)
    tag = repo.get_by_photo_id(photo_id)
    assert tag.status is None


def test_clear_status_preserves_color(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.set_color(photo_id, "red")
    svc.set_status(photo_id, "pick")

    svc.clear_status(photo_id)
    tag = repo.get_by_photo_id(photo_id)
    assert tag.status is None
    assert tag.color == "red"


def test_set_status_preserves_color(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.set_color(photo_id, "blue")
    svc.set_status(photo_id, "maybe")
    tag = repo.get_by_photo_id(photo_id)
    assert tag.status == "maybe"
    assert tag.color == "blue"


def test_set_color_preserves_status(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.set_status(photo_id, "reject")
    svc.set_color(photo_id, "yellow")
    tag = repo.get_by_photo_id(photo_id)
    assert tag.status == "reject"
    assert tag.color == "yellow"


def test_set_color_to_none_clears_color(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.set_color(photo_id, "green")
    assert repo.get_by_photo_id(photo_id).color == "green"

    svc.set_color(photo_id, None)
    tag = repo.get_by_photo_id(photo_id)
    assert tag.color is None


def test_batch_clear_status(db_conn):
    p_repo = PhotoRepository(db_conn)
    ids = [
        p_repo.insert(Photo(id=None, relative_path=f"bc{i}.jpg",
                            filename=f"bc{i}.jpg", file_size=1))
        for i in range(3)
    ]
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.batch_set_status(ids, "pick")
    svc.set_color(ids[0], "purple")

    svc.batch_clear_status(ids)
    for pid in ids:
        assert repo.get_by_photo_id(pid).status is None
    # color on the first one must survive a status-only clear
    assert repo.get_by_photo_id(ids[0]).color == "purple"


def test_batch_clear_status_creates_row_when_missing(db_conn):
    photo_id = _insert_photo(db_conn)
    repo = TagRepository(db_conn)
    svc = TagService(repo)
    svc.batch_clear_status([photo_id])
    tag = repo.get_by_photo_id(photo_id)
    assert tag is not None
    assert tag.status is None and tag.color is None
