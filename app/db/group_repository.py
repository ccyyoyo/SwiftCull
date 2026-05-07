import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class Group:
    id: int
    name: Optional[str]
    type: str
    created_at: str


class GroupRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create_group(self, name: Optional[str], group_type: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO groups (name, type, created_at) VALUES (?,?,?)",
            (name, group_type, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def add_photo_to_group(self, photo_id: int, group_id: int, is_best: bool = False) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO photo_groups (photo_id, group_id, is_best) VALUES (?,?,?)",
            (photo_id, group_id, 1 if is_best else 0),
        )
        self._conn.commit()

    def set_best_in_group(self, photo_id: int, group_id: int) -> None:
        self._conn.execute(
            "UPDATE photo_groups SET is_best=0 WHERE group_id=?", (group_id,)
        )
        self._conn.execute(
            "UPDATE photo_groups SET is_best=1 WHERE photo_id=? AND group_id=?",
            (photo_id, group_id),
        )
        self._conn.commit()

    def get_groups_by_type(self, group_type: str) -> List[Group]:
        rows = self._conn.execute(
            "SELECT * FROM groups WHERE type=? ORDER BY created_at", (group_type,)
        ).fetchall()
        return [Group(id=r["id"], name=r["name"], type=r["type"], created_at=r["created_at"]) for r in rows]

    def get_all_groups(self) -> List[Group]:
        rows = self._conn.execute(
            "SELECT * FROM groups ORDER BY type, created_at"
        ).fetchall()
        return [Group(id=r["id"], name=r["name"], type=r["type"], created_at=r["created_at"]) for r in rows]

    def get_photo_ids_in_group(self, group_id: int) -> List[int]:
        rows = self._conn.execute(
            "SELECT photo_id FROM photo_groups WHERE group_id=? ORDER BY is_best DESC, photo_id",
            (group_id,),
        ).fetchall()
        return [int(r["photo_id"]) for r in rows]

    def get_group_id_for_photo(self, photo_id: int, group_type: Optional[str] = None) -> Optional[int]:
        if group_type:
            row = self._conn.execute(
                "SELECT pg.group_id FROM photo_groups pg"
                " JOIN groups g ON pg.group_id=g.id"
                " WHERE pg.photo_id=? AND g.type=?",
                (photo_id, group_type),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT group_id FROM photo_groups WHERE photo_id=?", (photo_id,)
            ).fetchone()
        return int(row["group_id"]) if row else None

    def clear_groups_by_type(self, group_type: str) -> None:
        """Delete all groups of given type and their photo memberships (cascade)."""
        self._conn.execute(
            "DELETE FROM photo_groups WHERE group_id IN"
            " (SELECT id FROM groups WHERE type=?)",
            (group_type,),
        )
        self._conn.execute("DELETE FROM groups WHERE type=?", (group_type,))
        self._conn.commit()

    def count_photos_in_group(self, group_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM photo_groups WHERE group_id=?", (group_id,)
        ).fetchone()
        return int(row["n"]) if row else 0
