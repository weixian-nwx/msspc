"""SQLite persistence layer.

The database is the single source of truth. Every mutation is wrapped in a
committed transaction so an accidental exit (even mid-session) never loses data.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app import config


@dataclass
class Participant:
    qr_id: str
    name: str
    title: str
    grade: str
    seat_no: str
    bu: str
    row_index: int
    present: bool
    checkin_time: Optional[str]


class Database:
    def __init__(self, path: str) -> None:
        # check_same_thread=False: the scanner runs in a QThread but all writes
        # are funnelled through the main thread; reads stay simple.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS participants (
                qr_id        TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                title        TEXT NOT NULL,
                grade        TEXT NOT NULL,
                seat_no      TEXT NOT NULL DEFAULT '',
                bu           TEXT NOT NULL DEFAULT '',
                row_index    INTEGER NOT NULL,
                present      INTEGER NOT NULL DEFAULT 0,
                checkin_time TEXT
            );

            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS slide_mappings (
                grade          TEXT NOT NULL,
                role           TEXT NOT NULL,   -- present | absent
                kind           TEXT NOT NULL,   -- title | template
                slide_idx      INTEGER NOT NULL,
                name_shape_id  INTEGER,
                title_shape_id INTEGER,
                bu_shape_id    INTEGER,
                PRIMARY KEY (grade, role, kind)
            );
            """
        )
        self.conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Additively add columns introduced after a database was first created.

        Existing databases predate seat_no/bu and bu_shape_id; ALTER TABLE ADD
        COLUMN brings them up to date without losing any stored data.
        """
        additions = [
            ("participants", "seat_no", "TEXT NOT NULL DEFAULT ''"),
            ("participants", "bu", "TEXT NOT NULL DEFAULT ''"),
            ("slide_mappings", "bu_shape_id", "INTEGER"),
        ]
        for table, column, decl in additions:
            cols = {r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -------------------------------------------------------------------- meta
    def set_meta(self, key: str, value: Optional[str]) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def delete_meta(self, key: str) -> None:
        self.conn.execute("DELETE FROM meta WHERE key=?", (key,))
        self.conn.commit()

    # ------------------------------------------------------------ participants
    def replace_participants(self, rows: list[dict]) -> None:
        """Atomically replace the participant set from a freshly parsed excel.

        ``rows`` items must contain qr_id, name, title, grade, seat_no, bu, row_index.
        Clears any prior attendance because the roster has changed.
        """
        with self.conn:  # transaction
            self.conn.execute("DELETE FROM participants")
            self.conn.executemany(
                "INSERT INTO participants(qr_id, name, title, grade, seat_no, bu, row_index, present, checkin_time) "
                "VALUES(:qr_id, :name, :title, :grade, :seat_no, :bu, :row_index, 0, NULL)",
                rows,
            )

    def get_participant(self, qr_id: str) -> Optional[Participant]:
        row = self.conn.execute(
            "SELECT * FROM participants WHERE qr_id=?", (qr_id,)
        ).fetchone()
        return self._to_participant(row) if row else None

    def all_participants(self) -> list[Participant]:
        rows = self.conn.execute(
            "SELECT * FROM participants ORDER BY row_index"
        ).fetchall()
        return [self._to_participant(r) for r in rows]

    def distinct_grades(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT grade FROM participants ORDER BY grade"
        ).fetchall()
        return [r["grade"] for r in rows]

    def mark_present(self, qr_id: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "UPDATE participants SET present=1, checkin_time=? WHERE qr_id=?",
            (ts, qr_id),
        )
        self.conn.commit()

    def mark_absent(self, qr_id: str) -> None:
        """Single-row inverse of mark_present (for manual corrections)."""
        self.conn.execute(
            "UPDATE participants SET present=0, checkin_time=NULL WHERE qr_id=?",
            (qr_id,),
        )
        self.conn.commit()

    def counts(self) -> tuple[int, int]:
        """Return (present_count, total_count)."""
        total = self.conn.execute("SELECT COUNT(*) AS c FROM participants").fetchone()["c"]
        present = self.conn.execute(
            "SELECT COUNT(*) AS c FROM participants WHERE present=1"
        ).fetchone()["c"]
        return present, total

    def clear_attendance(self) -> None:
        self.conn.execute("UPDATE participants SET present=0, checkin_time=NULL")
        self.conn.commit()

    def clear_participants(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM participants")
            self.conn.execute("DELETE FROM slide_mappings")

    # --------------------------------------------------------- slide mappings
    def save_mapping(
        self,
        grade: str,
        role: str,
        kind: str,
        slide_idx: int,
        name_shape_id: Optional[int] = None,
        title_shape_id: Optional[int] = None,
        bu_shape_id: Optional[int] = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO slide_mappings(grade, role, kind, slide_idx, name_shape_id, title_shape_id, bu_shape_id) "
            "VALUES(?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(grade, role, kind) DO UPDATE SET "
            "slide_idx=excluded.slide_idx, name_shape_id=excluded.name_shape_id, "
            "title_shape_id=excluded.title_shape_id, bu_shape_id=excluded.bu_shape_id",
            (grade, role, kind, slide_idx, name_shape_id, title_shape_id, bu_shape_id),
        )
        self.conn.commit()

    def get_mappings(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM slide_mappings").fetchall()
        return [dict(r) for r in rows]

    def get_mapping(self, grade: str, role: str, kind: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM slide_mappings WHERE grade=? AND role=? AND kind=?",
            (grade, role, kind),
        ).fetchone()
        return dict(row) if row else None

    def clear_mappings(self) -> None:
        self.conn.execute("DELETE FROM slide_mappings")
        self.conn.commit()

    def mappings_complete(self) -> bool:
        """True if every distinct grade has all 4 (role, kind) slides mapped."""
        grades = self.distinct_grades()
        if not grades:
            return False
        mappings = self.get_mappings()
        existing = {(m["grade"], m["role"], m["kind"]) for m in mappings}
        for g in grades:
            for role in config.ROLES:
                for kind in config.KINDS:
                    if (g, role, kind) not in existing:
                        return False
        # Every template slide must also have all three shapes designated.
        for m in mappings:
            if m["kind"] == config.KIND_TEMPLATE:
                if (
                    m["name_shape_id"] is None
                    or m["title_shape_id"] is None
                    or m["bu_shape_id"] is None
                ):
                    return False
        return True

    # ----------------------------------------------------------------- helper
    @staticmethod
    def _to_participant(row: sqlite3.Row) -> Participant:
        return Participant(
            qr_id=row["qr_id"],
            name=row["name"],
            title=row["title"],
            grade=row["grade"],
            seat_no=row["seat_no"],
            bu=row["bu"],
            row_index=row["row_index"],
            present=bool(row["present"]),
            checkin_time=row["checkin_time"],
        )
