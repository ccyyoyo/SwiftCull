import sqlite3
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS photos (
            id            INTEGER PRIMARY KEY,
            relative_path TEXT UNIQUE NOT NULL,
            filename      TEXT NOT NULL,
            file_size     INTEGER NOT NULL,
            mtime         REAL,
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
        CREATE TABLE IF NOT EXISTS tags (
            id         INTEGER PRIMARY KEY,
            photo_id   INTEGER NOT NULL REFERENCES photos(id),
            status     TEXT CHECK(status IN ('pick','reject','maybe')),
            color      TEXT CHECK(color IN ('red','orange','yellow','green','blue','purple')),
            updated_at TEXT
        );
    """)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply additive schema migrations for existing project DBs.

    SQLite ALTER TABLE ADD COLUMN is safe and cheap; we only run it when
    the column is missing so reopening a fresh DB is a no-op.
    """
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(photos)")}
    if "mtime" not in cols:
        conn.execute("ALTER TABLE photos ADD COLUMN mtime REAL")
