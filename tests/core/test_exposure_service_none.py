def test_compute_scores_returns_none_for_missing_file(tmp_path):
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "nonexistent.jpg")
    assert result is None


def test_compute_scores_returns_result_for_valid_file(tmp_path):
    import numpy as np
    import cv2
    arr = np.full((100, 100, 3), 128, dtype=np.uint8)
    (tmp_path / "img.jpg").write_bytes(cv2.imencode(".jpg", arr)[1].tobytes())
    from app.core.exposure_service import ExposureService, ExposureResult
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "img.jpg")
    assert isinstance(result, ExposureResult)
