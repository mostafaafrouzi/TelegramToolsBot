"""Pick transfer destination before downloading media (when direct mode is off)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.handlers.link_direct_handler import verify_destination
from v2.transfer.user_credentials import load_bale_credentials, load_drive_credentials

TranslateFn = Callable[..., str]

_pending_media_source: dict[int, tuple[int, int]] = {}


@dataclass
class _VerifyDeps:
    get_user_session: Callable[[int], Optional[str]]
    queue: Any
    base_dir: Any


@dataclass(frozen=True)
class MediaDestHandlerDeps:
    tr: TranslateFn
    base_dir: Any
    queue: Any
    get_user_session: Callable[[int], Optional[str]]
    get_direct_mode_target: Callable[[int], Optional[str]]
    get_menu_section: Callable[[int], Optional[str]]
    download_and_queue_media: Callable[..., Awaitable[None]]


def _dest_keyboard(user_id: int, tr: TranslateFn) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "link_dest_rubika"), callback_data="mediadest:rubika"),
                InlineKeyboardButton(tr(user_id, "link_dest_bale"), callback_data="mediadest:bale"),
            ],
            [InlineKeyboardButton(tr(user_id, "link_dest_drive"), callback_data="mediadest:drive")],
            [InlineKeyboardButton(tr(user_id, "link_dest_cancel"), callback_data="mediadest:cancel")],
        ]
    )


def should_prompt_media_destination(
    user_id: int,
    section: str,
    *,
    get_direct_mode_target: Callable[[int], Optional[str]],
) -> bool:
    if get_direct_mode_target(user_id):
        return False
    sec = (section or "").strip().lower()
    if sec in ("bale", "drive"):
        return False
    return True


async def prompt_media_destination(
    deps: MediaDestHandlerDeps,
    message: Message,
    user_id: int,
) -> bool:
    if not should_prompt_media_destination(
        user_id,
        deps.get_menu_section(user_id) or "",
        get_direct_mode_target=deps.get_direct_mode_target,
    ):
        return False

    _pending_media_source[user_id] = (message.chat.id, message.id)
    await message.reply_text(
        deps.tr(user_id, "media_pick_dest"),
        reply_markup=_dest_keyboard(user_id, deps.tr),
        parse_mode=None,
    )
    return True


async def handle_media_dest_callback(
    deps: MediaDestHandlerDeps,
    client: Any,
    callback_query: Any,
    dest: str,
) -> bool:
    user_id = callback_query.from_user.id
    src = _pending_media_source.pop(user_id, None)
    if not src:
        await callback_query.answer(deps.tr(user_id, "media_dest_session_expired"), show_alert=True)
        return True

    if dest == "cancel":
        await callback_query.answer()
        try:
            await callback_query.message.edit_text(
                deps.tr(user_id, "link_cancelled"),
                reply_markup=None,
                parse_mode=None,
            )
        except Exception:
            pass
        return True

    vdeps = _VerifyDeps(
        get_user_session=deps.get_user_session,
        queue=deps.queue,
        base_dir=deps.base_dir,
    )
    ok, err_key, extra = verify_destination(dest, user_id, vdeps)  # type: ignore[arg-type]
    if not ok:
        await callback_query.answer(deps.tr(user_id, err_key), show_alert=True)
        _pending_media_source[user_id] = src
        return True

    chat_id, msg_id = src
    try:
        user_message = await client.get_messages(chat_id, msg_id)
    except Exception:
        await callback_query.answer(deps.tr(user_id, "media_dest_session_expired"), show_alert=True)
        return True

    await callback_query.answer()
    anchor = callback_query.message
    try:
        await anchor.edit_text(deps.tr(user_id, "media_download_status"), reply_markup=None, parse_mode=None)
    except Exception:
        pass

    task_type = "local_file"
    require_rubika = dest == "rubika"
    session_name = extra.get("rubika_session") if require_rubika else None
    if dest == "bale":
        task_type = "transfer_to_bale"
        require_rubika = False
    elif dest == "drive":
        task_type = "transfer_to_drive"
        require_rubika = False

    await deps.download_and_queue_media(
        client,
        user_message,
        user_id,
        task_type=task_type,
        extra=extra,
        require_rubika=require_rubika,
        session_name=session_name,
        status_message=anchor,
        batch_allowed=require_rubika and task_type == "local_file",
    )
    return True
