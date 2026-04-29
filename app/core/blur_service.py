import os
from typing import List

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


class BlurService:
    def compute_score(self, root_path: str, relative_path: str) -> float:
        """Return Laplacian variance of image. Higher = sharper. Returns 0.0 on failure."""
        if not _CV2_AVAILABLE:
            return 0.0
        abs_path = os.path.join(root_path, relative_path)
        try:
            img = cv2.imread(abs_path)
            if img is None:
                return 0.0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return 0.0

    def is_blurry_fixed(self, score: float, threshold: float) -> bool:
        """True if score is below threshold (fixed mode)."""
        return score < threshold

    def relative_threshold(self, scores: List[float], bottom_percent: float) -> float:
        """Return the score value at the bottom_percent percentile."""
        if not scores:
            return 0.0
        sorted_scores = sorted(scores)
        idx = max(0, int(len(sorted_scores) * bottom_percent / 100.0))
        return sorted_scores[min(idx, len(sorted_scores) - 1)]
