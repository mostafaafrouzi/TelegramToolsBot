"""Per-user Bale bot and Google Drive connect wizards (credentials stored per Telegram user)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.transfer.bale_client import validate_bot_token
from v2.transfer.user_credentials import default_drive_sa_path

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class ProviderConnectWizardDeps:
    tr: TranslateFn
    base_dir: Path
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    get_bale_credentials: Callable[[int], tuple[Optional[str], Optional[str]]]
    upsert_bale_bot_token: Callable[[int, str], None]
    upsert_bale_chat_id: Callable[[int, str], None]
    clear_bale_credentials: Callable[[int], None]
    upsert_drive_folder_id: Callable[[int, str], None]
    upsert_drive_sa_path: Callable[[int, str], None]
    clear_drive_credentials: Callable[[int], None]
    log_event: Callable[..., None]


async def dispatch_provider_connect_wizard(
    message: Message,
    user_id: int,
    state: dict,
    text: str,
    deps: ProviderConnectWizardDeps,
) -> bool:
    """Text steps for Bale/Drive connect. Returns True if consumed."""
    tr = deps.tr
    step = state.get("step")

    if step == "await_bale_token":
        token = text.strip()
        ok, detail = await asyncio.to_thread(validate_bot_token, token)
        if not ok:
            await message.reply_text(tr(user_id, "bale_token_invalid", detail=detail), parse_mode=None)
            return True
        deps.upsert_bale_bot_token(user_id, token)
        deps.set_state_preserving_menu(user_id, {"step": "await_bale_chat_id"})
        await message.reply_text(
            tr(user_id, "bale_token_ok", bot=detail),
            parse_mode=None,
        )
        deps.log_event("bale_connect_token_ok", user_id=user_id)
        return True

    if step == "await_bale_chat_id":
        chat_id = text.strip()
        if not chat_id:
            await message.reply_text(tr(user_id, "bale_chat_id_empty"), parse_mode=None)
            return True
        deps.upsert_bale_chat_id(user_id, chat_id)
        deps.clear_state(user_id)
        await message.reply_text(tr(user_id, "bale_connected_ok", chat_id=chat_id), parse_mode=None)
        deps.log_event("bale_connect_ok", user_id=user_id)
        return True

    if step == "await_drive_folder_id":
        folder_id = text.strip()
        if not folder_id:
            await message.reply_text(tr(user_id, "drive_folder_empty"), parse_mode=None)
            return True
        sa = default_drive_sa_path(deps.base_dir, user_id)
        if not sa.is_file():
            await message.reply_text(tr(user_id, "drive_sa_missing_retry"), parse_mode=None)
            deps.clear_state(user_id)
            return True
        deps.upsert_drive_folder_id(user_id, folder_id)
        deps.clear_state(user_id)
        await message.reply_text(tr(user_id, "drive_connected_ok", folder_id=folder_id), parse_mode=None)
        deps.log_event("drive_connect_ok", user_id=user_id)
        return True

    return False


async def handle_bale_connect(deps: ProviderConnectWizardDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.BALE)
    token, chat = deps.get_bale_credentials(uid)
    if token and chat:
        await message.reply_text(deps.tr(uid, "bale_already_connected"), parse_mode=None)
    deps.set_state_preserving_menu(uid, {"step": "await_bale_token"})
    deps.log_event("bale_connect_started", user_id=uid)
    await message.reply_text(deps.tr(uid, "bale_ask_token"), parse_mode=None)


async def handle_bale_disconnect(deps: ProviderConnectWizardDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.clear_bale_credentials(uid)
    deps.clear_state(uid)
    deps.log_event("bale_disconnect", user_id=uid)
    await message.reply_text(deps.tr(uid, "bale_disconnected"), parse_mode=None)


async def handle_drive_connect(deps: ProviderConnectWizardDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)
    deps.set_state_preserving_menu(uid, {"step": "await_drive_sa_json"})
    deps.log_event("drive_connect_started", user_id=uid)
    await message.reply_text(deps.tr(uid, "drive_ask_sa_json"), parse_mode=None)


async def handle_drive_disconnect(
    deps: ProviderConnectWizardDeps,
    client: Any,
    message: Message,
) -> None:
    uid = message.from_user.id
    sa = default_drive_sa_path(deps.base_dir, uid)
    try:
        if sa.is_file():
            sa.unlink()
    except OSError:
        pass
    deps.clear_drive_credentials(uid)
    deps.clear_state(uid)
    deps.log_event("drive_disconnect", user_id=uid)
    await message.reply_text(deps.tr(uid, "drive_disconnected"), parse_mode=None)


async def save_drive_sa_from_downloaded_file(
    deps: ProviderConnectWizardDeps,
    user_id: int,
    local_json_path: Path,
) -> tuple[bool, str]:
    """Validate and persist service-account JSON for ``user_id``."""
    try:
        raw = local_json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        return False, str(e)
    if data.get("type") != "service_account" or not data.get("client_email"):
        return False, "not a Google service account JSON"
    dest = default_drive_sa_path(deps.base_dir, user_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(raw, encoding="utf-8")
    try:
        local_json_path.unlink()
    except OSError:
        pass
    rel = dest.relative_to(deps.base_dir).as_posix()
    deps.upsert_drive_sa_path(user_id, rel)
    return True, ""
