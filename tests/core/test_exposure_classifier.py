import pytest
import numpy as np


def _photo(mean, over, under):
    from app.core.models import Photo
    return Photo(
        id=1, relative_path="x.jpg", filename="x.jpg", file_size=0,
        mtime=None, shot_at=None, imported_at=None,
        width=None, height=None, camera_model=None, lens_model=None,
        iso=None, aperture=None, shutter_speed=None, focal_length=None,
        blur_score=None,
        exposure_mean=mean,
        exposure_overexposed=over,
        exposure_underexposed=under,
    )


# --- exposure_states ---

def test_states_unanalyzed_when_all_none():
    from app.core.exposure_service import ExposureService
    p = _photo(None, None, None)
    assert ExposureService.exposure_states(p) == {"unanalyzed"}


def test_states_unanalyzed_when_any_none():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, None, 0.0)
    assert ExposureService.exposure_states(p) == {"unanalyzed"}


def test_states_normal_for_well_exposed():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.0, 0.0)
    assert ExposureService.exposure_states(p) == {"normal"}


def test_states_overexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(240.0, 0.05, 0.0)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" in states
    assert "normal" not in states


def test_states_underexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(20.0, 0.0, 0.05)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "underexposed" in states
    assert "normal" not in states


def test_states_black_frame():
    from app.core.exposure_service import ExposureService
    p = _photo(3.0, 0.0, 0.95)
    states = ExposureService.exposure_states(
        p,
        clip_threshold=0.01,
        black_mean_threshold=8.0,
        black_shadow_threshold=0.90,
    )
    assert "black_frame" in states
    assert "underexposed" in states  # black_frame is underexposed subtype


def test_states_black_frame_not_included_in_overexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(3.0, 0.0, 0.95)
    states = ExposureService.exposure_states(p)
    assert "overexposed" not in states


def test_states_mixed_over_and_under():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.05, 0.05)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" in states
    assert "underexposed" in states


def test_states_boundary_exact_clip_threshold_not_overexposed():
    from app.core.exposure_service import ExposureService
    # Exactly at threshold is NOT overexposed (strict >)
    p = _photo(200.0, 0.01, 0.0)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" not in states


def test_states_boundary_just_above_clip_threshold_is_overexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(200.0, 0.011, 0.0)
    states = ExposureService.exposure_states(p, clip_threshold=0.01)
    assert "overexposed" in states


# --- exposure_display_state priority ---

def test_display_state_black_frame_wins_over_underexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(3.0, 0.0, 0.95)
    assert ExposureService.exposure_display_state(p) == "black_frame"


def test_display_state_overexposed_wins_over_underexposed():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.05, 0.05)
    assert ExposureService.exposure_display_state(p, clip_threshold=0.01) == "overexposed"


def test_display_state_normal():
    from app.core.exposure_service import ExposureService
    p = _photo(128.0, 0.0, 0.0)
    assert ExposureService.exposure_display_state(p) == "normal"


def test_display_state_unanalyzed():
    from app.core.exposure_service import ExposureService
    p = _photo(None, None, None)
    assert ExposureService.exposure_display_state(p) == "unanalyzed"
