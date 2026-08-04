"""Clear bot messages in the current private chat (settings/plan preserved)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.core.bot_messages import clear_tracked, list_message_ids
from v2.core.menu_sections import MenuSection
from v2.core.msg_format import reply_plain

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class ClearChatDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]


async def handle_clear_chat_prompt(deps: ClearChatDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.PLAN)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تایید پاک کردن",
                    callback_data="clearchat:confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    "لغو",
                    callback_data="clearchat:cancel",
                )
            ],
        ]
    )
    await reply_plain(message, deps.tr(uid, "clear_chat_confirm"), reply_markup=kb)


async def handle_clear_chat_callback(
    deps: ClearChatDeps, client: Any, callback_query: Any, action: str
) -> bool:
    uid = callback_query.from_user.id
    chat_id = callback_query.message.chat.id if callback_query.message else uid
    await callback_query.answer()
    if action == "cancel":
        await reply_plain(callback_query.message, "لغو شد.")
        return True
    if action != "confirm":
        return True
    ids = list_message_ids(uid, chat_id, limit=500)
    deleted = 0
    # Telegram allows deleting own messages; batch in chunks of 100 where possible
    for mid in ids:
        try:
            ok = await client.delete_messages(chat_id, mid)
            if ok:
                deleted += 1
        except Exception:
            pass
    # Also try deleting the confirmation message itself
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    clear_tracked(uid, chat_id)
    # Send a fresh confirmation (will be tracked for next clear)
    try:
        await client.send_message(
            chat_id,
            deps.tr(uid, "clear_chat_done", n=deleted)
            if deleted
            else deps.tr(uid, "clear_chat_none"),
        )
    except Exception:
        pass
    return True
