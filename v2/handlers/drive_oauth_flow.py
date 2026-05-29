"""Shared Google Drive OAuth token save + notify user."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from v2.toolkit.drive_oauth_light import exchange_code, save_token_file
from v2.transfer.user_credentials import default_drive_oauth_path

TranslateFn = Callable[..., str]


def persist_oauth_token(
    base_dir: Path,
    user_id: int,
    token_payload: dict[str, Any],
    upsert_drive_oauth_path: Callable[[int, str], None],
) -> Path:
    dest = default_drive_oauth_path(base_dir, user_id)
    save_token_file(dest, token_payload)
    rel = dest.relative_to(base_dir).as_posix()
    upsert_drive_oauth_path(int(user_id), rel)
    return dest


def connect_drive_with_auth_code(
    base_dir: Path,
    user_id: int,
    code: str,
    upsert_drive_oauth_path: Callable[[int, str], None],
) -> tuple[bool, str]:
    ok, data = exchange_code(code.strip())
    if not ok:
        return False, str(data)
    if not isinstance(data, dict):
        return False, "invalid_token_response"
    persist_oauth_token(base_dir, user_id, data, upsert_drive_oauth_path)
    return True, ""


async def notify_oauth_success(
    client: Any,
    user_id: int,
    tr: TranslateFn,
    *,
    set_state_preserving_menu: Callable[..., None],
    clear_state: Callable[[int], None],
) -> None:
    set_state_preserving_menu(int(user_id), {"step": "await_drive_folder_id"})
    await client.send_message(
        int(user_id),
        tr(int(user_id), "drive_oauth_ok_ask_folder"),
        parse_mode=None,
    )


async def notify_oauth_failure(client: Any, user_id: int, tr: TranslateFn, detail: str) -> None:
    await client.send_message(
        int(user_id),
        tr(int(user_id), "drive_oauth_failed", detail=(detail or "error")[:400]),
        parse_mode=None,
    )
