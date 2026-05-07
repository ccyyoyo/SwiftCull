import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
    log.debug("OpenCV available for horizon detection")
except ImportError:
    _CV2_AVAILABLE = False
    log.warning("OpenCV not available - horizon detection disabled")

_MAX_SIDE = 1024          # resize width for speed
_MIN_LINE_FRACTION = 0.08 # min line length as fraction of width
_ANGLE_RANGE = 45.0       # accept lines within ±45° of horizontal


class HorizonService:
    def compute_skew(self, root_path: str, relative_path: str) -> Optional[float]:
        """Detect horizon skew via Hough lines. Returns angle in degrees (0=level),
        positive = clockwise tilt. Returns None on failure or no lines found."""
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            from app.core.image_io import read_image_color
            img = read_image_color(abs_path)
            if img is None:
                log.debug("Failed to read image: %s", relative_path)
                return None
            h, w = img.shape[:2]
            if w > _MAX_SIDE:
                scale = _MAX_SIDE / w
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
                h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(gray, 50, 150)
            min_length = int(w * _MIN_LINE_FRACTION)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=80,
                minLineLength=min_length,
                maxLineGap=10,
            )
            if lines is None:
                log.debug("No Hough lines found: %s", relative_path)
                return None
            angles = []
            lengths = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = x2 - x1
                dy = y2 - y1
                length = float(np.sqrt(dx * dx + dy * dy))
                angle = float(np.degrees(np.arctan2(dy, dx)))
                if abs(angle) <= _ANGLE_RANGE:
                    angles.append(angle)
                    lengths.append(length)
            if not angles:
                log.debug("No horizontal lines found: %s", relative_path)
                return None
            skew = _weighted_median(np.array(angles), np.array(lengths))
            log.debug("Horizon skew for %s: %.2f°", relative_path, skew)
            return float(skew)
        except Exception as e:
            log.debug("Error computing horizon skew for %s: %s", relative_path, e)
            return None

    @staticmethod
    def skew_state(photo, level_threshold: float = 1.0) -> str:
        """Return 'level', 'tilted', or 'unanalyzed' for a photo."""
        if photo.horizon_skew is None:
            return "unanalyzed"
        if abs(photo.horizon_skew) <= level_threshold:
            return "level"
        return "tilted"


def _weighted_median(values: "np.ndarray", weights: "np.ndarray") -> float:
    """Weighted median: first value whose cumulative weight reaches 50% of total."""
    sorted_idx = np.argsort(values)
    sorted_vals = values[sorted_idx]
    sorted_weights = weights[sorted_idx]
    cumulative = np.cumsum(sorted_weights)
    midpoint = cumulative[-1] / 2.0
    idx = int(np.searchsorted(cumulative, midpoint))
    idx = min(idx, len(sorted_vals) - 1)
    return float(sorted_vals[idx])
