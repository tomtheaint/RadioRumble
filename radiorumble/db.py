"""The small amount of state this app owns rather than reads.

Almost everything here comes from somewhere else: the rules from
``contest.toml``, the contacts from log files, the scores from arithmetic over
both. None of that belongs in a database, and putting it in one would only put
a query between a question and its answer.

Two things do not come from anywhere else. The fixture list, once it can be
written from the admin page rather than by hand-editing TOML, and the admin
password. Both are small, both must survive a restart, and both are read on
almost every request -- which is what a database is good at and what a JSON
file rewritten on every change is not.

Standard-library ``sqlite3``: no dependency, no server, one file in the data
directory. WAL because the web server reads on the event loop while the
watchdog thread may be writing, and the default journal mode makes those two
take turns.

The schema is created on first connect and only ever added to. There is no
migration tool here and there should not need to be one -- two tables that
change shape rarely do not justify Alembic.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT    NOT NULL DEFAULT '',
    teams      TEXT    NOT NULL DEFAULT '[]',   -- JSON array of abbreviations
    day        TEXT,                            -- ISO date, or NULL with a window
    start_at   TEXT,                            -- ISO datetime, UTC
    end_at     TEXT,
    is_open    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_matches_day ON matches (day);
"""


class Database:
    """One SQLite file, opened per thread.

    Per thread because sqlite3 connections are not shareable across them by
    default, and this app genuinely has two: uvicorn's event loop and the
    watchdog observer that notices the log file growing. A connection per
    thread is simpler than serialising every call through a lock, and with WAL
    they do not block each other anyway.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prepare()

    # -- connections ------------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        existing = getattr(self._local, "conn", None)
        if existing is not None:
            return existing
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        self._local.conn = conn
        return conn

    def _prepare(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        """Only the calling thread's connection; that is all it can reach."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # -- settings ---------------------------------------------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def delete_setting(self, key: str) -> None:
        self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.conn.commit()

    # -- matches ----------------------------------------------------------

    def add_match(self, *, label: str = "", teams=(), day: date | None = None,
                  start: datetime | None = None, end: datetime | None = None,
                  is_open: bool = False) -> int:
        """Store a fixture. Returns its id.

        Naming no teams means an open night -- the same rule the TOML loader
        applies, kept identical here so a fixture means the same thing whether
        it was typed into the page or into the file.
        """
        abbrs = [str(t).strip().upper() for t in teams if str(t).strip()]
        cur = self.conn.execute(
            "INSERT INTO matches (label, teams, day, start_at, end_at, is_open, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                label.strip(),
                json.dumps(abbrs),
                day.isoformat() if day else None,
                start.isoformat() if start else None,
                end.isoformat() if end else None,
                1 if (is_open or not abbrs) else 0,
                datetime.now().astimezone().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def all_matches(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM matches ORDER BY COALESCE(day, start_at, ''), id"
        ).fetchall()

    def delete_match(self, match_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        self.conn.commit()
        return cur.rowcount > 0
