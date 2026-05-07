from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.filter_service import FilterService
from app.core.models import Photo


def _insert_with_noise(repo, path, noise_score):
    pid = repo.insert(Photo(id=None, relative_path=path, filename=path, file_size=1))
    if noise_score is not None:
        repo.update_noise_score(pid, noise_score)
    return pid


def test_filter_noise_noisy(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_noisy = _insert_with_noise(repo, "noisy.jpg", 0.1)
    pid_clean = _insert_with_noise(repo, "clean.jpg", 1.5)

    results = svc.filter(noise=["noisy"], noise_fixed_threshold=0.5)
    ids = [p.id for p in results]
    assert pid_noisy in ids
    assert pid_clean not in ids


def test_filter_noise_clean(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_noisy = _insert_with_noise(repo, "noisy.jpg", 0.1)
    pid_clean = _insert_with_noise(repo, "clean.jpg", 1.5)

    results = svc.filter(noise=["clean"], noise_fixed_threshold=0.5)
    ids = [p.id for p in results]
    assert pid_clean in ids
    assert pid_noisy not in ids


def test_filter_noise_unanalyzed(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_none = _insert_with_noise(repo, "none.jpg", None)
    pid_scored = _insert_with_noise(repo, "scored.jpg", 0.8)

    results = svc.filter(noise=["unanalyzed"])
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_scored not in ids


def test_filter_noise_or_logic(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    pid_noisy = _insert_with_noise(repo, "noisy.jpg", 0.1)
    pid_clean = _insert_with_noise(repo, "clean.jpg", 1.5)

    results = svc.filter(noise=["noisy", "clean"], noise_fixed_threshold=0.5)
    ids = [p.id for p in results]
    assert pid_noisy in ids
    assert pid_clean in ids


def test_no_noise_filter_returns_all(db_conn):
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)

    _insert_with_noise(repo, "a.jpg", 0.1)
    _insert_with_noise(repo, "b.jpg", 1.5)
    _insert_with_noise(repo, "c.jpg", None)

    results = svc.filter()
    assert len(results) == 3
