"""Weather, calendar, currency, earthquakes, timezone, age."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.toolkit.calendar_light import age_report, calendar_report
from v2.toolkit.fx_light import currency_convert
from v2.toolkit.timezone_light import timezone_report
from v2.toolkit.weather_light import air_quality_report, recent_earthquakes, weather_report

# Re-export feed background helpers for older imports.
from v2.handlers.feed_reader_commands import (  # noqa: F401
    maybe_send_daily_digest,
    poll_rss_pushes,
)

TranslateFn = Callable[..., str]
LogEventFn = Callable[..., None]
QuotaTryFn = Callable[[int], tuple[bool, str]]
QuotaCommitFn = Callable[[int], None]


@dataclass(frozen=True)
class WorldCommandDeps:
    tr: TranslateFn
    queue: Any
    get_state: Callable[[int], dict]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    extract_first_url: Callable[[str], Optional[str]]
    get_lang: Callable[[int], str] = lambda _uid: "fa"
    log_event: LogEventFn = lambda *a, **k: None
    set_menu_section: Callable[..., None] | None = None
    world_quota_try: QuotaTryFn | None = None
    world_quota_commit: QuotaCommitFn | None = None


def _lang(deps: WorldCommandDeps, user_id: int) -> str:
    try:
        return "en" if deps.get_lang(user_id) == "en" else "fa"
    except Exception:
        return "fa"


async def _guard_world(deps: WorldCommandDeps, uid: int, message: Message) -> bool:
    from v2.core.upgrade_cta import buy_pro_keyboard

    if not deps.world_quota_try:
        return True
    ok, msg = deps.world_quota_try(uid)
    if ok:
        return True
    await message.reply_text(
        msg or deps.tr(uid, "world_quota_exceeded", used="?", limit="?"),
        reply_markup=buy_pro_keyboard(uid, deps.tr),
        parse_mode=None,
    )
    return False


def _commit_world(deps: WorldCommandDeps, uid: int) -> None:
    if deps.world_quota_commit:
        try:
            deps.world_quota_commit(uid)
        except Exception:
            pass


async def handle_calendar(deps: WorldCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if not await _guard_world(deps, uid, message):
        return
    body = await asyncio.to_thread(calendar_report, lang=_lang(deps, uid))
    _commit_world(deps, uid)
    await message.reply_text(body, parse_mode=None)


async def handle_earthquakes(deps: WorldCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if not await _guard_world(deps, uid, message):
        return
    ok, body = await asyncio.to_thread(recent_earthquakes, lang=_lang(deps, uid))
    if ok:
        _commit_world(deps, uid)
    await message.reply_text(body if ok else deps.tr(uid, "world_error", detail=body), parse_mode=None)


async def dispatch_world_wizard(
    message: Message,
    user_id: int,
    text: str,
    deps: WorldCommandDeps,
) -> bool:
    """Text steps for weather / currency / timezone / age. Returns True if consumed."""
    state = deps.get_state(user_id)
    step = state.get("step")
    lang = _lang(deps, user_id)

    if step == "await_weather_city":
        city = text.strip()
        if not city:
            await message.reply_text(deps.tr(user_id, "weather_ask_city"), parse_mode=None)
            return True
        if not await _guard_world(deps, user_id, message):
            deps.clear_state(user_id)
            return True
        ok, body = await asyncio.to_thread(weather_report, city, lang=lang)
        ok2, aq = await asyncio.to_thread(air_quality_report, city, lang=lang)
        parts = [body if ok else deps.tr(user_id, "world_error", detail=body)]
        if ok2:
            parts.append("────────")
            parts.append(aq)
        if ok:
            _commit_world(deps, user_id)
        deps.clear_state(user_id)
        await message.reply_text("\n\n".join(parts), parse_mode=None)
        return True

    if step == "await_currency_amount":
        deps.set_state_preserving_menu(user_id, {"step": "await_currency_pair", "amount": text.strip()})
        await message.reply_text(deps.tr(user_id, "currency_ask_pair"), parse_mode=None)
        return True

    if step == "await_currency_pair":
        amount_s = str(state.get("amount") or text).strip()
        try:
            amount = float(amount_s.replace(",", ""))
        except ValueError:
            await message.reply_text(deps.tr(user_id, "currency_bad_amount"), parse_mode=None)
            return True
        parts = text.strip().split()
        if len(parts) < 2:
            await message.reply_text(deps.tr(user_id, "currency_ask_pair"), parse_mode=None)
            return True
        if not await _guard_world(deps, user_id, message):
            deps.clear_state(user_id)
            return True
        ok, body = await asyncio.to_thread(currency_convert, amount, parts[0], parts[1], lang=lang)
        if ok:
            _commit_world(deps, user_id)
        deps.clear_state(user_id)
        await message.reply_text(body if ok else deps.tr(user_id, "world_error", detail=body), parse_mode=None)
        return True

    if step == "await_timezone_place":
        place = text.strip()
        if not place:
            await message.reply_text(deps.tr(user_id, "timezone_ask_place"), parse_mode=None)
            return True
        if not await _guard_world(deps, user_id, message):
            deps.clear_state(user_id)
            return True
        ok, body = await asyncio.to_thread(timezone_report, place, lang=lang)
        if ok:
            _commit_world(deps, user_id)
        deps.clear_state(user_id)
        await message.reply_text(body if ok else deps.tr(user_id, "world_error", detail=body), parse_mode=None)
        return True

    if step == "await_age_date":
        raw = text.strip()
        if not raw:
            await message.reply_text(deps.tr(user_id, "age_ask_date"), parse_mode=None)
            return True
        if not await _guard_world(deps, user_id, message):
            deps.clear_state(user_id)
            return True
        ok, body = await asyncio.to_thread(age_report, raw, lang=lang)
        if ok:
            _commit_world(deps, user_id)
        deps.clear_state(user_id)
        await message.reply_text(body if ok else deps.tr(user_id, "world_error", detail=body), parse_mode=None)
        return True

    return False


async def start_weather_wizard(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_weather_city"})
    await message.reply_text(deps.tr(uid, "weather_ask_city"), parse_mode=None)


async def start_currency_wizard(deps: WorldCommandDeps, message: Message) -> None:
    from v2.core.menu_sections import MenuSection

    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_currency_amount"})
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("USD→IRR", callback_data="fxquick:1:USD:IRR"),
                InlineKeyboardButton("EUR→IRR", callback_data="fxquick:1:EUR:IRR"),
            ],
            [
                InlineKeyboardButton("100 USD→IRR", callback_data="fxquick:100:USD:IRR"),
                InlineKeyboardButton("1 USDT→IRT", callback_data="fxquick:1:USDT:IRT"),
            ],
        ]
    )
    if deps.set_menu_section:
        deps.set_menu_section(uid, MenuSection.WORLD)
    await message.reply_text(deps.tr(uid, "currency_ask_amount"), reply_markup=kb, parse_mode=None)


async def start_timezone_wizard(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_timezone_place"})
    await message.reply_text(deps.tr(uid, "timezone_ask_place"), parse_mode=None)


async def start_age_wizard(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_age_date"})
    await message.reply_text(deps.tr(uid, "age_ask_date"), parse_mode=None)


async def handle_fx_quick_callback(
    deps: WorldCommandDeps,
    client: Any,
    callback_query: Any,
    amount_s: str,
    fc: str,
    tc: str,
) -> bool:
    uid = callback_query.from_user.id
    try:
        amount = float(amount_s)
    except ValueError:
        await callback_query.answer("bad amount", show_alert=True)
        return True
    if deps.world_quota_try:
        ok_q, msg = deps.world_quota_try(uid)
        if not ok_q:
            await callback_query.answer(msg[:180] if msg else "quota", show_alert=True)
            return True
    await callback_query.answer()
    lang = _lang(deps, uid)
    ok, body = await asyncio.to_thread(currency_convert, amount, fc, tc, lang=lang)
    if ok:
        _commit_world(deps, uid)
    deps.clear_state(uid)
    await callback_query.message.reply_text(
        body if ok else deps.tr(uid, "world_error", detail=body),
        parse_mode=None,
    )
    return True
