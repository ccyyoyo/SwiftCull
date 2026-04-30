"""Unit tests for RecentProjects.

Uses an in-memory dict in place of SettingsDB to keep the test pure-logic.
"""

from datetime import datetime, timezone
from pathlib import Path

from app.core.recent_projects import (
    RecentProjects, RecentProject, MAX_RECENT,
)


class FakeSettings:
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


def _norm(p) -> str:
    return str(Path(str(p)).resolve())


def test_empty_initially():
    rp = RecentProjects(FakeSettings())
    assert rp.list_all() == []
    assert rp.list_existing() == []


def test_add_creates_entry(tmp_path):
    rp = RecentProjects(FakeSettings())
    rp.add(str(tmp_path))
    items = rp.list_all()
    assert len(items) == 1
    assert items[0].path == _norm(tmp_path)
    assert items[0].opened_at  # non-empty timestamp


def test_add_same_folder_twice_keeps_one_at_front(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    rp = RecentProjects(FakeSettings())

    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t3 = datetime(2026, 12, 1, tzinfo=timezone.utc)

    rp.add(str(a), now=t1)
    rp.add(str(b), now=t2)
    rp.add(str(a), now=t3)

    paths = [p.path for p in rp.list_all()]
    assert paths == [_norm(a), _norm(b)]
    # most-recent timestamp wins for the deduped entry
    assert rp.list_all()[0].opened_at == t3.isoformat()


def test_max_recent_enforced(tmp_path):
    rp = RecentProjects(FakeSettings())
    folders = []
    for i in range(MAX_RECENT + 5):
        f = tmp_path / f"p{i:02d}"
        f.mkdir()
        folders.append(f)
        rp.add(str(f))
    items = rp.list_all()
    assert len(items) == MAX_RECENT
    # newest first → last-added is item[0]
    assert items[0].path == _norm(folders[-1])


def test_list_existing_filters_missing(tmp_path):
    a = tmp_path / "alive"; a.mkdir()
    rp = RecentProjects(FakeSettings())
    rp.add(str(a))
    rp.add(str(tmp_path / "ghost"))  # never created
    all_paths = [p.path for p in rp.list_all()]
    existing = [p.path for p in rp.list_existing()]
    assert _norm(a) in existing
    assert _norm(tmp_path / "ghost") in all_paths
    assert _norm(tmp_path / "ghost") not in existing


def test_remove(tmp_path):
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    rp = RecentProjects(FakeSettings())
    rp.add(str(a))
    rp.add(str(b))
    rp.remove(str(a))
    paths = [p.path for p in rp.list_all()]
    assert paths == [_norm(b)]


def test_remove_unknown_is_noop(tmp_path):
    rp = RecentProjects(FakeSettings())
    rp.add(str(tmp_path))
    rp.remove(str(tmp_path / "never-existed"))
    assert len(rp.list_all()) == 1


def test_prune_missing(tmp_path):
    a = tmp_path / "alive"; a.mkdir()
    rp = RecentProjects(FakeSettings())
    rp.add(str(tmp_path / "ghost"))
    rp.add(str(a))
    rp.prune_missing()
    paths = [p.path for p in rp.list_all()]
    assert paths == [_norm(a)]


def test_add_ignores_empty_path():
    rp = RecentProjects(FakeSettings())
    rp.add("")
    assert rp.list_all() == []


def test_corrupt_settings_value_returns_empty():
    fake = FakeSettings()
    fake.set("recent_folders", "not-a-list")
    rp = RecentProjects(fake)
    assert rp.list_all() == []


def test_dataclass_helpers(tmp_path):
    p = RecentProject(path=str(tmp_path), opened_at="2026-01-01T00:00:00+00:00")
    assert p.name == tmp_path.name
    assert p.exists() is True

    p2 = RecentProject(path=str(tmp_path / "nope"), opened_at="x")
    assert p2.exists() is False
