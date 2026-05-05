import logging
from typing import List, Optional
from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.models import Photo

log = logging.getLogger(__name__)


class FilterService:
    def __init__(self, photo_repo: PhotoRepository, tag_repo: TagRepository):
        self._photos = photo_repo
        self._tags = tag_repo

    def filter(
        self,
        statuses: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        blur: Optional[List[str]] = None,
        exposure: Optional[List[str]] = None,
        blur_mode: str = "fixed",
        blur_fixed_threshold: float = 100.0,
        blur_relative_percent: float = 20.0,
        exposure_clip_threshold: float = 0.01,
        exposure_black_mean_threshold: float = 8.0,
        exposure_black_shadow_threshold: float = 0.90,
    ) -> List[Photo]:
        log.debug(
            "filter called: statuses=%s colors=%s blur=%s exposure=%s",
            statuses, colors, blur, exposure,
        )
        all_photos = self._photos.get_all()
        if not statuses and not colors and not blur and not exposure:
            return all_photos

        effective_threshold = blur_fixed_threshold
        if blur and blur_mode == "relative":
            from app.core.blur_service import BlurService
            scores = [p.blur_score for p in all_photos if p.blur_score is not None]
            effective_threshold = BlurService().relative_threshold(
                scores, blur_relative_percent
            )

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
                passes = False
                if "unanalyzed" in blur and score is None:
                    passes = True
                if "blurry" in blur and score is not None and score < effective_threshold:
                    passes = True
                if "sharp" in blur and score is not None and score >= effective_threshold:
                    passes = True
                if not passes:
                    continue

            if exposure:
                from app.core.exposure_service import ExposureService
                states = ExposureService.exposure_states(
                    photo,
                    clip_threshold=exposure_clip_threshold,
                    black_mean_threshold=exposure_black_mean_threshold,
                    black_shadow_threshold=exposure_black_shadow_threshold,
                )
                if not states.intersection(set(exposure)):
                    continue

            result.append(photo)
        return result
