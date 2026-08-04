"""Persist last FX calculator queries per user for quick-replay buttons."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_DB = Path(__file__).resolve().parents[2] / "queue" / "fx_recent.sqlite3"
_MAX = 6


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS fx_recent (
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            ts REAL NOT NULL,
            PRIMARY KEY (user_id, query)
        )
        """
    )
    return c


def push(user_id: int, query: str) -> None:
    q = (query or "").strip()[:80]
    if not q:
        return
    try:
        conn = _conn()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO fx_recent(user_id, query, ts) VALUES (?,?,?)",
                (int(user_id), q, time.time()),
            )
            conn.execute(
                """
                DELETE FROM fx_recent WHERE user_id=? AND query NOT IN (
                  SELECT query FROM fx_recent WHERE user_id=? ORDER BY ts DESC LIMIT ?
                )
                """,
                (int(user_id), int(user_id), _MAX),
            )
        conn.close()
    except Exception:
        pass


def list_recent(user_id: int, *, limit: int = 5) -> list[str]:
    try:
        conn = _conn()
        rows = conn.execute(
            "SELECT query FROM fx_recent WHERE user_id=? ORDER BY ts DESC LIMIT ?",
            (int(user_id), int(limit)),
        ).fetchall()
        conn.close()
        return [str(r[0]) for r in rows]
    except Exception:
        return []
