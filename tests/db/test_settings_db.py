import json

from app.db.settings_db import SettingsDB


def _new_db(tmp_path) -> SettingsDB:
    return SettingsDB(
        db_path=str(tmp_path / "settings.db"),
        legacy_json_path=str(tmp_path / "settings.json"),  # nonexistent
    )


def test_set_and_get_string(tmp_path):
    db = _new_db(tmp_path)
    db.set("last_folder", "D:/photos/2026")
    assert db.get("last_folder") == "D:/photos/2026"
    db.close()


def test_set_and_get_dict(tmp_path):
    db = _new_db(tmp_path)
    db.set("dont_ask", {"pick": True, "reject": False})
    assert db.get("dont_ask") == {"pick": True, "reject": False}
    db.close()


def test_get_missing_returns_default(tmp_path):
    db = _new_db(tmp_path)
    assert db.get("missing") is None
    assert db.get("missing", default="x") == "x"
    db.close()


def test_set_overwrites_existing(tmp_path):
    db = _new_db(tmp_path)
    db.set("k", "v1")
    db.set("k", "v2")
    assert db.get("k") == "v2"
    db.close()


def test_delete(tmp_path):
    db = _new_db(tmp_path)
    db.set("k", 1)
    db.delete("k")
    assert db.get("k") is None
    db.close()


def test_persistence_across_open(tmp_path):
    path = str(tmp_path / "p.db")
    legacy = str(tmp_path / "missing.json")
    db = SettingsDB(db_path=path, legacy_json_path=legacy)
    db.set("foo", [1, 2, 3])
    db.close()

    db2 = SettingsDB(db_path=path, legacy_json_path=legacy)
    try:
        assert db2.get("foo") == [1, 2, 3]
    finally:
        db2.close()


def test_legacy_json_imported_on_first_open(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text(
        json.dumps({"last_folder": "D:/oldproj", "extra": 42}),
        encoding="utf-8",
    )
    db = SettingsDB(
        db_path=str(tmp_path / "settings.db"),
        legacy_json_path=str(legacy),
    )
    try:
        assert db.get("last_folder") == "D:/oldproj"
        assert db.get("extra") == 42
    finally:
        db.close()


def test_legacy_json_not_reimported_when_db_already_has_data(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text(json.dumps({"last_folder": "D:/from-json"}),
                      encoding="utf-8")
    db_path = tmp_path / "settings.db"

    db = SettingsDB(db_path=str(db_path), legacy_json_path=str(legacy))
    db.set("last_folder", "D:/from-db")
    db.close()

    # Re-open: legacy import must NOT clobber what the DB has.
    db2 = SettingsDB(db_path=str(db_path), legacy_json_path=str(legacy))
    try:
        assert db2.get("last_folder") == "D:/from-db"
    finally:
        db2.close()


def test_legacy_json_corrupt_is_ignored(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text("{not valid json", encoding="utf-8")
    db = SettingsDB(
        db_path=str(tmp_path / "settings.db"),
        legacy_json_path=str(legacy),
    )
    try:
        assert db.get("last_folder") is None
    finally:
        db.close()


def test_context_manager_closes(tmp_path):
    path = str(tmp_path / "ctx.db")
    legacy = str(tmp_path / "missing.json")
    with SettingsDB(db_path=path, legacy_json_path=legacy) as db:
        db.set("k", "v")
    # Re-opening must succeed (i.e. file was released)
    db2 = SettingsDB(db_path=path, legacy_json_path=legacy)
    try:
        assert db2.get("k") == "v"
    finally:
        db2.close()


def test_db_file_created_in_chosen_directory(tmp_path):
    nested = tmp_path / "a" / "b"
    db = SettingsDB(
        db_path=str(nested / "settings.db"),
        legacy_json_path=str(tmp_path / "missing.json"),
    )
    try:
        assert (nested / "settings.db").is_file()
    finally:
        db.close()
