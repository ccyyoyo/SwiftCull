import sqlite3

from app.db.connection import get_connection, init_db


def _photo_columns(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(photos)")}


def test_wal_mode_enabled(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_tables_created(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    init_db(conn)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    conn.close()
    assert "photos" in tables
    assert "tags" in tables


def test_photos_has_mtime_column(tmp_path):
    conn = get_connection(str(tmp_path / "fresh.db"))
    init_db(conn)
    cols = _photo_columns(conn)
    conn.close()
    assert "mtime" in cols


def test_migration_adds_mtime_to_old_db(tmp_path):
    """A pre-mtime DB is upgraded in-place when init_db runs again."""
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE photos (
            id            INTEGER PRIMARY KEY,
            relative_path TEXT UNIQUE NOT NULL,
            filename      TEXT NOT NULL,
            file_size     INTEGER NOT NULL,
            shot_at       TEXT,
            imported_at   TEXT,
            width         INTEGER,
            height        INTEGER,
            camera_model  TEXT,
            lens_model    TEXT,
            iso           INTEGER,
            aperture      REAL,
            shutter_speed TEXT,
            focal_length  REAL
        );
    """)
    conn.execute(
        "INSERT INTO photos (relative_path, filename, file_size) VALUES (?,?,?)",
        ("legacy.jpg", "legacy.jpg", 100),
    )
    conn.commit()
    assert "mtime" not in _photo_columns(conn)

    init_db(conn)

    cols = _photo_columns(conn)
    assert "mtime" in cols
    row = conn.execute(
        "SELECT relative_path, mtime FROM photos WHERE relative_path=?",
        ("legacy.jpg",),
    ).fetchone()
    assert row["relative_path"] == "legacy.jpg"
    assert row["mtime"] is None
    conn.close()


def test_init_db_idempotent(tmp_path):
    """Running init_db twice on the same DB does not crash or duplicate columns."""
    db_path = str(tmp_path / "idem.db")
    conn = get_connection(db_path)
    init_db(conn)
    init_db(conn)
    cols = _photo_columns(conn)
    conn.close()
    assert "mtime" in cols
