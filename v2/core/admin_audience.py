"""Resolve admin broadcast audiences (tiers, activity, known chats)."""

from __future__ import annotations

import time
from typing import Callable, Optional


SEGMENTS: dict[str, str] = {
    "all": "all_known_and_active",
    "known": "known_chats",
    "new7": "new_users_7d",
    "guest": "tier_guest",
    "free": "tier_free",
    "pro": "tier_pro",
    "star": "tier_star",
    "expiring7": "expiring_7d",
    "expired": "expired_paid",
    "inactive30": "inactive_30d",
}


def resolve_audience(
    segment: str,
    *,
    list_known_chat_ids: Callable[[], list[int]],
    list_activity_user_ids: Callable[[], list[int]],
    list_new_user_ids: Callable[[int], list[int]],
    list_inactive_user_ids: Callable[[int], list[int]],
    list_tier_user_ids: Callable[[str], list[int]],
    list_expiring_user_ids: Callable[[int], list[int]],
    list_expired_user_ids: Callable[[], list[int]],
) -> tuple[list[int], str]:
    """Return sorted unique telegram user ids and a short label key."""
    seg = (segment or "").strip().lower()
    ids: list[int] = []
    label = SEGMENTS.get(seg, seg or "unknown")

    if seg == "all":
        ids = list(set(list_known_chat_ids()) | set(list_activity_user_ids()))
    elif seg == "known":
        ids = list(list_known_chat_ids())
    elif seg == "new7":
        ids = list_new_user_ids(7)
    elif seg in ("guest", "free", "pro", "star"):
        ids = list_tier_user_ids(seg)
    elif seg == "expiring7":
        ids = list_expiring_user_ids(7)
    elif seg == "expired":
        ids = list_expired_user_ids()
    elif seg == "inactive30":
        ids = list_inactive_user_ids(30)
    else:
        return [], "unknown"

    out = sorted({int(x) for x in ids if int(x) > 0})
    return out, label


def admin_stats_blob(
    *,
    count_users: Callable[[], int],
    list_new_user_ids: Callable[[int], list[int]],
    list_inactive_user_ids: Callable[[int], list[int]],
    tier_counts: Callable[[], dict[str, int]],
    list_known_chat_ids: Callable[[], list[int]],
    list_expiring_user_ids: Callable[[int], list[int]],
    list_expired_user_ids: Callable[[], list[int]],
) -> dict:
    tiers = tier_counts()
    return {
        "users_total": count_users(),
        "known_chats": len(list_known_chat_ids()),
        "new_7d": len(list_new_user_ids(7)),
        "inactive_30d": len(list_inactive_user_ids(30)),
        "expiring_7d": len(list_expiring_user_ids(7)),
        "expired": len(list_expired_user_ids()),
        "tier_guest": int(tiers.get("guest") or 0),
        "tier_free": int(tiers.get("free") or 0),
        "tier_pro": int(tiers.get("pro") or 0),
        "tier_star": int(tiers.get("star") or 0),
        "ts": int(time.time()),
    }
