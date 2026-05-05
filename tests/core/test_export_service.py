import os
import pytest
from app.core.export_service import ExportService
from app.core.models import Photo
from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository


def _make_photo(tmp_path, repo: PhotoRepository, filename: str, content: str = "data") -> Photo:
    """Write a real file and insert a Photo record. Returns the saved Photo."""
    abs_path = tmp_path / filename
    abs_path.write_text(content)
    photo = Photo(
        id=None,
        relative_path=filename,
        filename=filename,
        file_size=len(content),
    )
    photo_id = repo.insert(photo)
    return repo.get_by_id(photo_id)


class TestCollectByStatus:
    def test_pick_only(self, db_conn, tmp_path):
        repo = PhotoRepository(db_conn)
        tag_repo = TagRepository(db_conn)
        p1 = _make_photo(tmp_path, repo, "a.jpg")
        p2 = _make_photo(tmp_path, repo, "b.jpg")
        p3 = _make_photo(tmp_path, repo, "c.jpg")
        from app.core.tag_service import TagService
        svc = TagService(tag_repo)
        svc.set_status(p1.id, "pick")
        svc.set_status(p2.id, "reject")
        # p3 untagged

        result = ExportService().collect_by_status(repo, tag_repo, ["pick"])
        assert [p.id for p in result] == [p1.id]

    def test_multiple_statuses(self, db_conn, tmp_path):
        repo = PhotoRepository(db_conn)
        tag_repo = TagRepository(db_conn)
        p1 = _make_photo(tmp_path, repo, "a.jpg")
        p2 = _make_photo(tmp_path, repo, "b.jpg")
        p3 = _make_photo(tmp_path, repo, "c.jpg")
        from app.core.tag_service import TagService
        svc = TagService(tag_repo)
        svc.set_status(p1.id, "pick")
        svc.set_status(p2.id, "reject")

        result = ExportService().collect_by_status(repo, tag_repo, ["pick", "reject"])
        ids = {p.id for p in result}
        assert ids == {p1.id, p2.id}

    def test_untagged(self, db_conn, tmp_path):
        repo = PhotoRepository(db_conn)
        tag_repo = TagRepository(db_conn)
        p1 = _make_photo(tmp_path, repo, "a.jpg")
        p2 = _make_photo(tmp_path, repo, "b.jpg")
        from app.core.tag_service import TagService
        TagService(tag_repo).set_status(p1.id, "pick")

        result = ExportService().collect_by_status(repo, tag_repo, [None])
        assert [p.id for p in result] == [p2.id]

    def test_empty_statuses_returns_nothing(self, db_conn, tmp_path):
        repo = PhotoRepository(db_conn)
        tag_repo = TagRepository(db_conn)
        _make_photo(tmp_path, repo, "a.jpg")
        result = ExportService().collect_by_status(repo, tag_repo, [])
        assert result == []


class TestExecuteCopy:
    def test_copies_files(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        (src / "a.jpg").write_text("aaa")
        (src / "b.jpg").write_text("bbb")
        photos = [
            Photo(id=1, relative_path="a.jpg", filename="a.jpg", file_size=3),
            Photo(id=2, relative_path="b.jpg", filename="b.jpg", file_size=3),
        ]
        result = ExportService().execute(photos, str(src), str(dest), "copy")
        assert result.succeeded == 2
        assert result.failed == []
        assert (dest / "a.jpg").read_text() == "aaa"
        assert (dest / "b.jpg").read_text() == "bbb"
        # originals still exist
        assert (src / "a.jpg").exists()

    def test_duplicate_filename_gets_suffix(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "a.jpg").write_text("new")
        (dest / "a.jpg").write_text("existing")
        photos = [Photo(id=1, relative_path="a.jpg", filename="a.jpg", file_size=3)]
        result = ExportService().execute(photos, str(src), str(dest), "copy")
        assert result.succeeded == 1
        assert (dest / "a_2.jpg").read_text() == "new"

    def test_creates_dest_dir(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "x.jpg").write_text("x")
        dest = tmp_path / "new" / "nested"
        photos = [Photo(id=1, relative_path="x.jpg", filename="x.jpg", file_size=1)]
        ExportService().execute(photos, str(src), str(dest), "copy")
        assert (dest / "x.jpg").exists()

    def test_failed_file_recorded(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        # no actual file on disk — copy should fail
        photos = [Photo(id=1, relative_path="missing.jpg", filename="missing.jpg", file_size=0)]
        result = ExportService().execute(photos, str(src), str(dest), "copy")
        assert result.succeeded == 0
        assert len(result.failed) == 1
        assert result.failed[0][0] == "missing.jpg"


class TestExecuteMove:
    def test_moves_files(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        (src / "a.jpg").write_text("aaa")
        photos = [Photo(id=1, relative_path="a.jpg", filename="a.jpg", file_size=3)]
        result = ExportService().execute(photos, str(src), str(dest), "move")
        assert result.succeeded == 1
        assert (dest / "a.jpg").read_text() == "aaa"
        assert not (src / "a.jpg").exists()


class TestProgressCallback:
    def test_progress_called(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        for name in ("a.jpg", "b.jpg", "c.jpg"):
            (src / name).write_text("x")
        photos = [
            Photo(id=i, relative_path=n, filename=n, file_size=1)
            for i, n in enumerate(["a.jpg", "b.jpg", "c.jpg"], 1)
        ]
        calls = []
        ExportService().execute(photos, str(src), str(dest), "copy",
                                on_progress=lambda d, t: calls.append((d, t)))
        # first call is (0, 3), last call is (3, 3)
        assert calls[0] == (0, 3)
        assert calls[-1] == (3, 3)
