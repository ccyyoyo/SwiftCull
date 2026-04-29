import os
from pathlib import Path
from typing import List
from PIL import Image
from app.core.models import Photo

try:
    import piexif
except ImportError:
    piexif = None

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}
RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng", ".rw2", ".orf"}

class ImportService:
    def scan_folder(self, folder_path: str) -> List[str]:
        all_exts = SUPPORTED_EXTENSIONS | RAW_EXTENSIONS
        result = []
        root = Path(folder_path)
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in all_exts:
                result.append(str(p.relative_to(root)))
        return result

    def build_photo_minimal(self, root_path: str, relative_path: str) -> Photo:
        """Cheap: only filesystem metadata. Safe to call inside the import loop."""
        abs_path = os.path.join(root_path, relative_path)
        return Photo(
            id=None,
            relative_path=relative_path,
            filename=os.path.basename(relative_path),
            file_size=os.path.getsize(abs_path),
        )

    def enrich_photo(self, root_path: str, relative_path: str) -> dict:
        """Expensive: open image for dimensions and parse EXIF. Run in worker thread."""
        abs_path = os.path.join(root_path, relative_path)
        width, height = self._get_dimensions(abs_path)
        exif = self._read_exif(abs_path)
        return {
            "width": width,
            "height": height,
            "shot_at": exif.get("shot_at"),
            "camera_model": exif.get("camera_model"),
            "lens_model": exif.get("lens_model"),
            "iso": exif.get("iso"),
            "aperture": exif.get("aperture"),
            "shutter_speed": exif.get("shutter_speed"),
            "focal_length": exif.get("focal_length"),
        }

    def build_photo(self, root_path: str, relative_path: str) -> Photo:
        """Full build (minimal + enrich). Kept for callers/tests that want everything at once."""
        photo = self.build_photo_minimal(root_path, relative_path)
        meta = self.enrich_photo(root_path, relative_path)
        for k, v in meta.items():
            setattr(photo, k, v)
        return photo

    def _get_dimensions(self, abs_path: str):
        ext = Path(abs_path).suffix.lower()
        if ext in RAW_EXTENSIONS:
            try:
                import rawpy, io
                with rawpy.imread(abs_path) as raw:
                    thumb = raw.extract_thumb()
                    if thumb.format.name == "JPEG":
                        img = Image.open(io.BytesIO(thumb.data))
                        return img.size
            except Exception:
                pass
            return None, None
        try:
            with Image.open(abs_path) as img:
                return img.size
        except Exception:
            return None, None

    def _read_exif(self, abs_path: str) -> dict:
        result = {}
        if piexif is None:
            return result
        try:
            exif_data = piexif.load(abs_path)
            exif = exif_data.get("Exif", {})
            ifd0 = exif_data.get("0th", {})
            if piexif.ExifIFD.DateTimeOriginal in exif:
                dt_bytes = exif[piexif.ExifIFD.DateTimeOriginal]
                result["shot_at"] = dt_bytes.decode("ascii", errors="ignore")
            if piexif.ImageIFD.Make in ifd0 and piexif.ImageIFD.Model in ifd0:
                make = ifd0[piexif.ImageIFD.Make].decode("ascii", errors="ignore").strip("\x00")
                model = ifd0[piexif.ImageIFD.Model].decode("ascii", errors="ignore").strip("\x00")
                result["camera_model"] = f"{make} {model}".strip()
            if piexif.ExifIFD.ISOSpeedRatings in exif:
                result["iso"] = exif[piexif.ExifIFD.ISOSpeedRatings]
            if piexif.ExifIFD.FNumber in exif:
                n, d = exif[piexif.ExifIFD.FNumber]
                result["aperture"] = n / d if d else None
            if piexif.ExifIFD.ExposureTime in exif:
                n, d = exif[piexif.ExifIFD.ExposureTime]
                result["shutter_speed"] = f"{n}/{d}" if d else None
            if piexif.ExifIFD.FocalLength in exif:
                n, d = exif[piexif.ExifIFD.FocalLength]
                result["focal_length"] = n / d if d else None
        except Exception:
            pass
        return result
