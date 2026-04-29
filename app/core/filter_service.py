from typing import List, Optional
from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.models import Photo


class FilterService:
    def __init__(self, photo_repo: PhotoRepository, tag_repo: TagRepository):
        self._photos = photo_repo
        self._tags = tag_repo

    def filter(
        self,
        statuses: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        blur: Optional[List[str]] = None,
        blur_threshold: float = 100.0,
    ) -> List[Photo]:
        all_photos = self._photos.get_all()
        if not statuses and not colors and not blur:
            return all_photos
        result = []
        for photo in all_photos:
            tag = self._tags.get_by_photo_id(photo.id)
            current_status = tag.status if tag else None
            current_color = tag.color if tag else None

            if statuses:
                if "untagged" in statuses:
                    if current_status is not None:
                        continue
                elif current_status not in statuses:
                    continue

            if colors and current_color not in colors:
                continue

            if blur:
                score = photo.blur_score
                if "unanalyzed" in blur and score is not None:
                    continue
                if "blurry" in blur and (score is None or score >= blur_threshold):
                    continue
                if "sharp" in blur and (score is None or score < blur_threshold):
                    continue

            result.append(photo)
        return result
