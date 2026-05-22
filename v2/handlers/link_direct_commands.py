"""Open link/video direct-download section."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class LinkDirectCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    build_link_direct_menu: Callable[[int], Any]


async def handle_show_link_direct_menu(
    deps: LinkDirectCommandDeps, client: Any, message: Message
) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.LINK_DIRECT)
    await message.reply_text(
        deps.tr(uid, "link_menu_opened"),
        reply_markup=deps.build_link_direct_menu(uid),
        parse_mode=None,
    )
