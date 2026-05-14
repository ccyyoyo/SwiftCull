"""FaceService.compute integration test against MediaPipe.

Skipped automatically when:
- MediaPipe is not installed
- The bundled face_landmarker.task model is missing
"""

import os
import pytest


pytestmark = pytest.mark.skipif(
    pytest.importorskip("mediapipe", reason="MediaPipe not installed") is None,
    reason="MediaPipe not installed",
)


def _model_exists():
    from app.core.face_service import _default_model_path
    return os.path.exists(_default_model_path())


def test_compute_returns_zero_faces_for_solid_color_image(tmp_path):
    if not _model_exists():
        pytest.skip("face_landmarker.task model missing")
    import cv2
    import numpy as np

    arr = np.full((300, 300, 3), 120, dtype=np.uint8)
    (tmp_path / "blank.jpg").write_bytes(cv2.imencode(".jpg", arr)[1].tobytes())

    from app.core.face_service import FaceService, FaceResult

    svc = FaceService()
    try:
        result = svc.compute(str(tmp_path), "blank.jpg")
    finally:
        svc.close()

    assert isinstance(result, FaceResult)
    assert result.face_count == 0
    assert result.face_max_area == 0.0
    assert result.eyes_closed_count == 0


def test_compute_returns_none_for_unreadable_file(tmp_path):
    if not _model_exists():
        pytest.skip("face_landmarker.task model missing")
    (tmp_path / "junk.jpg").write_bytes(b"not a real jpeg")
    from app.core.face_service import FaceService

    svc = FaceService()
    try:
        result = svc.compute(str(tmp_path), "junk.jpg")
    finally:
        svc.close()

    assert result is None
