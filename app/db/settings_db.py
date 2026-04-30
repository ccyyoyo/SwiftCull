"""Global app settings storage.

Per Phase 1 spec: `%LOCALAPPDATA%\\SwiftCull\\settings.db` — a tiny SQLite
key-value store. The schema is one table `settings(key TEXT PK, value TEXT)`
storing values as UTF-8 strings (callers wrap with json.dumps when needed).

We also auto-migrate from the legacy `%APPDATA%\\SwiftCull\\settings.json`
the first time settings.db is opened so existing users don't lose their
"last_folder" preference.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional


def _local_app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return Path(base) / "SwiftCull"


def _legacy_json_path() -> Path:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return Path(base) / "SwiftCull" / "settings.json"


def default_db_path() -> Path:
    return _local_app_data_dir() / "settings.db"


class SettingsDB:
    """Tiny key/value store backed by SQLite."""

    def __init__(self, db_path: Optional[str] = None,
                 legacy_json_path: Optional[str] = None):
        self._db_path = Path(db_path) if db_path else default_db_path()
        self._legacy_json = (Path(legacy_json_path) if legacy_json_path
                             else _legacy_json_path())
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._maybe_import_legacy_json()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self._conn.commit()

    def _maybe_import_legacy_json(self) -> None:
        # Only attempt import if DB has no rows yet AND legacy file exists.
        row = self._conn.execute("SELECT COUNT(*) AS n FROM settings").fetchone()
        if row and int(row["n"]) > 0:
            return
        if not self._legacy_json.is_file():
            return
        try:
            data = json.loads(self._legacy_json.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        for k, v in data.items():
            if v is None:
                continue
            self.set(str(k), v)

    def get(self, key: str, default=None):
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return default
        raw = row["value"]
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def set(self, key: str, value) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        self._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, encoded),
        )
        self._conn.commit()

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM settings WHERE key=?", (key,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
