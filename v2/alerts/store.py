"""SQLite store for paid market/weather/quake alert subscriptions."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

_DB = Path(__file__).resolve().parents[2] / "queue" / "alert_subscriptions.sqlite3"

KINDS = frozenset({"fx", "gold", "weather", "quake"})
SCHEDULES = frozenset({"hourly", "daily", "weekly"})


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.row_factory = sqlite3.Row
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            asset TEXT NOT NULL DEFAULT '',
            schedule TEXT NOT NULL DEFAULT 'daily',
            spike_pct REAL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_sent_at REAL NOT NULL DEFAULT 0,
            last_price REAL,
            created_at REAL NOT NULL
        )
        """
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_user ON alert_subscriptions(user_id, enabled)"
    )
    return c


def count_user(user_id: int) -> int:
    conn = _conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM alert_subscriptions WHERE user_id=? AND enabled=1",
        (int(user_id),),
    ).fetchone()[0]
    conn.close()
    return int(n)


def add_alert(
    user_id: int,
    *,
    kind: str,
    asset: str,
    schedule: str = "daily",
    spike_pct: Optional[float] = None,
) -> tuple[bool, str]:
    kind = (kind or "").lower().strip()
    schedule = (schedule or "daily").lower().strip()
    if kind not in KINDS:
        return False, "bad_kind"
    if schedule not in SCHEDULES:
        return False, "bad_schedule"
    if count_user(user_id) >= 20:
        return False, "limit"
    conn = _conn()
    with conn:
        conn.execute(
            """
            INSERT INTO alert_subscriptions
            (user_id, kind, asset, schedule, spike_pct, enabled, last_sent_at, created_at)
            VALUES (?,?,?,?,?,1,0,?)
            """,
            (
                int(user_id),
                kind,
                (asset or "").strip()[:120],
                schedule,
                float(spike_pct) if spike_pct is not None else None,
                time.time(),
            ),
        )
    conn.close()
    return True, "ok"


def list_alerts(user_id: int) -> list[dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM alert_subscriptions WHERE user_id=? ORDER BY id DESC",
        (int(user_id),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_alert(user_id: int, alert_id: int) -> bool:
    conn = _conn()
    with conn:
        cur = conn.execute(
            "DELETE FROM alert_subscriptions WHERE id=? AND user_id=?",
            (int(alert_id), int(user_id)),
        )
    conn.close()
    return cur.rowcount > 0


def due_alerts(now: Optional[float] = None) -> list[dict[str, Any]]:
    now = now or time.time()
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM alert_subscriptions WHERE enabled=1"
    ).fetchall()
    conn.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        last = float(d.get("last_sent_at") or 0)
        sched = d.get("schedule") or "daily"
        interval = {"hourly": 3600, "daily": 86400, "weekly": 604800}.get(sched, 86400)
        # Always include if spike may fire; poller decides
        d["_interval"] = interval
        d["_schedule_due"] = (now - last) >= interval
        out.append(d)
    return out


def mark_sent(alert_id: int, *, price: Optional[float] = None) -> None:
    conn = _conn()
    with conn:
        if price is None:
            conn.execute(
                "UPDATE alert_subscriptions SET last_sent_at=? WHERE id=?",
                (time.time(), int(alert_id)),
            )
        else:
            conn.execute(
                "UPDATE alert_subscriptions SET last_sent_at=?, last_price=? WHERE id=?",
                (time.time(), float(price), int(alert_id)),
            )
    conn.close()
