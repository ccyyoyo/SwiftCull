import os
from dataclasses import dataclass
from typing import List, Optional, Set

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

_HIGHLIGHT_THRESHOLD = 250
_SHADOW_THRESHOLD = 5
_EPSILON = 1e-9


@dataclass
class ExposureResult:
    mean_brightness: float
    overexposed_fraction: float
    underexposed_fraction: float


class ExposureService:
    def compute_scores(self, root_path: str, relative_path: str) -> Optional[ExposureResult]:
        """Analyse luminance histogram. Returns None if cv2 unavailable or image unreadable."""
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            from app.core.image_io import read_image_color
            img = read_image_color(abs_path)
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            total = gray.size
            mean_brightness = float(gray.mean())
            overexposed_fraction = float(np.sum(gray >= _HIGHLIGHT_THRESHOLD) / total)
            underexposed_fraction = float(np.sum(gray <= _SHADOW_THRESHOLD) / total)
            return ExposureResult(mean_brightness, overexposed_fraction, underexposed_fraction)
        except Exception:
            return None

    def is_overexposed(self, result: ExposureResult, fraction_threshold: float = 0.01) -> bool:
        """True if the blown-out fraction exceeds fraction_threshold (default 1%)."""
        return result.overexposed_fraction > fraction_threshold

    def is_underexposed(self, result: ExposureResult, fraction_threshold: float = 0.01) -> bool:
        """True if the shadow-crushed fraction exceeds fraction_threshold (default 1%)."""
        return result.underexposed_fraction > fraction_threshold

    def relative_overexposed_threshold(
        self, fractions: List[float], top_percent: float
    ) -> float:
        """Return the overexposed_fraction threshold so the top_percent% worst photos are flagged."""
        if not fractions:
            return 1.0
        sorted_fracs = sorted(fractions, reverse=True)
        idx = max(0, int(len(sorted_fracs) * top_percent / 100.0) - 1)
        return sorted_fracs[idx] - _EPSILON

    def relative_underexposed_threshold(
        self, fractions: List[float], top_percent: float
    ) -> float:
        """Return the underexposed_fraction threshold so the top_percent% worst photos are flagged."""
        if not fractions:
            return 1.0
        sorted_fracs = sorted(fractions, reverse=True)
        idx = max(0, int(len(sorted_fracs) * top_percent / 100.0) - 1)
        return sorted_fracs[idx] - _EPSILON

    @staticmethod
    def exposure_states(
        photo,
        clip_threshold: float = 0.01,
        black_mean_threshold: float = 8.0,
        black_shadow_threshold: float = 0.90,
    ) -> Set[str]:
        """Return all matching exposure states for a photo. photo must have
        exposure_mean, exposure_overexposed, exposure_underexposed attributes."""
        if (photo.exposure_mean is None
                or photo.exposure_overexposed is None
                or photo.exposure_underexposed is None):
            return {"unanalyzed"}

        states: Set[str] = set()
        if photo.exposure_overexposed > clip_threshold:
            states.add("overexposed")
        is_under = photo.exposure_underexposed > clip_threshold
        is_black = (
            photo.exposure_mean <= black_mean_threshold
            and photo.exposure_underexposed > black_shadow_threshold
        )
        if is_black:
            states.add("black_frame")
            states.add("underexposed")
        elif is_under:
            states.add("underexposed")
        if not states:
            states.add("normal")
        return states

    @staticmethod
    def exposure_display_state(
        photo,
        clip_threshold: float = 0.01,
        black_mean_threshold: float = 8.0,
        black_shadow_threshold: float = 0.90,
    ) -> str:
        """Return single highest-priority state for UI display.
        Priority: unanalyzed > black_frame > overexposed > underexposed > normal."""
        states = ExposureService.exposure_states(
            photo, clip_threshold, black_mean_threshold, black_shadow_threshold
        )
        for priority in ("unanalyzed", "black_frame", "overexposed", "underexposed", "normal"):
            if priority in states:
                return priority
        return "unanalyzed"
