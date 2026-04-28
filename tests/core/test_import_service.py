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
