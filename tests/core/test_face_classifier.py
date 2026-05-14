from app.core.face_service import FaceService
from app.core.models import Photo


def _photo(*, analyzed: bool, count=None, area=None, closed=None) -> Photo:
    return Photo(
        id=1, relative_path="x.jpg", filename="x.jpg", file_size=0,
        face_count=count,
        face_max_area=area,
        face_eyes_closed_count=closed,
        face_analyzed=analyzed,
    )


# --- face_states ---

def test_states_unanalyzed_when_flag_false():
    p = _photo(analyzed=False)
    assert FaceService.face_states(p) == {"unanalyzed"}


def test_states_unanalyzed_even_if_count_set_but_flag_false():
    """Defensive: if flag is False, treat as unanalyzed regardless of stale values."""
    p = _photo(analyzed=False, count=2, area=0.1, closed=0)
    assert FaceService.face_states(p) == {"unanalyzed"}


def test_states_no_face_when_zero_count():
    p = _photo(analyzed=True, count=0, area=0.0, closed=0)
    assert FaceService.face_states(p) == {"no_face"}


def test_states_has_face_when_count_positive():
    p = _photo(analyzed=True, count=1, area=0.15, closed=0)
    assert FaceService.face_states(p) == {"has_face"}


def test_states_eyes_closed_added_when_threshold_met():
    p = _photo(analyzed=True, count=2, area=0.2, closed=1)
    states = FaceService.face_states(p, eyes_closed_threshold=1)
    assert "has_face" in states
    assert "eyes_closed" in states


def test_states_eyes_closed_not_added_below_threshold():
    p = _photo(analyzed=True, count=2, area=0.2, closed=0)
    states = FaceService.face_states(p, eyes_closed_threshold=1)
    assert "has_face" in states
    assert "eyes_closed" not in states


def test_states_eyes_closed_threshold_two():
    p = _photo(analyzed=True, count=3, area=0.2, closed=1)
    assert "eyes_closed" not in FaceService.face_states(p, eyes_closed_threshold=2)
    p2 = _photo(analyzed=True, count=3, area=0.2, closed=2)
    assert "eyes_closed" in FaceService.face_states(p2, eyes_closed_threshold=2)


def test_states_no_face_does_not_get_eyes_closed():
    """Eyes-closed only makes sense for photos with faces."""
    p = _photo(analyzed=True, count=0, area=0.0, closed=0)
    states = FaceService.face_states(p)
    assert "no_face" in states
    assert "eyes_closed" not in states


def test_states_null_closed_count_treated_as_zero():
    """face_eyes_closed_count being None (legacy row) must not crash."""
    p = _photo(analyzed=True, count=1, area=0.1, closed=None)
    states = FaceService.face_states(p)
    assert "has_face" in states
    assert "eyes_closed" not in states


# --- face_display_state ---

def test_display_priority_unanalyzed_first():
    p = _photo(analyzed=False, count=2, area=0.2, closed=2)
    assert FaceService.face_display_state(p) == "unanalyzed"


def test_display_priority_eyes_closed_over_has_face():
    p = _photo(analyzed=True, count=1, area=0.15, closed=1)
    assert FaceService.face_display_state(p) == "eyes_closed"


def test_display_priority_has_face_when_no_eyes_closed():
    p = _photo(analyzed=True, count=1, area=0.15, closed=0)
    assert FaceService.face_display_state(p) == "has_face"


def test_display_no_face_for_zero_count():
    p = _photo(analyzed=True, count=0, area=0.0, closed=0)
    assert FaceService.face_display_state(p) == "no_face"
