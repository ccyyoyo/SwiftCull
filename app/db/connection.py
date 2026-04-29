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
    # Migration: add blur_score if absent (safe on existing DBs)
    try:
        conn.execute("ALTER TABLE photos ADD COLUMN blur_score REAL")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
