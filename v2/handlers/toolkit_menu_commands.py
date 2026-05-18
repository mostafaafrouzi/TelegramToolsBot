"""Toolkit menu hub and submenus (network / crypto)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]
MenuBuilder = Callable[[int], Any]


@dataclass(frozen=True)
class ToolkitMenuDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    build_toolkit_menu: MenuBuilder
    build_toolkit_network_menu: MenuBuilder
    build_toolkit_crypto_menu: MenuBuilder


async def handle_show_toolkit_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    await message.reply_text(
        deps.tr(uid, "toolkit_menu_title"),
        reply_markup=deps.build_toolkit_menu(uid),
    )


async def handle_show_toolkit_network_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    await message.reply_text(
        deps.tr(uid, "toolkit_network_menu_title"),
        reply_markup=deps.build_toolkit_network_menu(uid),
    )


async def handle_show_toolkit_crypto_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    await message.reply_text(
        deps.tr(uid, "toolkit_crypto_menu_title"),
        reply_markup=deps.build_toolkit_crypto_menu(uid),
    )
