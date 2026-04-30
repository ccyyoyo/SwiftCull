from dataclasses import dataclass
from typing import Optional

@dataclass
class Photo:
    id: Optional[int]
    relative_path: str
    filename: str
    file_size: int
    mtime: Optional[float] = None
    shot_at: Optional[str] = None
    imported_at: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    camera_model: Optional[str] = None
    lens_model: Optional[str] = None
    iso: Optional[int] = None
    aperture: Optional[float] = None
    shutter_speed: Optional[str] = None
    focal_length: Optional[float] = None
    blur_score: Optional[float] = None

@dataclass
class Tag:
    photo_id: int
    id: Optional[int] = None
    status: Optional[str] = None  # "pick" | "reject" | "maybe" | None
    color: Optional[str] = None   # "red"|"orange"|"yellow"|"green"|"blue"|"purple"|None
    updated_at: Optional[str] = None
