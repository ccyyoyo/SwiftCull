import os

from PIL import Image

from app.core.scan_service import ScanService, ScanResult


def _make_jpeg(path):
    Image.new("RGB", (40, 30), color=(0, 0, 0)).save(str(path), "JPEG")


def test_empty_folder_empty_db_returns_no_changes(tmp_path):
    svc = ScanService()
    result = svc.scan(str(tmp_path), {})
    assert result.new_paths == []
    assert result.modified_paths == []
    assert result.has_changes is False


def test_new_files_detected_when_db_is_empty(tmp_path):
    _make_jpeg(tmp_path / "a.jpg")
    (tmp_path / "sub").mkdir()
    _make_jpeg(tmp_path / "sub" / "b.jpg")
    svc = ScanService()
    result = svc.scan(str(tmp_path), {})
    assert sorted(result.new_paths) == sorted(["a.jpg", os.path.join("sub", "b.jpg")])
    assert result.modified_paths == []
    assert result.total == 2
    assert result.has_changes is True


def test_existing_files_with_matching_mtime_are_quiet(tmp_path):
    p = tmp_path / "x.jpg"
    _make_jpeg(p)
    db = {"x.jpg": os.path.getmtime(p)}
    svc = ScanService()
    result = svc.scan(str(tmp_path), db)
    assert result.new_paths == []
    assert result.modified_paths == []


def test_modified_file_detected_when_disk_mtime_is_newer(tmp_path):
    p = tmp_path / "m.jpg"
    _make_jpeg(p)
    real_mtime = os.path.getmtime(p)
    # DB thinks file was last seen well before its current state.
    db = {"m.jpg": real_mtime - 60.0}
    svc = ScanService()
    result = svc.scan(str(tmp_path), db)
    assert result.new_paths == []
    assert result.modified_paths == ["m.jpg"]


def test_subsecond_drift_within_epsilon_is_ignored(tmp_path):
    p = tmp_path / "n.jpg"
    _make_jpeg(p)
    db = {"n.jpg": os.path.getmtime(p) - 0.1}  # below epsilon
    svc = ScanService(mtime_epsilon=1.0)
    result = svc.scan(str(tmp_path), db)
    assert result.modified_paths == []


def test_legacy_row_with_null_mtime_is_not_flagged(tmp_path):
    p = tmp_path / "legacy.jpg"
    _make_jpeg(p)
    db = {"legacy.jpg": None}
    svc = ScanService()
    result = svc.scan(str(tmp_path), db)
    assert result.modified_paths == []
    assert result.new_paths == []


def test_db_row_for_missing_file_is_ignored(tmp_path):
    """Files in DB but no longer on disk are out of scope for this service."""
    _make_jpeg(tmp_path / "present.jpg")
    db = {
        "present.jpg": os.path.getmtime(tmp_path / "present.jpg"),
        "vanished.jpg": 123456.0,
    }
    svc = ScanService()
    result = svc.scan(str(tmp_path), db)
    assert result.new_paths == []
    assert result.modified_paths == []


def test_mixed_new_and_modified(tmp_path):
    p1 = tmp_path / "old.jpg"
    p2 = tmp_path / "fresh.jpg"
    _make_jpeg(p1)
    _make_jpeg(p2)
    db = {"old.jpg": os.path.getmtime(p1) - 100.0}
    svc = ScanService()
    result = svc.scan(str(tmp_path), db)
    assert result.new_paths == ["fresh.jpg"]
    assert result.modified_paths == ["old.jpg"]
    assert result.total == 2


def test_scan_result_is_immutable_dataclass():
    r = ScanResult(new_paths=["a"], modified_paths=["b"])
    assert r.new_paths == ["a"]
    assert r.modified_paths == ["b"]
    assert r.total == 2
