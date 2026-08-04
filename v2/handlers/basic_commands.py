"""Slash handlers with no Rubika/network/admin coupling (extracted from telebot)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class BasicCommandDeps:
    tr: TranslateFn
    remember_chat: Callable[[int], None]
    set_menu_section: Callable[[int, MenuSection], None]
    get_direct_mode_target: Callable[[int], Optional[str]]
    set_direct_mode_target: Callable[[int, Optional[str]], None]
    build_main_menu: Callable[[int], Any]
    app_version: str
    clear_state: Callable[[int], None] | None = None
    connection_checklist: Callable[[int], str] | None = None
    is_admin: Callable[[int], bool] | None = None


def _clear_wizard(deps: BasicCommandDeps, uid: int) -> None:
    if deps.clear_state:
        try:
            deps.clear_state(uid)
        except Exception:
            pass


async def handle_start(deps: BasicCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if deps.get_direct_mode_target(uid):
        deps.set_direct_mode_target(uid, None)
    _clear_wizard(deps, uid)
    deps.remember_chat(message.chat.id)
    deps.set_menu_section(uid, MenuSection.MAIN)

    body = deps.tr(uid, "welcome")
    if deps.connection_checklist:
        try:
            body = body + "\n\n" + deps.connection_checklist(uid)
        except Exception:
            pass

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(deps.tr(uid, "btn_onboard_transfer"), callback_data="imenu:transfer"),
                InlineKeyboardButton(deps.tr(uid, "btn_onboard_tools"), callback_data="imenu:toolkit"),
            ],
            [
                InlineKeyboardButton(deps.tr(uid, "btn_onboard_world"), callback_data="imenu:world"),
                InlineKeyboardButton(deps.tr(uid, "btn_onboard_feed"), callback_data="imenu:feeds"),
            ],
            [
                InlineKeyboardButton(deps.tr(uid, "btn_onboard_rubika"), callback_data="imenu:rubika"),
                InlineKeyboardButton(deps.tr(uid, "btn_onboard_plan"), callback_data="imenu:plan"),
            ],
            [
                InlineKeyboardButton(deps.tr(uid, "btn_main_help"), callback_data="imenu:help"),
            ],
        ]
    )
    await message.reply_text(body, reply_markup=deps.build_main_menu(uid), parse_mode=None)
    await message.reply_text(deps.tr(uid, "onboard_next_steps"), reply_markup=kb, parse_mode=None)


async def handle_menu(deps: BasicCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if deps.get_direct_mode_target(uid):
        deps.set_direct_mode_target(uid, None)
    _clear_wizard(deps, uid)
    deps.set_menu_section(uid, MenuSection.MAIN)
    body = deps.tr(uid, "menu_intro")
    if deps.connection_checklist:
        try:
            body = body + "\n\n" + deps.connection_checklist(uid)
        except Exception:
            pass
    await message.reply_text(
        body,
        reply_markup=deps.build_main_menu(uid),
        parse_mode=None,
    )


async def handle_lang(deps: BasicCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("فارسی", callback_data="setlang:fa"),
                InlineKeyboardButton("English", callback_data="setlang:en"),
            ],
        ]
    )
    await message.reply_text(deps.tr(uid, "pick_lang"), reply_markup=kb)


async def handle_help(deps: BasicCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    body = deps.tr(uid, "help_short")
    if deps.is_admin and deps.is_admin(uid):
        extra = deps.tr(uid, "help_short_admin_extra")
        if extra and extra != "help_short_admin_extra":
            body = f"{body}\n\n{extra}"
    await message.reply_text(body, parse_mode=None)


async def handle_log_help(deps: BasicCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    await message.reply_text(deps.tr(uid, "loghelp_body"))


async def handle_version(deps: BasicCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    await message.reply_text(
        deps.tr(uid, "version_line", version=deps.app_version),
    )
