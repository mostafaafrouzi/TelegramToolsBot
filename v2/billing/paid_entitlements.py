"""Apply ``user_entitlements`` when a ledger row reaches ``paid`` (optional ``grant_*`` in ``raw_json``)."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from queue_db import QueueDB

from v2.billing.status import PAID


def maybe_grant_plan_after_paid(db: QueueDB, payment_id: int) -> bool:
    """If metadata requests a tier grant and none applied yet, call ``set_user_tier``. Returns True if granted."""
    row = db.get_v2_payment_by_id(int(payment_id))
    if not row:
        return False
    if str(row.get("status", "")).strip().lower() != PAID:
        return False
    raw = row.get("raw_json")
    if raw is None or not str(raw).strip():
        return False
    try:
        meta = json.loads(str(raw))
    except json.JSONDecodeError:
        return False
    if not isinstance(meta, dict):
        return False
    if meta.get("entitlement_applied_at"):
        return False
    tier_raw = meta.get("grant_tier")
    if tier_raw is None or tier_raw == "":
        return False
    uid = row.get("telegram_user_id")
    if uid is None:
        return False
    tier_s = str(tier_raw).strip().lower()
    days_i = int(meta.get("grant_days") or 0)
    # Timed paid tiers (pro/star) get an absolute expiry; free/guest ignore days.
    exp = 0
    if tier_s in ("pro", "star") and days_i > 0:
        exp = int(time.time()) + days_i * 86400

    from user_entitlements import set_user_tier

    set_user_tier(int(uid), tier_s, exp)
    now = int(time.time())
    db.update_v2_payment_status(
        int(payment_id),
        PAID,
        raw_patch={
            "entitlement_applied_at": now,
            "entitlement_notify_pending": True,
            "grant_tier": tier_s,
            "grant_days": days_i,
            "grant_expires_at": exp,
        },
    )
    return True


def claim_pending_entitlement_notifies(db: QueueDB, *, limit: int = 40) -> list[dict[str, Any]]:
    """
    Return paid grants waiting for a user DM, then mark each as notified.
    Each item: payment_id, telegram_user_id, tier, days, expires_at.
    """
    out: list[dict[str, Any]] = []
    rows = db.list_v2_payments_by_status(PAID, limit=max(1, min(200, int(limit))))
    for row in rows:
        raw = row.get("raw_json")
        if raw is None or not str(raw).strip():
            continue
        try:
            meta = json.loads(str(raw))
        except json.JSONDecodeError:
            continue
        if not isinstance(meta, dict):
            continue
        if not meta.get("entitlement_notify_pending"):
            continue
        if meta.get("entitlement_notified_at"):
            continue
        uid = row.get("telegram_user_id")
        if uid is None:
            continue
        pid = int(row["id"])
        item = {
            "payment_id": pid,
            "telegram_user_id": int(uid),
            "tier": str(meta.get("grant_tier") or "pro"),
            "days": int(meta.get("grant_days") or 0),
            "expires_at": int(meta.get("grant_expires_at") or 0),
        }
        db.update_v2_payment_status(
            pid,
            PAID,
            raw_patch={
                "entitlement_notify_pending": False,
                "entitlement_notified_at": int(time.time()),
            },
        )
        out.append(item)
    return out
