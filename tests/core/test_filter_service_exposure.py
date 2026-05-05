from unittest.mock import MagicMock
from app.core.models import Photo, Tag
from app.core.filter_service import FilterService


def _photo(pid, mean, over, under):
    return Photo(
        id=pid, relative_path=f"{pid}.jpg", filename=f"{pid}.jpg",
        file_size=0, mtime=None, shot_at=None, imported_at=None,
        width=None, height=None, camera_model=None, lens_model=None,
        iso=None, aperture=None, shutter_speed=None, focal_length=None,
        blur_score=None,
        exposure_mean=mean,
        exposure_overexposed=over,
        exposure_underexposed=under,
    )


def _make_svc(photos):
    photo_repo = MagicMock()
    photo_repo.get_all.return_value = photos
    tag_repo = MagicMock()
    tag_repo.get_by_photo_id.return_value = None
    return FilterService(photo_repo, tag_repo)


def test_exposure_filter_none_returns_all():
    p1 = _photo(1, 128.0, 0.0, 0.0)
    svc = _make_svc([p1])
    result = svc.filter(exposure=None)
    assert len(result) == 1


def test_exposure_filter_unanalyzed():
    p_none = _photo(1, None, None, None)
    p_normal = _photo(2, 128.0, 0.0, 0.0)
    svc = _make_svc([p_none, p_normal])
    result = svc.filter(exposure=["unanalyzed"])
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_overexposed():
    p_over = _photo(1, 240.0, 0.05, 0.0)
    p_normal = _photo(2, 128.0, 0.0, 0.0)
    svc = _make_svc([p_over, p_normal])
    result = svc.filter(exposure=["overexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_underexposed():
    p_under = _photo(1, 20.0, 0.0, 0.05)
    p_normal = _photo(2, 128.0, 0.0, 0.0)
    svc = _make_svc([p_under, p_normal])
    result = svc.filter(exposure=["underexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_black_frame():
    p_black = _photo(1, 3.0, 0.0, 0.95)
    p_dark = _photo(2, 20.0, 0.0, 0.05)  # underexposed but not black
    svc = _make_svc([p_black, p_dark])
    result = svc.filter(
        exposure=["black_frame"],
        exposure_clip_threshold=0.01,
        exposure_black_mean_threshold=8.0,
        exposure_black_shadow_threshold=0.90,
    )
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_filter_underexposed_includes_black_frame():
    p_black = _photo(1, 3.0, 0.0, 0.95)
    svc = _make_svc([p_black])
    result = svc.filter(
        exposure=["underexposed"],
        exposure_clip_threshold=0.01,
        exposure_black_mean_threshold=8.0,
        exposure_black_shadow_threshold=0.90,
    )
    assert len(result) == 1


def test_exposure_filter_normal():
    p_normal = _photo(1, 128.0, 0.0, 0.0)
    p_over = _photo(2, 240.0, 0.05, 0.0)
    svc = _make_svc([p_normal, p_over])
    result = svc.filter(exposure=["normal"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids


def test_exposure_or_semantics_multiple_values():
    p_over = _photo(1, 240.0, 0.05, 0.0)
    p_under = _photo(2, 20.0, 0.0, 0.05)
    p_normal = _photo(3, 128.0, 0.0, 0.0)
    svc = _make_svc([p_over, p_under, p_normal])
    result = svc.filter(exposure=["overexposed", "underexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 in ids
    assert 3 not in ids


def test_exposure_and_status_and_semantics():
    p_over_pick = _photo(1, 240.0, 0.05, 0.0)
    p_over_reject = _photo(2, 240.0, 0.05, 0.0)

    photo_repo = MagicMock()
    photo_repo.get_all.return_value = [p_over_pick, p_over_reject]
    tag_repo = MagicMock()

    tag_pick = Tag(photo_id=1, status="pick", color=None, updated_at=None)
    tag_reject = Tag(photo_id=2, status="reject", color=None, updated_at=None)
    tag_repo.get_by_photo_id.side_effect = lambda pid: {1: tag_pick, 2: tag_reject}[pid]

    svc = FilterService(photo_repo, tag_repo)
    result = svc.filter(statuses=["pick"], exposure=["overexposed"], exposure_clip_threshold=0.01)
    ids = [p.id for p in result]
    assert 1 in ids
    assert 2 not in ids
