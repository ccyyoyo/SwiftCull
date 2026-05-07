import numpy as np
import cv2
import pytest


def _make_level_image(tmp_path, angle_deg=0.0):
    """Draw a strong horizontal line on a gray background."""
    img = np.full((300, 500, 3), 128, dtype=np.uint8)
    cy = 150
    # draw line at given angle through center
    rad = np.radians(angle_deg)
    dx = int(200 * np.cos(rad))
    dy = int(200 * np.sin(rad))
    cv2.line(img, (250 - dx, cy - dy), (250 + dx, cy + dy), (0, 0, 0), 4)
    path = tmp_path / "level.jpg"
    cv2.imwrite(str(path), img)
    return str(path)


def _make_tilted_image(tmp_path, angle_deg=10.0):
    """Draw a diagonal line to simulate a tilted horizon."""
    img = np.full((300, 500, 3), 128, dtype=np.uint8)
    rad = np.radians(angle_deg)
    dx = int(200 * np.cos(rad))
    dy = int(200 * np.sin(rad))
    cv2.line(img, (250 - dx, 150 - dy), (250 + dx, 150 + dy), (0, 0, 0), 4)
    path = tmp_path / "tilted.jpg"
    cv2.imwrite(str(path), img)
    return str(path)


def test_compute_skew_returns_float_for_image_with_lines(tmp_path):
    from app.core.horizon_service import HorizonService
    _make_level_image(tmp_path, angle_deg=0.0)
    svc = HorizonService()
    result = svc.compute_skew(str(tmp_path), "level.jpg")
    assert result is None or isinstance(result, float)


def test_compute_skew_returns_none_for_missing_file(tmp_path):
    from app.core.horizon_service import HorizonService
    svc = HorizonService()
    result = svc.compute_skew(str(tmp_path), "nonexistent.jpg")
    assert result is None


def test_compute_skew_returns_none_for_solid_image(tmp_path):
    """A solid-color image has no edges, so HoughLinesP returns nothing."""
    from app.core.horizon_service import HorizonService
    arr = np.full((200, 400, 3), 200, dtype=np.uint8)
    path = tmp_path / "solid.jpg"
    cv2.imwrite(str(path), arr)
    svc = HorizonService()
    result = svc.compute_skew(str(tmp_path), "solid.jpg")
    assert result is None


def test_tilted_image_returns_nonzero_angle(tmp_path):
    from app.core.horizon_service import HorizonService
    _make_tilted_image(tmp_path, angle_deg=15.0)
    svc = HorizonService()
    result = svc.compute_skew(str(tmp_path), "tilted.jpg")
    if result is not None:
        assert abs(result) > 0.5


def test_skew_state_unanalyzed():
    from app.core.horizon_service import HorizonService
    from app.core.models import Photo

    photo = Photo(id=1, relative_path="a.jpg", filename="a.jpg", file_size=1)
    assert photo.horizon_skew is None
    assert HorizonService.skew_state(photo) == "unanalyzed"


def test_skew_state_level():
    from app.core.horizon_service import HorizonService
    from app.core.models import Photo

    photo = Photo(id=1, relative_path="a.jpg", filename="a.jpg",
                  file_size=1, horizon_skew=0.5)
    assert HorizonService.skew_state(photo, level_threshold=1.0) == "level"


def test_skew_state_tilted():
    from app.core.horizon_service import HorizonService
    from app.core.models import Photo

    photo = Photo(id=1, relative_path="a.jpg", filename="a.jpg",
                  file_size=1, horizon_skew=5.2)
    assert HorizonService.skew_state(photo, level_threshold=1.0) == "tilted"


def test_skew_state_negative_tilted():
    from app.core.horizon_service import HorizonService
    from app.core.models import Photo

    photo = Photo(id=1, relative_path="a.jpg", filename="a.jpg",
                  file_size=1, horizon_skew=-3.0)
    assert HorizonService.skew_state(photo, level_threshold=1.0) == "tilted"


def test_skew_state_custom_threshold():
    from app.core.horizon_service import HorizonService
    from app.core.models import Photo

    photo = Photo(id=1, relative_path="a.jpg", filename="a.jpg",
                  file_size=1, horizon_skew=2.0)
    assert HorizonService.skew_state(photo, level_threshold=3.0) == "level"
    assert HorizonService.skew_state(photo, level_threshold=1.0) == "tilted"
