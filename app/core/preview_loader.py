"""Load image preview bytes for full-screen Loupe viewing.

Per ROADMAP Phase 1: RAW files use the embedded JPEG preview (fast).
Standard formats (JPEG/PNG/TIFF/WebP) return their raw file bytes so the
caller can hand them to QPixmap.loadFromData().

Returns None when the path does not exist, the format is unsupported, or
the embedded preview cannot be extracted. Callers are responsible for
showing an empty/error state in that case.
"""

import os
from pathlib import Path
from typing import Optional

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng", ".rw2", ".orf"}
STANDARD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}


def load_preview_bytes(abs_path: str) -> Optional[bytes]:
    """Return image bytes suitable for QPixmap.loadFromData().

    For RAW files extracts the embedded JPEG thumbnail via rawpy. For
    standard formats reads the file as-is. Returns None on any failure.
    """
    if not abs_path or not os.path.isfile(abs_path):
        return None

    ext = Path(abs_path).suffix.lower()

    if ext in RAW_EXTENSIONS:
        return _extract_raw_jpeg(abs_path)

    if ext in STANDARD_EXTENSIONS:
        try:
            with open(abs_path, "rb") as f:
                return f.read()
        except OSError:
            return None

    return None


def _extract_raw_jpeg(abs_path: str) -> Optional[bytes]:
    try:
        import rawpy
    except ImportError:
        return None
    try:
        with rawpy.imread(abs_path) as raw:
            thumb = raw.extract_thumb()
            if getattr(thumb, "format", None) is None:
                return None
            if thumb.format.name == "JPEG":
                return bytes(thumb.data)
            return None
    except Exception:
        return None
