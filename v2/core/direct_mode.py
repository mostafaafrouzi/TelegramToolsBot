"""Direct-send destination (mutually exclusive: rubika | bale | drive | off)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Literal, Optional

if TYPE_CHECKING:
    from queue_db import QueueDB

DirectTarget = Literal["rubika", "bale", "drive"]
_VALID = frozenset({"rubika", "bale", "drive"})


def normalize_target(value: Optional[str]) -> Optional[DirectTarget]:
    if not value:
        return None
    v = str(value).strip().lower()
    if v in _VALID:
        return v  # type: ignore[return-value]
    return None


def load_direct_mode_target(
    user_id: int,
    *,
    load_users: Callable[[], dict],
    get_user_key: Callable[[int], str],
    queue: Optional[QueueDB] = None,
) -> Optional[DirectTarget]:
    users = load_users()
    item = users.get(get_user_key(user_id), {})
    if "direct_mode_target" in item:
        return normalize_target(item.get("direct_mode_target"))
    if item.get("direct_mode") is True:
        return "rubika"
    if queue is not None:
        try:
            t = queue.get_direct_mode_target(user_id)
            if t:
                return normalize_target(t)
            dm = queue.get_direct_mode(user_id)
            if dm:
                return "rubika"
        except Exception:
            pass
    return None


def save_direct_mode_target(
    user_id: int,
    target: Optional[DirectTarget],
    *,
    load_users: Callable[[], dict],
    save_users: Callable[[dict], None],
    get_user_key: Callable[[int], str],
    queue: Optional[QueueDB] = None,
) -> None:
    users = load_users()
    key = get_user_key(user_id)
    item = dict(users.get(key, {}))
    if target:
        item["direct_mode_target"] = target
        item["direct_mode"] = True
    else:
        item.pop("direct_mode_target", None)
        item["direct_mode"] = False
    users[key] = item
    save_users(users)
    if queue is not None:
        try:
            queue.upsert_direct_mode_target(user_id, target)
            queue.upsert_direct_mode(user_id, bool(target))
        except Exception:
            pass
