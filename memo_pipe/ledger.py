"""SQLite ledger of processed recordings.

A file is only marked done after the full pipeline (transcribe + Devin session
creation) succeeds, so a crash mid-transcription leaves it eligible for retry
and each memo is processed exactly once.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed (
    sha256      TEXT PRIMARY KEY,
    path        TEXT NOT NULL,
    processed_at REAL NOT NULL,
    session_id  TEXT,
    session_url TEXT
);
CREATE TABLE IF NOT EXISTS failures (
    sha256     TEXT PRIMARY KEY,
    path       TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_attempt_at REAL
);
"""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Ledger:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def is_processed(self, sha256: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM processed WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return row is not None

    def mark_processed(
        self, sha256: str, path: Path, session_id: str, session_url: str
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO processed VALUES (?, ?, ?, ?, ?)",
                (sha256, str(path), time.time(), session_id, session_url),
            )
            self.conn.execute("DELETE FROM failures WHERE sha256 = ?", (sha256,))

    def record_failure(self, sha256: str, path: Path, error: str) -> int:
        """Record a failed attempt; returns the total attempt count."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO failures (sha256, path, attempts, last_error, last_attempt_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    attempts = attempts + 1,
                    last_error = excluded.last_error,
                    last_attempt_at = excluded.last_attempt_at
                """,
                (sha256, str(path), error, time.time()),
            )
        row = self.conn.execute(
            "SELECT attempts FROM failures WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return int(row[0])
