from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.filter_service import FilterService
from app.core.models import Photo


def _insert_with_skew(repo, path, skew):
    pid = repo.insert(Photo(id=None, relative_path=path, filename=path, file_size=1))
    if skew is not None:
        repo.update_horizon_skew(pid, skew)
    return pid


def test_filter_horizon_level(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_level = _insert_with_skew(repo, "level.jpg", 0.5)
    pid_tilted = _insert_with_skew(repo, "tilted.jpg", 5.0)
    pid_none = _insert_with_skew(repo, "none.jpg", None)

    results = svc.filter(horizon=["level"], horizon_skew_threshold=1.0)
    ids = [p.id for p in results]
    assert pid_level in ids
    assert pid_tilted not in ids
    assert pid_none not in ids


def test_filter_horizon_tilted(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_level = _insert_with_skew(repo, "level.jpg", 0.3)
    pid_tilted = _insert_with_skew(repo, "tilted.jpg", -4.0)
    pid_none = _insert_with_skew(repo, "none.jpg", None)

    results = svc.filter(horizon=["tilted"], horizon_skew_threshold=1.0)
    ids = [p.id for p in results]
    assert pid_tilted in ids
    assert pid_level not in ids
    assert pid_none not in ids


def test_filter_horizon_unanalyzed(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_level = _insert_with_skew(repo, "level.jpg", 0.0)
    pid_none = _insert_with_skew(repo, "none.jpg", None)

    results = svc.filter(horizon=["unanalyzed"])
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_level not in ids


def test_filter_horizon_or_logic(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_level = _insert_with_skew(repo, "level.jpg", 0.5)
    pid_tilted = _insert_with_skew(repo, "tilted.jpg", 3.0)
    pid_none = _insert_with_skew(repo, "none.jpg", None)

    results = svc.filter(horizon=["level", "tilted"], horizon_skew_threshold=1.0)
    ids = [p.id for p in results]
    assert pid_level in ids
    assert pid_tilted in ids
    assert pid_none not in ids


def test_filter_no_horizon_returns_all(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    _insert_with_skew(repo, "a.jpg", 0.0)
    _insert_with_skew(repo, "b.jpg", 5.0)
    _insert_with_skew(repo, "c.jpg", None)

    results = svc.filter()
    assert len(results) == 3


def test_filter_horizon_threshold_boundary(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_exact = _insert_with_skew(repo, "exact.jpg", 2.0)
    pid_over = _insert_with_skew(repo, "over.jpg", 2.1)

    results = svc.filter(horizon=["level"], horizon_skew_threshold=2.0)
    ids = [p.id for p in results]
    assert pid_exact in ids
    assert pid_over not in ids
