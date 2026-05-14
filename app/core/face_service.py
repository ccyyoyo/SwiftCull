"""Face detection and eye-blink analysis via MediaPipe FaceLandmarker.

MediaPipe is imported lazily inside ``compute`` so unit tests for the static
classifier (``face_states``) can run without the native dependency installed.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

log = logging.getLogger(__name__)

# Per-eye blendshape value above which the eye is considered closed.
# MediaPipe ``eyeBlinkLeft`` / ``eyeBlinkRight`` scores are typically:
#   open    : 0.0 - 0.15
#   blink   : 0.30 - 0.55
#   closed  : 0.55 - 1.00
# A 0.45 threshold flags blink + closed without triggering on open eyes.
_EYE_CLOSED_THRESHOLD = 0.45

# Resize long-edge target before sending into MediaPipe. Smaller is faster;
# face landmarks remain stable down to ~1024 px on the long edge.
_MAX_SIDE = 1024

# Detect up to this many faces per photo. Group portraits routinely have 5-10.
_NUM_FACES = 10


@dataclass
class FaceResult:
    face_count: int
    face_max_area: float            # 0.0 - 1.0 (largest face bbox / image area)
    eyes_closed_count: int          # faces where >=1 eye blendshape > threshold


def _default_model_path() -> str:
    """assets/face_landmarker.task at repo root."""
    return str(Path(__file__).resolve().parents[2] / "assets" / "face_landmarker.task")


class FaceService:
    """Stateless from caller perspective; lazy-inits FaceLandmarker on first use."""

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path or _default_model_path()
        self._landmarker = None  # lazy
        self._mp_image_cls = None

    def _ensure_landmarker(self) -> bool:
        """Lazy-init FaceLandmarker. Returns True on success, False otherwise.

        Called from the worker thread; MediaPipe builds native graphs which we
        avoid running on the main thread.
        """
        if self._landmarker is not None:
            return True
        if not os.path.exists(self._model_path):
            log.warning("FaceLandmarker model not found at %s", self._model_path)
            return False
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            base_options = mp_python.BaseOptions(model_asset_path=self._model_path)
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=False,
                num_faces=_NUM_FACES,
            )
            self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
            self._mp_image_cls = mp.Image
            self._mp_image_format = mp.ImageFormat.SRGB
            log.info("FaceLandmarker initialized from %s", self._model_path)
            return True
        except Exception as e:
            log.exception("Failed to initialize FaceLandmarker: %s", e)
            return False

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None

    def compute(self, root_path: str, relative_path: str) -> Optional[FaceResult]:
        """Detect faces and eye-closed count.

        Returns:
            ``FaceResult(0, 0.0, 0)`` when the image is decoded but no faces are
            found (still counts as a successful analysis).
            ``None`` when MediaPipe cannot init, the image fails to read, or
            inference raises.
        """
        if not self._ensure_landmarker():
            return None
        abs_path = os.path.join(root_path, relative_path)
        try:
            from app.core.image_io import read_image_color
            import cv2
            import numpy as np

            img_bgr = read_image_color(abs_path)
            if img_bgr is None:
                return None
            h, w = img_bgr.shape[:2]
            long_side = max(h, w)
            if long_side > _MAX_SIDE:
                scale = _MAX_SIDE / long_side
                img_bgr = cv2.resize(
                    img_bgr,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_AREA,
                )
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            mp_image = self._mp_image_cls(
                image_format=self._mp_image_format, data=img_rgb
            )
            result = self._landmarker.detect(mp_image)

            landmarks_list = getattr(result, "face_landmarks", None) or []
            blendshapes_list = getattr(result, "face_blendshapes", None) or []

            face_count = len(landmarks_list)
            if face_count == 0:
                return FaceResult(face_count=0, face_max_area=0.0, eyes_closed_count=0)

            max_area = 0.0
            for landmarks in landmarks_list:
                if not landmarks:
                    continue
                xs = [lm.x for lm in landmarks]
                ys = [lm.y for lm in landmarks]
                width_norm = max(0.0, max(xs) - min(xs))
                height_norm = max(0.0, max(ys) - min(ys))
                area = float(width_norm * height_norm)
                if area > max_area:
                    max_area = area
            max_area = min(1.0, max_area)

            eyes_closed_count = 0
            for blendshapes in blendshapes_list:
                left = right = 0.0
                for cat in blendshapes:
                    name = getattr(cat, "category_name", None)
                    score = float(getattr(cat, "score", 0.0))
                    if name == "eyeBlinkLeft":
                        left = score
                    elif name == "eyeBlinkRight":
                        right = score
                if max(left, right) > _EYE_CLOSED_THRESHOLD:
                    eyes_closed_count += 1

            return FaceResult(
                face_count=face_count,
                face_max_area=max_area,
                eyes_closed_count=eyes_closed_count,
            )
        except Exception as e:
            log.exception("Error computing face result for %s: %s", relative_path, e)
            return None

    @staticmethod
    def face_states(photo, eyes_closed_threshold: int = 1) -> Set[str]:
        """Classify a photo into face-related states.

        Returns ``{"unanalyzed"}`` if face analysis has not been attempted yet.
        Otherwise returns a set drawn from ``{has_face, no_face, eyes_closed}``.

        ``has_face`` and ``eyes_closed`` are not mutually exclusive: a photo with
        a face whose eyes are closed will return both.
        """
        if not getattr(photo, "face_analyzed", False):
            return {"unanalyzed"}
        states: Set[str] = set()
        face_count = photo.face_count or 0
        if face_count > 0:
            states.add("has_face")
            closed = photo.face_eyes_closed_count or 0
            if closed >= eyes_closed_threshold:
                states.add("eyes_closed")
        else:
            states.add("no_face")
        return states

    @staticmethod
    def face_display_state(photo, eyes_closed_threshold: int = 1) -> str:
        """Pick the highest-priority state for a single-label UI badge.

        Priority: unanalyzed > eyes_closed > has_face > no_face.
        """
        states = FaceService.face_states(photo, eyes_closed_threshold)
        for priority in ("unanalyzed", "eyes_closed", "has_face", "no_face"):
            if priority in states:
                return priority
        return "unanalyzed"
