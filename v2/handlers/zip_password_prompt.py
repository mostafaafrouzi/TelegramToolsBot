"""Handle per-user safe-mode ZIP password prompt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from pyrogram.types import Message

TranslateFn = Callable[[int, str], str]


@dataclass(frozen=True)
class ZipPasswordPromptDeps:
    get_waiting_for_password: Callable[[int], bool]
    set_waiting_for_password: Callable[[bool, int], None]
    tr: TranslateFn
    load_settings: Callable[[], dict]
    save_settings: Callable[[Dict], None]


async def handle_zip_password_text(
    message: Message,
    user_id: int,
    text: str,
    deps: ZipPasswordPromptDeps,
) -> bool:
    """
    If this user is waiting for ZIP password after safemode on, consume message.
    Returns True when handled (including empty password re-prompt).
    """
    if not deps.get_waiting_for_password(user_id):
        return False

    password = text.strip()
    if not password:
        await message.reply_text(deps.tr(user_id, "password_empty"))
        return True

    settings = deps.load_settings()
    settings["safe_mode"] = True
    settings["zip_password"] = password
    deps.save_settings(settings)

    deps.set_waiting_for_password(False, user_id)

    await message.reply_text(deps.tr(user_id, "password_saved_zip"))
    return True
