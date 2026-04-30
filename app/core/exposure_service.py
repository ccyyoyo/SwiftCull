import os
from dataclasses import dataclass
from typing import List

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# Pixel brightness thresholds for clipping detection (0-255)
_HIGHLIGHT_THRESHOLD = 250
_SHADOW_THRESHOLD = 5

# Small epsilon subtracted from relative thresholds so the boundary photo
# itself is classified as over/underexposed (strict inequality in is_* checks).
_EPSILON = 1e-9


@dataclass
class ExposureResult:
    mean_brightness: float       # 0–255
    overexposed_fraction: float  # 0.0–1.0, fraction of pixels >= HIGHLIGHT_THRESHOLD
    underexposed_fraction: float # 0.0–1.0, fraction of pixels <= SHADOW_THRESHOLD


_ZERO = ExposureResult(0.0, 0.0, 0.0)


class ExposureService:
    def compute_scores(self, root_path: str, relative_path: str) -> ExposureResult:
        """Analyse luminance histogram. Returns zero-valued result on failure."""
        if not _CV2_AVAILABLE:
            return _ZERO
        abs_path = os.path.join(root_path, relative_path)
        try:
            img = cv2.imread(abs_path)
            if img is None:
                return _ZERO
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            total = gray.size
            mean_brightness = float(gray.mean())
            overexposed_fraction = float(np.sum(gray >= _HIGHLIGHT_THRESHOLD) / total)
            underexposed_fraction = float(np.sum(gray <= _SHADOW_THRESHOLD) / total)
            return ExposureResult(mean_brightness, overexposed_fraction, underexposed_fraction)
        except Exception:
            return _ZERO

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
