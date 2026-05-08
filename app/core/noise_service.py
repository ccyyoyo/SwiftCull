"""FFT/SNR-based noise detection service."""

import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    log.warning("OpenCV not available - noise detection disabled")


class NoiseService:
    def compute_score(self, root_path: str, relative_path: str) -> Optional[float]:
        """Return FFT-based SNR score. Higher = cleaner (less noisy). Returns None on failure.

        Computes the ratio of low-frequency power (signal) to high-frequency power
        (noise) in the 2D FFT of the grayscale image, returned as log10(SNR + 1).
        """
        if not _CV2_AVAILABLE:
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            from app.core.image_io import read_image_color
            img = read_image_color(abs_path)
            if img is None:
                log.debug("Failed to read image: %s", relative_path)
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            gray -= gray.mean()  # remove DC so SNR reflects signal structure, not mean brightness

            fft_shift = np.fft.fftshift(np.fft.fft2(gray))
            power = np.abs(fft_shift) ** 2

            h, w = power.shape
            cy, cx = h // 2, w // 2
            r = min(h, w) // 8
            Y, X = np.ogrid[:h, :w]
            low_freq_mask = (Y - cy) ** 2 + (X - cx) ** 2 <= r ** 2

            signal_power = float(power[low_freq_mask].sum())
            noise_power = float(power[~low_freq_mask].sum())

            snr = signal_power / (noise_power + 1e-9)
            score = float(np.log10(snr + 1.0))
            log.debug("Noise score for %s: %.4f", relative_path, score)
            return score
        except Exception as e:
            log.debug("Error computing noise score for %s: %s", relative_path, e)
            return None

    def is_noisy_fixed(self, score: Optional[float], threshold: float) -> bool:
        """True if score is below threshold (noisier). Returns False for None (unanalyzed)."""
        if score is None:
            return False
        return score < threshold

