"""Weather, calendar, currency, earthquakes, timezone, age, RSS push/digest."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.toolkit.calendar_light import age_report, calendar_report
from v2.toolkit.fx_light import currency_convert
from v2.toolkit.rss_light import (
    encode_seen_ids,
    fetch_feed_items,
    format_items_body,
    new_items_since,
)
from v2.toolkit.timezone_light import timezone_report
from v2.toolkit.weather_light import air_quality_report, recent_earthquakes, weather_report

TranslateFn = Callable[..., str]
LogEventFn = Callable[..., None]


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


def _lang(deps: WorldCommandDeps, user_id: int) -> str:
    try:
        return "en" if deps.get_lang(user_id) == "en" else "fa"
    except Exception:
        return "fa"


async def handle_calendar(deps: WorldCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    body = await asyncio.to_thread(calendar_report, lang=_lang(deps, uid))
    await message.reply_text(body, parse_mode=None)


async def handle_earthquakes(deps: WorldCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    ok, body = await asyncio.to_thread(recent_earthquakes, lang=_lang(deps, uid))
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
        ok, body = await asyncio.to_thread(weather_report, city, lang=lang)
        ok2, aq = await asyncio.to_thread(air_quality_report, city, lang=lang)
        parts = [body if ok else deps.tr(user_id, "world_error", detail=body)]
        if ok2:
            parts.append(aq)
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
        ok, body = await asyncio.to_thread(currency_convert, amount, parts[0], parts[1], lang=lang)
        deps.clear_state(user_id)
        await message.reply_text(body if ok else deps.tr(user_id, "world_error", detail=body), parse_mode=None)
        return True

    if step == "await_timezone_place":
        place = text.strip()
        if not place:
            await message.reply_text(deps.tr(user_id, "timezone_ask_place"), parse_mode=None)
            return True
        ok, body = await asyncio.to_thread(timezone_report, place, lang=lang)
        deps.clear_state(user_id)
        await message.reply_text(body if ok else deps.tr(user_id, "world_error", detail=body), parse_mode=None)
        return True

    if step == "await_age_date":
        raw = text.strip()
        if not raw:
            await message.reply_text(deps.tr(user_id, "age_ask_date"), parse_mode=None)
            return True
        ok, body = await asyncio.to_thread(age_report, raw, lang=lang)
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
                InlineKeyboardButton("1 IRR→USD", callback_data="fxquick:1:IRR:USD"),
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
    await callback_query.answer()
    lang = _lang(deps, uid)
    ok, body = await asyncio.to_thread(currency_convert, amount, fc, tc, lang=lang)
    deps.clear_state(uid)
    await callback_query.message.reply_text(
        body if ok else deps.tr(uid, "world_error", detail=body),
        parse_mode=None,
    )
    return True


async def poll_rss_pushes(client: Any, queue: Any, tr: TranslateFn, *, log_event: LogEventFn | None = None) -> None:
    """Background: notify users when push-enabled feeds have new items."""
    log = log_event or (lambda *a, **k: None)
    feeds = queue.list_push_feeds()
    for row in feeds:
        fid = int(row["id"])
        uid = int(row["telegram_user_id"])
        url = row["feed_url"]
        ok, items, seen = await asyncio.to_thread(fetch_feed_items, url, 10)
        if not ok or not items:
            continue
        prev = (row.get("last_content_hash") or "").strip()
        fresh = new_items_since(prev, items, limit=5)
        queue.update_feed_hash(fid, seen or encode_seen_ids(items))
        if not prev or not fresh:
            continue
        try:
            label = row.get("label") or url
            body = format_items_body(fresh)
            await client.send_message(
                uid,
                tr(uid, "rss_push_new", label=label) + "\n\n" + body[:3000],
                parse_mode=None,
            )
        except Exception as e:
            log("rss_push_send_failed", user_id=uid, feed_id=fid, error=str(e)[:200])


_DIGEST_LAST_DAY: dict[str, str] = {}


def _digest_enabled() -> bool:
    raw = (os.getenv("WORLD_DIGEST_ENABLE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _digest_hour_tehran() -> int:
    try:
        return max(0, min(23, int((os.getenv("WORLD_DIGEST_HOUR_TEHRAN") or "8").strip())))
    except ValueError:
        return 8


async def maybe_send_daily_digest(
    client: Any,
    queue: Any,
    tr: TranslateFn,
    *,
    log_event: LogEventFn | None = None,
) -> None:
    """Once per Tehran calendar day at configured hour, digest push-enabled feeds per user."""
    if not _digest_enabled():
        return
    log = log_event or (lambda *a, **k: None)
    try:
        tehran = datetime.now(ZoneInfo("Asia/Tehran"))
    except Exception:
        return
    if tehran.hour != _digest_hour_tehran():
        return
    day_key = tehran.strftime("%Y-%m-%d")
    feeds = queue.list_push_feeds()
    by_user: dict[int, list[dict]] = {}
    for row in feeds:
        by_user.setdefault(int(row["telegram_user_id"]), []).append(row)

    for uid, rows in by_user.items():
        stamp_key = f"{uid}:{day_key}"
        if _DIGEST_LAST_DAY.get(stamp_key) == "1":
            continue
        # Persist lightly via module memory; also skip if already sent this process day
        blocks = [tr(uid, "world_digest_title", date=day_key)]
        for row in rows[:12]:
            url = row["feed_url"]
            label = row.get("label") or url
            ok, items, _seen = await asyncio.to_thread(fetch_feed_items, url, 3)
            if not ok or not items:
                continue
            blocks.append(f"📰 {label}\n" + format_items_body(items[:3]))
        if len(blocks) <= 1:
            _DIGEST_LAST_DAY[stamp_key] = "1"
            continue
        try:
            await client.send_message(uid, "\n\n".join(blocks)[:3900], parse_mode=None)
            _DIGEST_LAST_DAY[stamp_key] = "1"
            log("world_digest_sent", user_id=uid, feeds=len(rows))
        except Exception as e:
            log("world_digest_failed", user_id=uid, error=str(e)[:200])
