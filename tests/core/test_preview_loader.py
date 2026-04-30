import io
import sys
import types

from PIL import Image

from app.core.preview_loader import load_preview_bytes


def _make_jpeg(path, w=120, h=80, color=(10, 20, 30)):
    Image.new("RGB", (w, h), color=color).save(str(path), "JPEG")


def _make_png(path, w=60, h=40):
    Image.new("RGBA", (w, h), color=(255, 0, 0, 128)).save(str(path), "PNG")


def test_returns_none_for_missing_path():
    assert load_preview_bytes("does/not/exist.jpg") is None


def test_returns_none_for_empty_path():
    assert load_preview_bytes("") is None


def test_returns_none_for_unsupported_extension(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hi")
    assert load_preview_bytes(str(p)) is None


def test_jpeg_returns_full_bytes_pil_can_decode(tmp_path):
    p = tmp_path / "a.jpg"
    _make_jpeg(p, w=120, h=80)
    data = load_preview_bytes(str(p))
    assert data is not None
    assert data == p.read_bytes()
    with Image.open(io.BytesIO(data)) as img:
        assert img.size == (120, 80)


def test_png_returns_full_bytes_pil_can_decode(tmp_path):
    p = tmp_path / "b.png"
    _make_png(p, w=60, h=40)
    data = load_preview_bytes(str(p))
    assert data is not None
    with Image.open(io.BytesIO(data)) as img:
        assert img.size == (60, 40)


def test_extension_lookup_is_case_insensitive(tmp_path):
    p = tmp_path / "MIXED.JPEG"
    _make_jpeg(p)
    assert load_preview_bytes(str(p)) is not None


def _make_fake_rawpy(thumb_format_name: str, payload: bytes):
    """Build a minimal stand-in for the rawpy module."""
    class _Format:
        name = thumb_format_name

    class _Thumb:
        format = _Format()
        data = payload

    class _Raw:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_thumb(self):
            return _Thumb()

    fake = types.ModuleType("rawpy")
    fake.imread = lambda _path: _Raw()
    return fake


def test_raw_extracts_embedded_jpeg(tmp_path, monkeypatch):
    raw_path = tmp_path / "shot.cr2"
    raw_path.write_bytes(b"not-actually-a-raw-file")
    expected = b"\xff\xd8\xff\xe0FAKEJPEG"
    fake_rawpy = _make_fake_rawpy("JPEG", expected)
    monkeypatch.setitem(sys.modules, "rawpy", fake_rawpy)

    data = load_preview_bytes(str(raw_path))
    assert data == expected


def test_raw_returns_none_when_thumb_is_not_jpeg(tmp_path, monkeypatch):
    raw_path = tmp_path / "shot.nef"
    raw_path.write_bytes(b"x")
    fake_rawpy = _make_fake_rawpy("BITMAP", b"rgbpixels")
    monkeypatch.setitem(sys.modules, "rawpy", fake_rawpy)

    assert load_preview_bytes(str(raw_path)) is None


def test_raw_returns_none_when_rawpy_raises(tmp_path, monkeypatch):
    raw_path = tmp_path / "shot.arw"
    raw_path.write_bytes(b"x")

    fake = types.ModuleType("rawpy")

    def _boom(_p):
        raise RuntimeError("corrupt RAW")

    fake.imread = _boom
    monkeypatch.setitem(sys.modules, "rawpy", fake)

    assert load_preview_bytes(str(raw_path)) is None


def test_raw_returns_none_when_rawpy_missing(tmp_path, monkeypatch):
    raw_path = tmp_path / "shot.dng"
    raw_path.write_bytes(b"x")
    monkeypatch.setitem(sys.modules, "rawpy", None)

    assert load_preview_bytes(str(raw_path)) is None
