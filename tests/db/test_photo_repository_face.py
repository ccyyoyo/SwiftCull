from app.db.photo_repository import PhotoRepository
from app.core.models import Photo


def test_face_fields_default_none_and_unanalyzed(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="a.jpg", filename="a.jpg", file_size=1))
    photo = repo.get_by_id(pid)
    assert photo.face_count is None
    assert photo.face_max_area is None
    assert photo.face_eyes_closed_count is None
    assert photo.face_analyzed is False


def test_update_face_result_sets_all_fields_and_flag(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="b.jpg", filename="b.jpg", file_size=1))
    repo.update_face_result(pid, face_count=2, face_max_area=0.15, face_eyes_closed_count=1)
    photo = repo.get_by_id(pid)
    assert photo.face_count == 2
    assert abs(photo.face_max_area - 0.15) < 0.001
    assert photo.face_eyes_closed_count == 1
    assert photo.face_analyzed is True


def test_update_face_result_zero_faces(db_conn):
    """A successful detection with 0 faces still marks as analyzed."""
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="c.jpg", filename="c.jpg", file_size=1))
    repo.update_face_result(pid, face_count=0, face_max_area=0.0, face_eyes_closed_count=0)
    photo = repo.get_by_id(pid)
    assert photo.face_count == 0
    assert photo.face_max_area == 0.0
    assert photo.face_eyes_closed_count == 0
    assert photo.face_analyzed is True


def test_mark_face_no_result_sets_analyzed_flag_only(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="d.jpg", filename="d.jpg", file_size=1))
    repo.mark_face_no_result(pid)
    photo = repo.get_by_id(pid)
    assert photo.face_count is None
    assert photo.face_max_area is None
    assert photo.face_eyes_closed_count is None
    assert photo.face_analyzed is True


def test_get_face_unanalyzed_ids_returns_only_unprocessed(db_conn):
    repo = PhotoRepository(db_conn)
    pid1 = repo.insert(Photo(id=None, relative_path="x.jpg", filename="x.jpg", file_size=1))
    pid2 = repo.insert(Photo(id=None, relative_path="y.jpg", filename="y.jpg", file_size=1))
    pid3 = repo.insert(Photo(id=None, relative_path="z.jpg", filename="z.jpg", file_size=1))
    repo.update_face_result(pid2, face_count=1, face_max_area=0.2, face_eyes_closed_count=0)
    repo.mark_face_no_result(pid3)
    result = repo.get_face_unanalyzed_ids()
    assert pid1 in result
    assert pid2 not in result
    assert pid3 not in result


def test_get_face_unanalyzed_ids_empty_when_all_analyzed(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="q.jpg", filename="q.jpg", file_size=1))
    repo.update_face_result(pid, face_count=0, face_max_area=0.0, face_eyes_closed_count=0)
    assert repo.get_face_unanalyzed_ids() == []


def test_clear_face_result_resets_for_reanalysis(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="e.jpg", filename="e.jpg", file_size=1))
    repo.update_face_result(pid, face_count=3, face_max_area=0.4, face_eyes_closed_count=2)
    repo.clear_face_result(pid)
    photo = repo.get_by_id(pid)
    assert photo.face_count is None
    assert photo.face_max_area is None
    assert photo.face_eyes_closed_count is None
    assert photo.face_analyzed is False
    # should appear again in unanalyzed list
    assert pid in repo.get_face_unanalyzed_ids()


def test_get_all_includes_face_fields(db_conn):
    repo = PhotoRepository(db_conn)
    pid = repo.insert(Photo(id=None, relative_path="r.jpg", filename="r.jpg", file_size=1))
    repo.update_face_result(pid, face_count=4, face_max_area=0.3, face_eyes_closed_count=1)
    photos = repo.get_all()
    match = next(p for p in photos if p.id == pid)
    assert match.face_count == 4
    assert abs(match.face_max_area - 0.3) < 0.001
    assert match.face_eyes_closed_count == 1
    assert match.face_analyzed is True
