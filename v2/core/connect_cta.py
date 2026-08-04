"""Inline CTAs so users never need to type slash commands for common actions."""

from __future__ import annotations

from typing import Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def connect_keyboard(
    *,
    rubika: bool = False,
    bale: bool = False,
    drive: bool = False,
    cloudflare: bool = False,
    direct: bool = False,
    transfer: bool = False,
    netstatus: bool = False,
    purchase: bool = False,
    lang: str = "fa",
) -> Optional[InlineKeyboardMarkup]:
    rows: list[list[InlineKeyboardButton]] = []
    fa = lang != "en"
    if rubika:
        rows.append([InlineKeyboardButton("🔗 اتصال روبیکا" if fa else "🔗 Connect Rubika", callback_data="cta:rubika_connect")])
    if bale:
        rows.append([InlineKeyboardButton("🔗 اتصال بله" if fa else "🔗 Connect Bale", callback_data="cta:bale_connect")])
    if drive:
        rows.append([InlineKeyboardButton("☁️ اتصال درایو" if fa else "☁️ Connect Drive", callback_data="cta:drive_connect")])
    if cloudflare:
        rows.append([InlineKeyboardButton("☁️ اتصال Cloudflare" if fa else "☁️ Connect Cloudflare", callback_data="cta:cf_connect")])
    if direct:
        rows.append([InlineKeyboardButton("📤 ارسال مستقیم" if fa else "📤 Direct send", callback_data="cta:direct_menu")])
    if transfer:
        rows.append([InlineKeyboardButton("📁 منوی انتقال" if fa else "📁 Transfer menu", callback_data="cta:transfer_menu")])
    if netstatus:
        rows.append([InlineKeyboardButton("🌐 وضعیت شبکه" if fa else "🌐 Network status", callback_data="cta:netstatus")])
    if purchase:
        rows.append([InlineKeyboardButton("💳 خرید / ارتقا" if fa else "💳 Purchase", callback_data="cta:purchase")])
    if not rows:
        return None
    return InlineKeyboardMarkup(rows)
