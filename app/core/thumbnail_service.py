import hashlib
from pathlib import Path
from PIL import Image

class ThumbnailService:
    def __init__(self, cache_dir: str):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail(self, abs_path: str, size: int = 256) -> str:
        cache_key = hashlib.md5(f"{abs_path}:{size}".encode()).hexdigest()
        cache_path = self._cache_dir / f"{cache_key}.jpg"
        if cache_path.exists():
            return str(cache_path)
        ext = Path(abs_path).suffix.lower()
        raw_exts = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng", ".rw2", ".orf"}
        if ext in raw_exts:
            img = self._load_raw_thumb(abs_path)
        else:
            img = Image.open(abs_path).convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        img.save(str(cache_path), "JPEG", quality=85)
        return str(cache_path)

    def _load_raw_thumb(self, abs_path: str) -> Image.Image:
        import rawpy, io
        with rawpy.imread(abs_path) as raw:
            thumb = raw.extract_thumb()
            if thumb.format.name == "JPEG":
                return Image.open(io.BytesIO(thumb.data)).convert("RGB")
        raise ValueError(f"Cannot extract thumbnail from {abs_path}")
