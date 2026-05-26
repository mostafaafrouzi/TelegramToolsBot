"""Dual-write provider credentials to ``users.json`` for survives updates / SQLite issues."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from queue_db import QueueDB

UserKeyFn = Callable[[int], str]
LoadUsersFn = Callable[[], dict]
SaveUsersFn = Callable[[dict], None]


def mirror_bale_to_users_json(
    user_id: int,
    *,
    load_users: LoadUsersFn,
    save_users: SaveUsersFn,
    get_user_key: UserKeyFn,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    clear: bool = False,
) -> None:
    users = load_users()
    key = get_user_key(user_id)
    item = dict(users.get(key, {}))
    if clear:
        item.pop("bale_bot_token", None)
        item.pop("bale_chat_id", None)
    else:
        if bot_token is not None:
            item["bale_bot_token"] = bot_token
        if chat_id is not None:
            item["bale_chat_id"] = chat_id
    users[key] = item
    save_users(users)


def mirror_cloudflare_to_users_json(
    user_id: int,
    token: Optional[str],
    *,
    load_users: LoadUsersFn,
    save_users: SaveUsersFn,
    get_user_key: UserKeyFn,
    clear: bool = False,
) -> None:
    users = load_users()
    key = get_user_key(user_id)
    item = dict(users.get(key, {}))
    if clear:
        item.pop("cloudflare_api_token", None)
    elif token is not None:
        item["cloudflare_api_token"] = token
    users[key] = item
    save_users(users)


def sync_provider_credentials_from_users_json(
    queue: QueueDB,
    *,
    load_users: LoadUsersFn,
    get_user_key: UserKeyFn,
) -> int:
    """Restore SQLite provider prefs from ``users.json`` when DB row is empty."""
    restored = 0
    users = load_users() or {}
    for key, item in users.items():
        if not isinstance(key, str) or not key.isdigit() or not isinstance(item, dict):
            continue
        uid = int(key)
        token = (item.get("bale_bot_token") or "").strip()
        chat = (item.get("bale_chat_id") or "").strip()
        if token:
            db_token, db_chat = queue.get_bale_credentials(uid)
            if not db_token:
                queue.upsert_bale_bot_token(uid, token)
                restored += 1
            if chat and not db_chat:
                queue.upsert_bale_chat_id(uid, chat)
        cf = (item.get("cloudflare_api_token") or "").strip()
        if cf and not (queue.get_cloudflare_api_token(uid) or "").strip():
            queue.upsert_cloudflare_api_token(uid, cf)
            restored += 1
        folder = (item.get("drive_folder_id") or "").strip()
        sa = (item.get("drive_sa_path") or "").strip()
        if folder and not (queue.get_drive_folder_id(uid) or "").strip():
            queue.upsert_drive_folder_id(uid, folder)
            restored += 1
        if sa and not (queue.get_drive_sa_path(uid) or "").strip():
            queue.upsert_drive_sa_path(uid, sa)
            restored += 1
    return restored


def backup_sqlite_provider_prefs_to_users_json(
    queue: QueueDB,
    *,
    load_users: LoadUsersFn,
    save_users: SaveUsersFn,
    get_user_key: UserKeyFn,
) -> int:
    """Copy SQLite provider credentials into ``users.json`` (SQLite remains source of truth)."""
    backed = 0
    users = dict(load_users() or {})
    try:
        with queue._connect() as conn:
            rows = conn.execute(
                """
                SELECT telegram_user_id, bale_bot_token, bale_chat_id,
                       cloudflare_api_token, drive_folder_id, drive_sa_path
                FROM v2_user_prefs
                WHERE bale_bot_token IS NOT NULL
                   OR bale_chat_id IS NOT NULL
                   OR cloudflare_api_token IS NOT NULL
                   OR drive_folder_id IS NOT NULL
                   OR drive_sa_path IS NOT NULL
                """
            ).fetchall()
    except Exception:
        return 0
    for row in rows:
        uid = int(row["telegram_user_id"])
        key = get_user_key(uid)
        item = dict(users.get(key, {}))
        changed = False
        for col in (
            "bale_bot_token",
            "bale_chat_id",
            "cloudflare_api_token",
            "drive_folder_id",
            "drive_sa_path",
        ):
            val = row[col]
            if val is None:
                continue
            sval = str(val).strip()
            if sval and item.get(col) != sval:
                item[col] = sval
                changed = True
        if changed:
            users[key] = item
            backed += 1
    if backed:
        save_users(users)
    return backed
