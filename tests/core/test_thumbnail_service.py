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


def test_invalidate_removes_cache_entries(tmp_path):
    img_path = tmp_path / "inv.jpg"
    cache_dir = tmp_path / "cache"
    _make_jpeg(img_path)
    svc = ThumbnailService(str(cache_dir))
    cache_a = svc.get_thumbnail(str(img_path), size=100)
    cache_b = svc.get_thumbnail(str(img_path), size=160)
    assert os.path.exists(cache_a) and os.path.exists(cache_b)

    removed = svc.invalidate(str(img_path), sizes=(100, 160, 240))
    assert removed == 2  # 240 didn't exist
    assert not os.path.exists(cache_a)
    assert not os.path.exists(cache_b)


def test_invalidate_when_nothing_cached_is_safe(tmp_path):
    svc = ThumbnailService(str(tmp_path / "cache"))
    assert svc.invalidate(str(tmp_path / "ghost.jpg")) == 0


def test_invalidate_then_get_regenerates(tmp_path):
    img_path = tmp_path / "regen.jpg"
    cache_dir = tmp_path / "cache"
    _make_jpeg(img_path)
    svc = ThumbnailService(str(cache_dir))
    first = svc.get_thumbnail(str(img_path), size=128)
    first_mtime = os.path.getmtime(first)
    # ensure clock moves on slow filesystems before regenerating
    os.utime(img_path, (first_mtime + 5, first_mtime + 5))

    svc.invalidate(str(img_path), sizes=(128,))
    assert not os.path.exists(first)

    again = svc.get_thumbnail(str(img_path), size=128)
    assert again == first  # same cache path (md5 of abs+size)
    assert os.path.exists(again)
