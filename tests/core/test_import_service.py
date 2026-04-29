import os
from PIL import Image
from app.core.import_service import ImportService, SUPPORTED_EXTENSIONS

def _make_jpeg(path):
    img = Image.new("RGB", (100, 80), color=(128, 64, 32))
    img.save(str(path), "JPEG")

def test_scan_finds_supported_files(tmp_path):
    (tmp_path / "sub").mkdir()
    _make_jpeg(tmp_path / "a.jpg")
    _make_jpeg(tmp_path / "sub" / "b.jpeg")
    (tmp_path / "ignore.txt").write_text("x")
    svc = ImportService()
    found = svc.scan_folder(str(tmp_path))
    names = {os.path.basename(p) for p in found}
    assert "a.jpg" in names
    assert "b.jpeg" in names
    assert "ignore.txt" not in names

def test_scan_returns_relative_paths(tmp_path):
    _make_jpeg(tmp_path / "c.jpg")
    svc = ImportService()
    found = svc.scan_folder(str(tmp_path))
    for p in found:
        assert not os.path.isabs(p)

def test_build_photo_from_jpeg(tmp_path):
    img_path = tmp_path / "d.jpg"
    _make_jpeg(img_path)
    svc = ImportService()
    photo = svc.build_photo(str(tmp_path), "d.jpg")
    assert photo.filename == "d.jpg"
    assert photo.relative_path == "d.jpg"
    assert photo.file_size > 0
    assert photo.width == 100
    assert photo.height == 80

def test_build_photo_minimal_skips_dimensions(tmp_path):
    img_path = tmp_path / "min.jpg"
    _make_jpeg(img_path)
    svc = ImportService()
    photo = svc.build_photo_minimal(str(tmp_path), "min.jpg")
    assert photo.filename == "min.jpg"
    assert photo.relative_path == "min.jpg"
    assert photo.file_size > 0
    assert photo.width is None
    assert photo.height is None
    assert photo.shot_at is None

def test_enrich_photo_returns_dimensions(tmp_path):
    img_path = tmp_path / "e.jpg"
    _make_jpeg(img_path)
    svc = ImportService()
    meta = svc.enrich_photo(str(tmp_path), "e.jpg")
    assert meta["width"] == 100
    assert meta["height"] == 80
    assert "shot_at" in meta
