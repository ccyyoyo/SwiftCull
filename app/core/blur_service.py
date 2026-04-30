import os
from typing import List, Optional

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


class BlurService:
    def compute_score(self, root_path: str, relative_path: str) -> Optional[float]:
        """Return Laplacian variance of image. Higher = sharper. Returns None on failure."""
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            img = cv2.imread(abs_path)
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return None

    def is_blurry_fixed(self, score: Optional[float], threshold: float) -> bool:
        """True if score is below threshold (fixed mode). Returns False for None (unanalyzed)."""
        if score is None:
            return False
        return score < threshold

    def relative_threshold(self, scores: List[Optional[float]], bottom_percent: float) -> float:
        """Return threshold so photos at/below the bottom_percent percentile are blurry."""
        valid = [s for s in scores if s is not None]
        if not valid:
            return 0.0
        sorted_scores = sorted(valid)
        idx = max(0, int(len(sorted_scores) * bottom_percent / 100.0) - 1)
        # Add small epsilon so the boundary photo itself is classified as blurry
        return sorted_scores[idx] + 1e-9
