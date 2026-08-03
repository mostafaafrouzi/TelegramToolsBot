"""Inline upgrade CTAs shared by quota / plan blockers."""

from __future__ import annotations

from typing import Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TranslateFn = Callable[..., str]


def buy_pro_keyboard(user_id: int, tr: TranslateFn) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    tr(user_id, "btn_buy_pro_cta"),
                    callback_data="imenu:purchase",
                )
            ],
            [
                InlineKeyboardButton(
                    tr(user_id, "btn_plan_compare"),
                    callback_data="imenu:plan_compare",
                )
            ],
        ]
    )


def with_upgrade_hint(text: str, *, lang: str = "fa") -> str:
    tip = "Upgrade: /purchase" if lang == "en" else "برای ارتقا: /purchase"
    if "/purchase" in (text or ""):
        return text
    return f"{text.rstrip()}\n\n{tip}"
