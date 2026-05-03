import pytest
from unittest.mock import MagicMock
from app.core.tag_service import TagService


def _make_svc():
    repo = MagicMock()
    repo.get_by_photo_id.return_value = None
    return TagService(repo), repo


def test_batch_set_color_calls_set_color_for_each_id():
    svc, repo = _make_svc()
    tag1 = MagicMock(); tag1.color = None; tag1.status = None
    tag2 = MagicMock(); tag2.color = None; tag2.status = None
    repo.get_by_photo_id.side_effect = lambda pid: {1: tag1, 2: tag2}[pid]

    svc.batch_set_color([1, 2], "red")

    assert tag1.color == "red"
    assert tag2.color == "red"
    assert repo.upsert.call_count == 2


def test_batch_clear_color_sets_none():
    svc, repo = _make_svc()
    tag1 = MagicMock(); tag1.color = "blue"; tag1.status = "pick"
    repo.get_by_photo_id.return_value = tag1

    svc.batch_clear_color([1])

    assert tag1.color is None
    repo.upsert.assert_called_once()


def test_batch_set_color_invalid_raises():
    svc, _ = _make_svc()
    with pytest.raises(ValueError):
        svc.batch_set_color([1], "magenta")
