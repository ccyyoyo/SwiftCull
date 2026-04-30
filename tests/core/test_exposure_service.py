import pytest
import numpy as np
import cv2


def _make_overexposed_jpeg(tmp_path):
    """All-white image — maximum brightness, fully blown highlights."""
    arr = np.full((200, 200, 3), 255, dtype=np.uint8)
    path = tmp_path / "overexposed.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


def _make_underexposed_jpeg(tmp_path):
    """All-black image — zero brightness, fully crushed shadows."""
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    path = tmp_path / "underexposed.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


def _make_normal_jpeg(tmp_path):
    """Mid-gray image — well-exposed, no clipping."""
    arr = np.full((200, 200, 3), 128, dtype=np.uint8)
    path = tmp_path / "normal.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


# ── compute_scores ─────────────────────────────────────────────────

def test_compute_scores_returns_exposure_result(tmp_path):
    from app.core.exposure_service import ExposureService, ExposureResult
    _make_normal_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "normal.jpg")
    assert isinstance(result, ExposureResult)
    assert 100.0 < result.mean_brightness < 160.0
    assert result.overexposed_fraction == 0.0
    assert result.underexposed_fraction == 0.0


def test_compute_scores_normal_near_mid_brightness(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_normal_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "normal.jpg")
    assert 100.0 < result.mean_brightness < 160.0


def test_compute_scores_overexposed_high_mean_and_fraction(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_overexposed_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "overexposed.jpg")
    assert result.mean_brightness > 200.0
    assert result.overexposed_fraction > 0.9


def test_compute_scores_underexposed_low_mean_and_fraction(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_underexposed_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "underexposed.jpg")
    assert result.mean_brightness < 10.0
    assert result.underexposed_fraction > 0.9


def test_compute_scores_missing_file_returns_zeros(tmp_path):
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "nonexistent.jpg")
    assert result.mean_brightness == 0.0
    assert result.overexposed_fraction == 0.0
    assert result.underexposed_fraction == 0.0


# ── is_overexposed / is_underexposed ───────────────────────────────────────────

def test_is_overexposed_detects_blown_image(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_overexposed_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "overexposed.jpg")
    assert svc.is_overexposed(result) is True


def test_is_overexposed_normal_image_false(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_normal_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "normal.jpg")
    assert svc.is_overexposed(result) is False


def test_is_underexposed_detects_black_image(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_underexposed_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "underexposed.jpg")
    assert svc.is_underexposed(result) is True


def test_is_underexposed_normal_image_false(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_normal_jpeg(tmp_path)
    svc = ExposureService()
    result = svc.compute_scores(str(tmp_path), "normal.jpg")
    assert svc.is_underexposed(result) is False


# ── relative thresholds ───────────────────────────────────────────────────

def test_relative_overexposed_threshold_flags_worst(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_overexposed_jpeg(tmp_path)
    _make_normal_jpeg(tmp_path)
    svc = ExposureService()
    over_result = svc.compute_scores(str(tmp_path), "overexposed.jpg")
    normal_result = svc.compute_scores(str(tmp_path), "normal.jpg")
    fracs = [over_result.overexposed_fraction, normal_result.overexposed_fraction]
    threshold = svc.relative_overexposed_threshold(fracs, top_percent=50)
    assert svc.is_overexposed(over_result, fraction_threshold=threshold) is True
    assert svc.is_overexposed(normal_result, fraction_threshold=threshold) is False


def test_relative_underexposed_threshold_flags_worst(tmp_path):
    from app.core.exposure_service import ExposureService
    _make_underexposed_jpeg(tmp_path)
    _make_normal_jpeg(tmp_path)
    svc = ExposureService()
    under_result = svc.compute_scores(str(tmp_path), "underexposed.jpg")
    normal_result = svc.compute_scores(str(tmp_path), "normal.jpg")
    fracs = [under_result.underexposed_fraction, normal_result.underexposed_fraction]
    threshold = svc.relative_underexposed_threshold(fracs, top_percent=50)
    assert svc.is_underexposed(under_result, fraction_threshold=threshold) is True
    assert svc.is_underexposed(normal_result, fraction_threshold=threshold) is False


def test_relative_threshold_empty_list():
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    assert svc.relative_overexposed_threshold([], top_percent=50) == 1.0
    assert svc.relative_underexposed_threshold([], top_percent=50) == 1.0


def test_relative_threshold_single_element():
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    # With a single element the threshold must be just below that value,
    # so the element itself is flagged as the worst photo.
    assert svc.relative_overexposed_threshold([0.25], top_percent=50) == pytest.approx(0.25, abs=1e-6)
    assert svc.relative_underexposed_threshold([0.75], top_percent=50) == pytest.approx(0.75, abs=1e-6)


def test_relative_threshold_all_identical():
    from app.core.exposure_service import ExposureService
    svc = ExposureService()
    fracs = [0.5, 0.5, 0.5]
    # All values identical — threshold should be just below 0.5.
    over_threshold = svc.relative_overexposed_threshold(fracs, top_percent=50)
    under_threshold = svc.relative_underexposed_threshold(fracs, top_percent=50)
    assert over_threshold < 0.5
    assert under_threshold < 0.5
