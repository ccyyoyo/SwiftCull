from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.filter_service import FilterService
from app.core.models import Photo


def _insert_with_face(repo, path, *, count=None, area=None, closed=None, analyzed=False):
    pid = repo.insert(Photo(id=None, relative_path=path, filename=path, file_size=1))
    if analyzed:
        repo.update_face_result(
            pid,
            face_count=count if count is not None else 0,
            face_max_area=area if area is not None else 0.0,
            face_eyes_closed_count=closed if closed is not None else 0,
        )
    return pid


def test_filter_face_has_face(db_conn):
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    pid_has = _insert_with_face(repo, "has.jpg", count=1, area=0.15, closed=0, analyzed=True)
    pid_none = _insert_with_face(repo, "none.jpg", count=0, area=0.0, closed=0, analyzed=True)
    pid_un = _insert_with_face(repo, "un.jpg", analyzed=False)

    results = svc.filter(face=["has_face"])
    ids = [p.id for p in results]
    assert pid_has in ids
    assert pid_none not in ids
    assert pid_un not in ids


def test_filter_face_no_face(db_conn):
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    pid_has = _insert_with_face(repo, "has.jpg", count=2, area=0.1, closed=0, analyzed=True)
    pid_none = _insert_with_face(repo, "none.jpg", count=0, area=0.0, closed=0, analyzed=True)
    pid_un = _insert_with_face(repo, "un.jpg", analyzed=False)

    results = svc.filter(face=["no_face"])
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_has not in ids
    assert pid_un not in ids


def test_filter_face_unanalyzed(db_conn):
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    pid_has = _insert_with_face(repo, "has.jpg", count=1, area=0.1, closed=0, analyzed=True)
    pid_un = _insert_with_face(repo, "un.jpg", analyzed=False)

    results = svc.filter(face=["unanalyzed"])
    ids = [p.id for p in results]
    assert pid_un in ids
    assert pid_has not in ids


def test_filter_face_eyes_closed(db_conn):
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    pid_open = _insert_with_face(repo, "open.jpg", count=1, area=0.1, closed=0, analyzed=True)
    pid_closed = _insert_with_face(repo, "closed.jpg", count=1, area=0.1, closed=1, analyzed=True)

    results = svc.filter(face=["eyes_closed"], eyes_closed_threshold=1)
    ids = [p.id for p in results]
    assert pid_closed in ids
    assert pid_open not in ids


def test_filter_face_or_logic(db_conn):
    """Selecting has_face + no_face returns both."""
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    pid_has = _insert_with_face(repo, "has.jpg", count=1, area=0.1, closed=0, analyzed=True)
    pid_none = _insert_with_face(repo, "none.jpg", count=0, area=0.0, closed=0, analyzed=True)
    pid_un = _insert_with_face(repo, "un.jpg", analyzed=False)

    results = svc.filter(face=["has_face", "no_face"])
    ids = [p.id for p in results]
    assert pid_has in ids
    assert pid_none in ids
    assert pid_un not in ids


def test_filter_face_eyes_closed_threshold(db_conn):
    """eyes_closed_threshold=2 requires at least 2 closed-eye faces."""
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    pid_one = _insert_with_face(repo, "one.jpg", count=3, area=0.1, closed=1, analyzed=True)
    pid_two = _insert_with_face(repo, "two.jpg", count=3, area=0.1, closed=2, analyzed=True)

    results = svc.filter(face=["eyes_closed"], eyes_closed_threshold=2)
    ids = [p.id for p in results]
    assert pid_two in ids
    assert pid_one not in ids


def test_filter_no_face_returns_all(db_conn):
    repo = PhotoRepository(db_conn)
    svc = FilterService(repo, TagRepository(db_conn))

    _insert_with_face(repo, "a.jpg", count=1, area=0.1, closed=0, analyzed=True)
    _insert_with_face(repo, "b.jpg", count=0, area=0.0, closed=0, analyzed=True)
    _insert_with_face(repo, "c.jpg", analyzed=False)

    results = svc.filter()
    assert len(results) == 3


def test_filter_face_combined_with_status(db_conn):
    """face filter composes with status filter via AND."""
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    from app.core.models import Tag

    pid_has_pick = _insert_with_face(repo, "p.jpg", count=1, area=0.1, closed=0, analyzed=True)
    pid_has_reject = _insert_with_face(repo, "r.jpg", count=1, area=0.1, closed=0, analyzed=True)
    pid_none_pick = _insert_with_face(repo, "np.jpg", count=0, area=0.0, closed=0, analyzed=True)

    tag_repo.upsert(Tag(photo_id=pid_has_pick, status="pick"))
    tag_repo.upsert(Tag(photo_id=pid_has_reject, status="reject"))
    tag_repo.upsert(Tag(photo_id=pid_none_pick, status="pick"))

    results = svc.filter(statuses=["pick"], face=["has_face"])
    ids = [p.id for p in results]
    assert pid_has_pick in ids
    assert pid_has_reject not in ids
    assert pid_none_pick not in ids
