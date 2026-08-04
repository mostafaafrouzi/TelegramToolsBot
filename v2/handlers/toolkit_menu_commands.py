"""Toolkit menu hub and submenus (network / crypto / calc)."""

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
    build_toolkit_calc_menu: MenuBuilder | None = None
    build_calc_finance_menu: MenuBuilder | None = None
    build_calc_numbers_menu: MenuBuilder | None = None
    build_calc_convert_menu: MenuBuilder | None = None
    build_calc_math_menu: MenuBuilder | None = None
    build_calc_text_menu: MenuBuilder | None = None
    build_calc_other_menu: MenuBuilder | None = None
    miniapp_base_url: str = ""


async def handle_show_toolkit_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    await message.reply_text(
        deps.tr(uid, "toolkit_menu_title"),
        reply_markup=deps.build_toolkit_menu(uid),
    )


async def handle_show_toolkit_network_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT_NETWORK)
    await message.reply_text(
        deps.tr(uid, "toolkit_network_menu_title"),
        reply_markup=deps.build_toolkit_network_menu(uid),
    )
    base = (deps.miniapp_base_url or "").strip()
    if base:
        from v2.core.inline_menus import build_inline_toolkit_network

        _body, kb = build_inline_toolkit_network(uid, deps.tr, webapp_url=base)
        await message.reply_text(
            deps.tr(uid, "toolkit_network_miniapp_hint"),
            reply_markup=kb,
            parse_mode=None,
        )


async def handle_show_toolkit_crypto_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT_CRYPTO)
    await message.reply_text(
        deps.tr(uid, "toolkit_crypto_menu_title"),
        reply_markup=deps.build_toolkit_crypto_menu(uid),
    )


async def handle_show_toolkit_calc_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT_CALC)
    markup = deps.build_toolkit_calc_menu(uid) if deps.build_toolkit_calc_menu else None
    await message.reply_text(
        deps.tr(uid, "toolkit_calc_menu_title"),
        reply_markup=markup,
    )


async def _show_calc_cat(
    deps: ToolkitMenuDeps,
    message: Message,
    builder_attr: str,
    title_key: str,
) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT_CALC_CAT)
    builder = getattr(deps, builder_attr, None)
    await message.reply_text(
        deps.tr(uid, title_key),
        reply_markup=builder(uid) if builder else None,
    )


async def handle_show_calc_finance_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    await _show_calc_cat(deps, message, "build_calc_finance_menu", "calc_cat_finance_title")


async def handle_show_calc_numbers_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    await _show_calc_cat(deps, message, "build_calc_numbers_menu", "calc_cat_numbers_title")


async def handle_show_calc_convert_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    await _show_calc_cat(deps, message, "build_calc_convert_menu", "calc_cat_convert_title")


async def handle_show_calc_math_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    await _show_calc_cat(deps, message, "build_calc_math_menu", "calc_cat_math_title")


async def handle_show_calc_text_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    await _show_calc_cat(deps, message, "build_calc_text_menu", "calc_cat_text_title")


async def handle_show_calc_other_menu(deps: ToolkitMenuDeps, client: Any, message: Message) -> None:
    await _show_calc_cat(deps, message, "build_calc_other_menu", "calc_cat_other_title")
