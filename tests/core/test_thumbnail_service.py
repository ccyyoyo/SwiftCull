import os
from PIL import Image
from app.core.thumbnail_service import ThumbnailService

def _make_jpeg(path, w=200, h=150):
    Image.new("RGB", (w, h), color=(10, 20, 30)).save(str(path), "JPEG")

def test_generates_thumbnail(tmp_path):
    img_path = tmp_path / "photo.jpg"
    cache_dir = tmp_path / "cache"
    _make_jpeg(img_path)
    svc = ThumbnailService(str(cache_dir))
    thumb_path = svc.get_thumbnail(str(img_path), size=128)
    assert os.path.exists(thumb_path)
    with Image.open(thumb_path) as img:
        assert max(img.size) <= 128

def test_returns_cached_on_second_call(tmp_path):
    img_path = tmp_path / "photo.jpg"
    cache_dir = tmp_path / "cache"
    _make_jpeg(img_path)
    svc = ThumbnailService(str(cache_dir))
    path1 = svc.get_thumbnail(str(img_path), size=128)
    mtime1 = os.path.getmtime(path1)
    path2 = svc.get_thumbnail(str(img_path), size=128)
    mtime2 = os.path.getmtime(path2)
    assert mtime1 == mtime2
