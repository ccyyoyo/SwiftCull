"""FaceService failure-path tests that do not need MediaPipe to be functional.

These tests pass even when the model file is missing or MediaPipe init fails,
because the service is required to return None gracefully in those cases.
"""

import os
from pathlib import Path


def test_compute_returns_none_for_missing_file(tmp_path):
    from app.core.face_service import FaceService
    # Point to a model path that doesn't exist; compute should return None
    # before any decode attempt (and well before any MediaPipe call).
    svc = FaceService(model_path=str(tmp_path / "does_not_exist.task"))
    assert svc.compute(str(tmp_path), "nonexistent.jpg") is None


def test_compute_returns_none_when_model_missing_even_with_valid_image(tmp_path):
    """If the model cannot be loaded, compute() must not crash."""
    import pytest
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    arr = np.full((50, 50, 3), 200, dtype=np.uint8)
    (tmp_path / "img.jpg").write_bytes(cv2.imencode(".jpg", arr)[1].tobytes())

    from app.core.face_service import FaceService
    svc = FaceService(model_path=str(tmp_path / "missing.task"))
    assert svc.compute(str(tmp_path), "img.jpg") is None


def test_default_model_path_points_into_assets():
    from app.core.face_service import _default_model_path
    p = _default_model_path()
    assert p.endswith("face_landmarker.task")
    assert "assets" in p.replace("\\", "/").split("/")


def test_default_model_file_exists_in_repo():
    """The model file is bundled in the repo. If this fails the asset is
    missing from the checkout and face detection won't work in the app."""
    from app.core.face_service import _default_model_path
    assert os.path.exists(_default_model_path())
