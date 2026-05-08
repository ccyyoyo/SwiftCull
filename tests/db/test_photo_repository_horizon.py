from app.db.photo_repository import PhotoRepository
from app.core.models import Photo


def test_horizon_skew_defaults_none(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="a.jpg", filename="a.jpg", file_size=1))
    photo = repo.get_by_id(pid)
    assert photo.horizon_skew is None
    assert photo.horizon_analyzed is False


def test_update_horizon_skew(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="b.jpg", filename="b.jpg", file_size=1))
    repo.update_horizon_skew(pid, 3.7)
    photo = repo.get_by_id(pid)
    assert abs(photo.horizon_skew - 3.7) < 0.001
    assert photo.horizon_analyzed is True


def test_update_horizon_skew_negative(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="c.jpg", filename="c.jpg", file_size=1))
    repo.update_horizon_skew(pid, -8.5)
    photo = repo.get_by_id(pid)
    assert abs(photo.horizon_skew - (-8.5)) < 0.001
    assert photo.horizon_analyzed is True


def test_mark_horizon_no_result_sets_analyzed_flag(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="d.jpg", filename="d.jpg", file_size=1))
    repo.mark_horizon_no_result(pid)
    photo = repo.get_by_id(pid)
    assert photo.horizon_skew is None
    assert photo.horizon_analyzed is True


def test_get_horizon_unanalyzed_ids_returns_only_unprocessed(db_conn):
    repo = PhotoRepository(db_conn)
    pid1 = repo.insert(Photo(id=None, relative_path="x.jpg", filename="x.jpg", file_size=1))
    pid2 = repo.insert(Photo(id=None, relative_path="y.jpg", filename="y.jpg", file_size=1))
    pid3 = repo.insert(Photo(id=None, relative_path="z.jpg", filename="z.jpg", file_size=1))
    repo.update_horizon_skew(pid2, 1.5)       # analyzed + has skew
    repo.mark_horizon_no_result(pid3)         # analyzed + no skew
    result = repo.get_horizon_unanalyzed_ids()
    assert pid1 in result
    assert pid2 not in result
    assert pid3 not in result


def test_get_horizon_unanalyzed_ids_empty_when_all_analyzed(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="q.jpg", filename="q.jpg", file_size=1))
    repo.update_horizon_skew(pid, 0.0)
    assert repo.get_horizon_unanalyzed_ids() == []


def test_clear_horizon_skew_resets_for_reanalysis(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="e.jpg", filename="e.jpg", file_size=1))
    repo.update_horizon_skew(pid, 5.0)
    repo.clear_horizon_skew(pid)
    photo = repo.get_by_id(pid)
    assert photo.horizon_skew is None
    assert photo.horizon_analyzed is False
    # should appear again in unanalyzed list
    assert pid in repo.get_horizon_unanalyzed_ids()


def test_get_all_includes_horizon_skew(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="r.jpg", filename="r.jpg", file_size=1))
    repo.update_horizon_skew(pid, 2.2)
    photos = repo.get_all()
    match = next(p for p in photos if p.id == pid)
    assert abs(match.horizon_skew - 2.2) < 0.001
    assert match.horizon_analyzed is True
