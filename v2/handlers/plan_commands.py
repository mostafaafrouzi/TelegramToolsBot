"""Plan / billing slash commands (extracted from telebot)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]
UsageReportFn = Callable[[int], str]


@dataclass(frozen=True)
class PlanCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    usage_report_text: UsageReportFn
    stub_checkout_enabled: bool = False
    create_stub_checkout: Optional[Callable[[int], tuple[int, str]]] = None
    create_gateway_checkout: Optional[Callable[[int], tuple[int, str, str]]] = None
    plan_compare_text: Optional[Callable[[int], str]] = None


async def handle_usage(deps: PlanCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.PLAN)
    await message.reply_text(deps.usage_report_text(uid), parse_mode=None)


async def handle_plan(deps: PlanCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.PLAN)
    body = deps.usage_report_text(uid) + "\n\n" + deps.tr(uid, "purchase_info_body")
    if deps.plan_compare_text:
        body += "\n\n" + deps.plan_compare_text(uid)
    await message.reply_text(body, parse_mode=None)


async def handle_plan_compare(deps: PlanCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.PLAN)
    if deps.plan_compare_text:
        await message.reply_text(deps.plan_compare_text(uid), parse_mode=None)
        return
    await message.reply_text(deps.tr(uid, "purchase_info_body"), parse_mode=None)


async def handle_purchase(deps: PlanCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.PLAN)
    if deps.create_gateway_checkout:
        try:
            pid, authority, pay_url = deps.create_gateway_checkout(uid)
        except Exception as e:
            await message.reply_text(
                deps.tr(uid, "purchase_gateway_error", error=str(e)[:400]),
                parse_mode=None,
            )
            return
        kb = None
        if pay_url and str(pay_url).startswith("http"):
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            deps.tr(uid, "btn_open_pay_url"),
                            url=str(pay_url),
                        )
                    ]
                ]
            )
        await message.reply_text(
            deps.tr(
                uid,
                "purchase_gateway_started",
                payment_id=pid,
                authority=authority,
                pay_url=pay_url or "-",
            ),
            reply_markup=kb,
            parse_mode=None,
        )
        return
    if deps.stub_checkout_enabled and deps.create_stub_checkout:
        pid, authority = deps.create_stub_checkout(uid)
        await message.reply_text(
            deps.tr(uid, "purchase_stub_started", payment_id=pid, authority=authority),
            parse_mode=None,
        )
        return
    await message.reply_text(deps.tr(uid, "purchase_info_body"), parse_mode=None)
