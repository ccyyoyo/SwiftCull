import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")


def _make_clean_jpeg(tmp_path):
    """Smooth gradient — dominated by low frequencies → high SNR."""
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    for i in range(200):
        arr[i, :] = int(i * 255 / 199)
    path = tmp_path / "clean.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


def _make_noisy_jpeg(tmp_path):
    """Random pixel noise — flat frequency spectrum → low SNR."""
    rng = np.random.default_rng(42)
    arr = rng.integers(0, 256, (200, 200, 3), dtype=np.uint8)
    path = tmp_path / "noisy.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


def test_compute_score_clean_higher_than_noisy(tmp_path):
    from app.core.noise_service import NoiseService
    _make_clean_jpeg(tmp_path)
    _make_noisy_jpeg(tmp_path)
    svc = NoiseService()
    clean = svc.compute_score(str(tmp_path), "clean.jpg")
    noisy = svc.compute_score(str(tmp_path), "noisy.jpg")
    assert clean is not None
    assert noisy is not None
    assert clean > noisy


def test_compute_score_returns_non_negative_float(tmp_path):
    from app.core.noise_service import NoiseService
    _make_clean_jpeg(tmp_path)
    svc = NoiseService()
    score = svc.compute_score(str(tmp_path), "clean.jpg")
    assert isinstance(score, float)
    assert score >= 0.0


def test_is_noisy_fixed_below_threshold(tmp_path):
    from app.core.noise_service import NoiseService
    _make_noisy_jpeg(tmp_path)
    svc = NoiseService()
    score = svc.compute_score(str(tmp_path), "noisy.jpg")
    assert score is not None
    assert svc.is_noisy_fixed(score, threshold=10.0) is True


def test_is_noisy_fixed_above_threshold(tmp_path):
    from app.core.noise_service import NoiseService
    _make_clean_jpeg(tmp_path)
    svc = NoiseService()
    score = svc.compute_score(str(tmp_path), "clean.jpg")
    assert score is not None
    assert svc.is_noisy_fixed(score, threshold=0.0) is False


def test_is_noisy_fixed_none_returns_false():
    from app.core.noise_service import NoiseService
    svc = NoiseService()
    assert svc.is_noisy_fixed(None, threshold=1.0) is False


def test_relative_threshold_ignores_none_and_selects_bottom_percentile():
    from app.core.noise_service import NoiseService
    threshold = NoiseService().relative_threshold(
        [None, 0.05, 0.5, 5.0],
        bottom_percent=40.0,
    )
    assert 0.05 < threshold < 0.5


def test_compute_score_returns_none_for_missing_file(tmp_path):
    from app.core.noise_service import NoiseService
    svc = NoiseService()
    result = svc.compute_score(str(tmp_path), "nonexistent.jpg")
    assert result is None


def test_compute_score_returns_none_for_invalid_file(tmp_path):
    from app.core.noise_service import NoiseService
    p = tmp_path / "shot.CR2"
    p.write_bytes(b"not a real raw file")
    svc = NoiseService()
    result = svc.compute_score(str(tmp_path), "shot.CR2")
    assert result is None


def test_compute_score_reads_unicode_filename(tmp_path):
    from app.core.noise_service import NoiseService
    arr = np.zeros((50, 50, 3), dtype=np.uint8)
    for i in range(50):
        arr[i, :] = int(i * 255 / 49)
    encoded = cv2.imencode(".jpg", arr)[1]
    path = tmp_path / "60919-0012_調整大小.jpg"
    encoded.tofile(str(path))
    svc = NoiseService()
    result = svc.compute_score(str(tmp_path), path.name)
    assert isinstance(result, float)
