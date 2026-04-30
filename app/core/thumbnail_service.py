import hashlib
from pathlib import Path
from typing import Iterable
from PIL import Image

_RAW_EXTS = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng", ".rw2", ".orf"}


class ThumbnailService:
    def __init__(self, cache_dir: str):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail(self, abs_path: str, size: int = 256) -> str:
        cache_path = self._cache_path(abs_path, size)
        if cache_path.exists():
            return str(cache_path)
        ext = Path(abs_path).suffix.lower()
        if ext in _RAW_EXTS:
            img = self._load_raw_thumb(abs_path)
        else:
            img = Image.open(abs_path).convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        img.save(str(cache_path), "JPEG", quality=85)
        return str(cache_path)

    def invalidate(self, abs_path: str, sizes: Iterable[int] = (100, 160, 240, 256)) -> int:
        """Drop cache entries for `abs_path` so the next view regenerates them.

        Returns the number of cache files removed. Sizes covers the snap sizes
        used by the grid plus the historical default to be safe; callers may
        pass an explicit set if they know which sizes are in use.
        """
        removed = 0
        for size in sizes:
            cache_path = self._cache_path(abs_path, size)
            try:
                cache_path.unlink()
                removed += 1
            except FileNotFoundError:
                continue
            except OSError:
                continue
        return removed

    def _cache_path(self, abs_path: str, size: int) -> Path:
        cache_key = hashlib.md5(f"{abs_path}:{size}".encode()).hexdigest()
        return self._cache_dir / f"{cache_key}.jpg"

    def _load_raw_thumb(self, abs_path: str) -> Image.Image:
        import rawpy, io
        with rawpy.imread(abs_path) as raw:
            thumb = raw.extract_thumb()
            if thumb.format.name == "JPEG":
                return Image.open(io.BytesIO(thumb.data)).convert("RGB")
        raise ValueError(f"Cannot extract thumbnail from {abs_path}")
