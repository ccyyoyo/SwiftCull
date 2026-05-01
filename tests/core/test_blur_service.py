import numpy as np
import cv2


def _make_sharp_jpeg(tmp_path):
    """Checkerboard pattern — high frequency = high Laplacian variance."""
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    for i in range(200):
        for j in range(200):
            arr[i, j] = 255 if (i // 10 + j // 10) % 2 == 0 else 0
    path = tmp_path / "sharp.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


def _make_blurry_jpeg(tmp_path):
    """Solid color — zero variance = maximum blur."""
    arr = np.full((200, 200, 3), 128, dtype=np.uint8)
    path = tmp_path / "blurry.jpg"
    cv2.imwrite(str(path), arr)
    return str(path)


def test_compute_score_sharp_higher_than_blurry(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    _make_blurry_jpeg(tmp_path)
    svc = BlurService()
    sharp = svc.compute_score(str(tmp_path), "sharp.jpg")
    blurry = svc.compute_score(str(tmp_path), "blurry.jpg")
    assert sharp > blurry


def test_compute_score_returns_float(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    svc = BlurService()
    score = svc.compute_score(str(tmp_path), "sharp.jpg")
    assert isinstance(score, float)
    assert score >= 0.0


def test_is_blurry_fixed_mode(tmp_path):
    from app.core.blur_service import BlurService
    _make_blurry_jpeg(tmp_path)
    svc = BlurService()
    score = svc.compute_score(str(tmp_path), "blurry.jpg")
    assert svc.is_blurry_fixed(score, threshold=100.0) is True


def test_is_blurry_fixed_mode_sharp(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    svc = BlurService()
    score = svc.compute_score(str(tmp_path), "sharp.jpg")
    assert svc.is_blurry_fixed(score, threshold=10.0) is False


def test_classify_relative(tmp_path):
    from app.core.blur_service import BlurService
    _make_sharp_jpeg(tmp_path)
    _make_blurry_jpeg(tmp_path)
    svc = BlurService()
    scores = [svc.compute_score(str(tmp_path), "blurry.jpg"),
              svc.compute_score(str(tmp_path), "sharp.jpg")]
    threshold = svc.relative_threshold(scores, bottom_percent=50)
    assert svc.is_blurry_fixed(scores[0], threshold) is True
    assert svc.is_blurry_fixed(scores[1], threshold) is False


def test_compute_score_returns_none_for_missing_file(tmp_path):
    from app.core.blur_service import BlurService
    svc = BlurService()
    result = svc.compute_score(str(tmp_path), "nonexistent.jpg")
    assert result is None


def test_compute_score_returns_none_for_unreadable_raw(tmp_path):
    from app.core.blur_service import BlurService
    # Write a file that is not a valid image
    p = tmp_path / "shot.CR2"
    p.write_bytes(b"not a real raw file")
    svc = BlurService()
    result = svc.compute_score(str(tmp_path), "shot.CR2")
    assert result is None


def test_compute_score_reads_unicode_filename(tmp_path):
    from app.core.blur_service import BlurService

    arr = np.full((20, 20, 3), 128, dtype=np.uint8)
    encoded = cv2.imencode(".jpg", arr)[1]
    path = tmp_path / "60919-0012_調整大小.jpg"
    encoded.tofile(str(path))

    svc = BlurService()
    result = svc.compute_score(str(tmp_path), path.name)

    assert isinstance(result, float)
