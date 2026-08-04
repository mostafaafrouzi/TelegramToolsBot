"""
Per-Telegram-user plan tiers, usage meters (day/month), and parallel job limits.
Uses the same SQLite file as the task queue. Successful uploads increment usage in rub.py.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

from queue_db import DB_FILE, QUEUE_DIR

PROCESSING_FILE = QUEUE_DIR / "processing.json"

DISABLE_USAGE_LIMITS = os.getenv("DISABLE_USAGE_LIMITS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

DEFAULT_TIER_FOR_NEW_USER = "free"

# toolkit/world daily: 0 = unlimited. feed_push_allowed: 0/1.
TIER_LIMITS: dict[str, dict[str, int]] = {
    "guest": {
        "quota_day_mb": 100,
        "quota_month_mb": 500,
        "max_file_mb": 50,
        "max_parallel": 1,
        "toolkit_daily_cmds": 15,
        "world_daily_cmds": 10,
        "feed_max": 5,
        "feed_push_allowed": 0,
    },
    "free": {
        "quota_day_mb": 500,
        "quota_month_mb": 5000,
        "max_file_mb": 500,
        "max_parallel": 2,
        "toolkit_daily_cmds": 40,
        "world_daily_cmds": 30,
        "feed_max": 20,
        "feed_push_allowed": 1,
    },
    "pro": {
        "quota_day_mb": 5000,
        "quota_month_mb": 50000,
        "max_file_mb": 2048,
        "max_parallel": 5,
        "toolkit_daily_cmds": 0,
        "world_daily_cmds": 0,
        "feed_max": 50,
        "feed_push_allowed": 1,
    },
    "star": {
        "quota_day_mb": 15000,
        "quota_month_mb": 120000,
        "max_file_mb": 2048,
        "max_parallel": 8,
        "toolkit_daily_cmds": 0,
        "world_daily_cmds": 0,
        "feed_max": 100,
        "feed_push_allowed": 1,
    },
}


@dataclass
class ResolvedLimits:
    tier: str
    quota_day_mb: int
    quota_month_mb: int
    max_file_mb: int
    max_parallel: int
    toolkit_daily_cmds: int
    world_daily_cmds: int
    feed_max: int
    feed_push_allowed: bool
    expires_at: int


def _parse_env_max_file_mb() -> Optional[int]:
    raw = (os.getenv("MAX_FILE_MB") or "").strip()
    if not raw or raw == "0":
        return None
    try:
        mb = int(raw)
        if mb <= 0:
            return None
        return mb
    except ValueError:
        return None


class UsageTables:
    """SQLite: user_entitlements + usage_ledger."""

    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_entitlements (
                    user_id INTEGER PRIMARY KEY,
                    tier TEXT NOT NULL DEFAULT 'free',
                    expires_at INTEGER NOT NULL DEFAULT 0,
                    bonus_month_mb INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_ledger (
                    user_id INTEGER NOT NULL,
                    bucket TEXT NOT NULL,
                    bytes_total INTEGER NOT NULL DEFAULT 0,
                    jobs INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, bucket)
                )
                """
            )
            conn.commit()


_usage_singleton: Optional[UsageTables] = None


def usage_store() -> UsageTables:
    global _usage_singleton
    if _usage_singleton is None:
        _usage_singleton = UsageTables()
    return _usage_singleton


def _day_key(ts: Optional[float] = None) -> str:
    t = time.gmtime((ts or time.time()))
    return f"d:{t.tm_year:04d}{t.tm_mon:02d}{t.tm_mday:02d}"


def _month_key(ts: Optional[float] = None) -> str:
    t = time.gmtime((ts or time.time()))
    return f"m:{t.tm_year:04d}{t.tm_mon:02d}"


def _effective_tier(row: Optional[sqlite3.Row]) -> str:
    if not row:
        return DEFAULT_TIER_FOR_NEW_USER
    tier = (row["tier"] or DEFAULT_TIER_FOR_NEW_USER).strip().lower()
    if tier not in TIER_LIMITS:
        tier = DEFAULT_TIER_FOR_NEW_USER
    exp = int(row["expires_at"] or 0)
    if tier in ("pro", "star") and exp > 0 and int(time.time()) > exp:
        return "free"
    return tier


def get_entitlement_row(user_id: int) -> Optional[sqlite3.Row]:
    store = usage_store()
    with store._connect() as conn:
        return conn.execute(
            "SELECT * FROM user_entitlements WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()


def _admin_ids() -> set[int]:
    raw = (os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or "").strip()
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out


def resolved_limits(user_id: int) -> ResolvedLimits:
    # Admins always receive top-tier (star) limits.
    if int(user_id) in _admin_ids():
        base = TIER_LIMITS["star"]
        return ResolvedLimits(
            tier="star",
            quota_day_mb=base["quota_day_mb"],
            quota_month_mb=base["quota_month_mb"],
            max_file_mb=base["max_file_mb"],
            max_parallel=base["max_parallel"],
            toolkit_daily_cmds=int(base.get("toolkit_daily_cmds", 0)),
            world_daily_cmds=int(base.get("world_daily_cmds", 0)),
            feed_max=int(base.get("feed_max", 100)),
            feed_push_allowed=True,
            expires_at=0,
        )
    row = get_entitlement_row(user_id)
    tier = _effective_tier(row)
    base = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    bonus = int(row["bonus_month_mb"] or 0) if row else 0
    exp = int(row["expires_at"] or 0) if row else 0
    return ResolvedLimits(
        tier=tier,
        quota_day_mb=base["quota_day_mb"],
        quota_month_mb=base["quota_month_mb"] + max(0, bonus),
        max_file_mb=base["max_file_mb"],
        max_parallel=base["max_parallel"],
        toolkit_daily_cmds=int(base.get("toolkit_daily_cmds", 0)),
        world_daily_cmds=int(base.get("world_daily_cmds", 0)),
        feed_max=int(base.get("feed_max", 20)),
        feed_push_allowed=bool(int(base.get("feed_push_allowed", 0))),
        expires_at=exp,
    )


def _parse_toolkit_daily_env_cap() -> int:
    try:
        return int((os.getenv("TOOLKIT_DAILY_LIMIT_PER_USER") or "0").strip())
    except ValueError:
        return 0


def effective_toolkit_daily_limit(user_id: int) -> int:
    """Max toolkit command invocations per UTC day. 0 = unlimited.

    Uses per-tier ``toolkit_daily_cmds`` (0 in tier = unlimited). Optional env
    ``TOOLKIT_DAILY_LIMIT_PER_USER`` (when > 0) applies as a hard ceiling for all tiers.
    """
    if DISABLE_USAGE_LIMITS:
        return 0
    tier_cap = int(resolved_limits(user_id).toolkit_daily_cmds)
    env_cap = _parse_toolkit_daily_env_cap()
    if env_cap > 0:
        if tier_cap <= 0:
            return env_cap
        return min(tier_cap, env_cap)
    return tier_cap


def effective_world_daily_limit(user_id: int) -> int:
    """Max World/FX tool invocations per UTC day. 0 = unlimited."""
    if DISABLE_USAGE_LIMITS:
        return 0
    return int(resolved_limits(user_id).world_daily_cmds)


def effective_feed_max(user_id: int) -> int:
    """Max saved feeds for user. Env WORLD_FEED_LIMIT_* can raise/override ceilings."""
    lim = resolved_limits(user_id)
    base = int(lim.feed_max)
    env_key = {
        "guest": "WORLD_FEED_LIMIT_GUEST",
        "free": "WORLD_FEED_LIMIT_FREE",
        "pro": "WORLD_FEED_LIMIT_PRO",
        "star": "WORLD_FEED_LIMIT_STAR",
    }.get(lim.tier, "WORLD_FEED_LIMIT_FREE")
    raw = (os.getenv(env_key) or "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return max(1, base)


def feed_push_allowed(user_id: int) -> bool:
    if DISABLE_USAGE_LIMITS:
        return True
    return bool(resolved_limits(user_id).feed_push_allowed)


def plan_matrix_text(*, lang: str = "fa") -> str:
    """Human-readable Free/Pro/Star comparison (guest omitted from marketing)."""
    blocks = []
    for tier in ("free", "pro", "star"):
        b = TIER_LIMITS[tier]
        tk = "∞" if int(b["toolkit_daily_cmds"]) == 0 else str(b["toolkit_daily_cmds"])
        wd = "∞" if int(b["world_daily_cmds"]) == 0 else str(b["world_daily_cmds"])
        if lang == "en":
            push = "yes" if b["feed_push_allowed"] else "no"
            blocks.append(
                f"▸ {tier.upper()}\n"
                f"  Transfer: {b['quota_day_mb']} / {b['quota_month_mb']} MB (day/mo)\n"
                f"  File: {b['max_file_mb']} MB · Parallel: {b['max_parallel']}\n"
                f"  Toolkit/day: {tk} · World/day: {wd}\n"
                f"  Feeds: {b['feed_max']} · Push: {push}"
            )
        else:
            push_fa = "بله" if b["feed_push_allowed"] else "خیر"
            blocks.append(
                f"▸ {tier.upper()}\n"
                f"  انتقال: {b['quota_day_mb']} / {b['quota_month_mb']} MB (روز/ماه)\n"
                f"  فایل: {b['max_file_mb']} MB · موازی: {b['max_parallel']}\n"
                f"  ابزار/روز: {tk} · جهان/روز: {wd}\n"
                f"  فید: {b['feed_max']} · Push: {push_fa}"
            )
    return "\n\n".join(blocks)


def get_usage_snapshot(user_id: int) -> dict[str, Any]:
    store = usage_store()
    dk, mk = _day_key(), _month_key()
    with store._connect() as conn:
        drow = conn.execute(
            "SELECT bytes_total, jobs FROM usage_ledger WHERE user_id = ? AND bucket = ?",
            (int(user_id), dk),
        ).fetchone()
        mrow = conn.execute(
            "SELECT bytes_total, jobs FROM usage_ledger WHERE user_id = ? AND bucket = ?",
            (int(user_id), mk),
        ).fetchone()
    day_b = int(drow["bytes_total"] or 0) if drow else 0
    day_j = int(drow["jobs"] or 0) if drow else 0
    month_b = int(mrow["bytes_total"] or 0) if mrow else 0
    month_j = int(mrow["jobs"] or 0) if mrow else 0
    lim = resolved_limits(user_id)
    return {
        "tier": lim.tier,
        "expires_at": lim.expires_at,
        "day_bytes": day_b,
        "month_bytes": month_b,
        "day_jobs": day_j,
        "month_jobs": month_j,
        "quota_day_mb": lim.quota_day_mb,
        "quota_month_mb": lim.quota_month_mb,
        "max_file_mb": lim.max_file_mb,
        "max_parallel": lim.max_parallel,
        "toolkit_daily_cmds": lim.toolkit_daily_cmds,
        "world_daily_cmds": lim.world_daily_cmds,
        "feed_max": lim.feed_max,
        "feed_push_allowed": lim.feed_push_allowed,
    }


def record_successful_upload_bytes(user_id: int, byte_count: int) -> None:
    if DISABLE_USAGE_LIMITS or byte_count <= 0:
        return
    store = usage_store()
    b = int(byte_count)
    dk, mk = _day_key(), _month_key()
    with store._lock:
        with store._connect() as conn:
            for bucket in (dk, mk):
                conn.execute(
                    """
                    INSERT INTO usage_ledger (user_id, bucket, bytes_total, jobs)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id, bucket) DO UPDATE SET
                      bytes_total = usage_ledger.bytes_total + excluded.bytes_total,
                      jobs = usage_ledger.jobs + 1
                    """,
                    (int(user_id), bucket, b),
                )
            conn.commit()


def list_expiring_paid_tiers(*, within_sec: int = 3 * 86400, limit: int = 100) -> list[dict[str, Any]]:
    """Users on pro/star whose expires_at is in (now, now+within_sec]."""
    store = usage_store()
    now = int(time.time())
    until = now + max(0, int(within_sec))
    with store._connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id, tier, expires_at FROM user_entitlements
            WHERE tier IN ('pro', 'star')
              AND expires_at > ?
              AND expires_at <= ?
            ORDER BY expires_at ASC
            LIMIT ?
            """,
            (now, until, max(1, int(limit))),
        ).fetchall()
    return [
        {
            "user_id": int(r["user_id"]),
            "tier": str(r["tier"]),
            "expires_at": int(r["expires_at"] or 0),
        }
        for r in rows
    ]


def list_tier_user_ids(tier: str, *, limit: int = 5000) -> list[int]:
    """User ids whose stored tier equals ``tier`` (not effective/expired remap)."""
    t = (tier or "").strip().lower()
    if t not in TIER_LIMITS:
        return []
    store = usage_store()
    with store._connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id FROM user_entitlements
            WHERE lower(tier) = ?
            ORDER BY user_id ASC
            LIMIT ?
            """,
            (t, max(1, int(limit))),
        ).fetchall()
    return [int(r["user_id"]) for r in rows]


def list_expired_paid_user_ids(*, limit: int = 5000) -> list[int]:
    """pro/star rows whose expires_at is in the past (still stored as paid tier)."""
    store = usage_store()
    now = int(time.time())
    with store._connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id FROM user_entitlements
            WHERE tier IN ('pro', 'star')
              AND expires_at > 0
              AND expires_at <= ?
            ORDER BY expires_at DESC
            LIMIT ?
            """,
            (now, max(1, int(limit))),
        ).fetchall()
    return [int(r["user_id"]) for r in rows]


def tier_counts() -> dict[str, int]:
    store = usage_store()
    out = {k: 0 for k in TIER_LIMITS}
    with store._connect() as conn:
        rows = conn.execute(
            "SELECT lower(tier) AS t, COUNT(1) AS c FROM user_entitlements GROUP BY lower(tier)"
        ).fetchall()
    for r in rows:
        t = str(r["t"] or "")
        if t in out:
            out[t] = int(r["c"] or 0)
    return out


def set_user_tier(user_id: int, tier: str, expires_at: int = 0) -> None:
    tier = tier.strip().lower()
    if tier not in TIER_LIMITS:
        tier = "free"
    store = usage_store()
    now = int(time.time())
    uid = int(user_id)
    with store._lock:
        with store._connect() as conn:
            row = conn.execute(
                "SELECT bonus_month_mb FROM user_entitlements WHERE user_id = ?",
                (uid,),
            ).fetchone()
            bonus = int(row["bonus_month_mb"] or 0) if row else 0
            conn.execute(
                """
                INSERT INTO user_entitlements (user_id, tier, expires_at, bonus_month_mb, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  tier = excluded.tier,
                  expires_at = excluded.expires_at,
                  updated_at = excluded.updated_at
                """,
                (uid, tier, int(expires_at), bonus, now),
            )
            conn.commit()


def add_bonus_month_mb(user_id: int, mb: int) -> None:
    if mb == 0:
        return
    store = usage_store()
    now = int(time.time())
    with store._lock:
        with store._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_entitlements (user_id, tier, expires_at, bonus_month_mb, updated_at)
                VALUES (?, 'free', 0, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  bonus_month_mb = bonus_month_mb + excluded.bonus_month_mb,
                  updated_at = excluded.updated_at
                """,
                (int(user_id), int(mb), now),
            )
            conn.commit()


def processing_matches_user(telegram_user_id: int) -> bool:
    if not PROCESSING_FILE.exists():
        return False
    try:
        data = json.loads(PROCESSING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False
    uid = data.get("telegram_user_id")
    if uid is None:
        uid = data.get("chat_id")
    try:
        return int(uid or 0) == int(telegram_user_id)
    except (TypeError, ValueError):
        return False


def parallel_job_count(telegram_user_id: int, queue) -> int:
    n = queue.count_tasks_for_user(int(telegram_user_id))
    if processing_matches_user(telegram_user_id):
        n += 1
    return n


def effective_max_file_bytes(user_id: int) -> Optional[int]:
    """
    Hard cap for one queued file (bytes). None = no cap from tier/env combo.
    """
    env_cap = _parse_env_max_file_mb()
    if DISABLE_USAGE_LIMITS:
        if env_cap is None:
            return None
        return env_cap * 1024 * 1024
    tier_mb = resolved_limits(user_id).max_file_mb
    if env_cap is None:
        return tier_mb * 1024 * 1024
    return min(env_cap * 1024 * 1024, tier_mb * 1024 * 1024)


def can_enqueue(
    user_id: int,
    job_bytes_estimate: int,
    queue,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Returns (ok, reason_code, detail) — reason_code for i18n key suffix or literal.
    """
    detail: dict[str, Any] = {"limits": resolved_limits(user_id).__dict__}
    detail.update(get_usage_snapshot(user_id))

    if DISABLE_USAGE_LIMITS:
        return True, "ok", detail

    lim = resolved_limits(user_id)
    env_cap = _parse_env_max_file_mb()
    tier_cap_mb = lim.max_file_mb
    caps_mb = [tier_cap_mb]
    if env_cap is not None:
        caps_mb.append(env_cap)
    eff_mb = min(caps_mb)
    if job_bytes_estimate > eff_mb * 1024 * 1024:
        detail["max_mb"] = eff_mb
        detail["need_mb"] = f"{job_bytes_estimate / (1024 * 1024):.1f}"
        return False, "quota_file_cap", detail

    par = parallel_job_count(user_id, queue)
    if par >= lim.max_parallel:
        detail["parallel"] = par
        detail["max_parallel"] = lim.max_parallel
        return False, "quota_parallel", detail

    snap = get_usage_snapshot(user_id)
    day_b = int(snap["day_bytes"])
    month_b = int(snap["month_bytes"])
    day_limit = lim.quota_day_mb * 1024 * 1024
    month_limit = lim.quota_month_mb * 1024 * 1024

    if day_b + job_bytes_estimate > day_limit:
        detail["remain_day_mb"] = max(0, (day_limit - day_b) / (1024 * 1024))
        detail["need_mb"] = f"{job_bytes_estimate / (1024 * 1024):.1f}"
        return False, "quota_day", detail

    if month_b + job_bytes_estimate > month_limit:
        detail["remain_month_mb"] = max(0, (month_limit - month_b) / (1024 * 1024))
        detail["need_mb"] = f"{job_bytes_estimate / (1024 * 1024):.1f}"
        return False, "quota_month", detail

    # Soft warning when projected usage crosses 80% of day or month caps.
    warn_codes: list[str] = []
    if day_limit > 0 and (day_b + job_bytes_estimate) / day_limit >= 0.8:
        warn_codes.append("day")
        detail["day_pct"] = round(100.0 * (day_b + job_bytes_estimate) / day_limit, 1)
    if month_limit > 0 and (month_b + job_bytes_estimate) / month_limit >= 0.8:
        warn_codes.append("month")
        detail["month_pct"] = round(100.0 * (month_b + job_bytes_estimate) / month_limit, 1)
    if warn_codes:
        detail["quota_soft_warn"] = warn_codes
        return True, "ok_warn", detail

    return True, "ok", detail


def estimate_task_bytes(task: dict) -> int:
    """Best-effort bytes counted against quota (successful completion)."""
    t = task.get("type")
    if t == "text_message":
        return min(4096, len((task.get("text") or "").encode("utf-8")))
    if t in {"local_file", "transfer_to_bale", "transfer_to_drive", "ssh_put"}:
        return int(task.get("file_size") or 0)
    if t == "direct_url":
        return int(task.get("file_size") or 0)
    if t == "bundle_local_files":
        files = task.get("files") or []
        total = 0
        for p in files:
            try:
                fp = Path(p)
                if fp.exists():
                    total += fp.stat().st_size
            except OSError:
                pass
        return total
    return 0
