import logging
import os
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


def read_image_color(path: str) -> Optional[np.ndarray]:
    """Read an image as BGR, including Unicode paths on Windows."""
    try:
        data = np.fromfile(os.fspath(path), dtype=np.uint8)
    except OSError as e:
        log.debug("Failed to read image bytes from %s: %s", path, e)
        return None

    if data.size == 0:
        log.debug("Image file is empty: %s", path)
        return None

    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        log.debug("Failed to decode image: %s", path)
    return img
