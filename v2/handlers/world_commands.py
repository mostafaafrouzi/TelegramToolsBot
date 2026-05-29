"""Weather, calendar, currency, earthquakes, RSS feeds."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.toolkit.calendar_light import calendar_report
from v2.toolkit.rss_light import fetch_feed
from v2.toolkit.rss_resolve import resolve_feed_url
from v2.toolkit.weather_light import (
    air_quality_report,
    currency_convert,
    recent_earthquakes,
    weather_report,
)

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class WorldCommandDeps:
    tr: TranslateFn
    queue: Any
    get_state: Callable[[int], dict]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    extract_first_url: Callable[[str], Optional[str]]


def _rss_push_keyboard(user_id: int, feed_id: int, tr: TranslateFn) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "rss_push_on"), callback_data=f"rsspush:on:{feed_id}"),
                InlineKeyboardButton(tr(user_id, "rss_push_off"), callback_data=f"rsspush:off:{feed_id}"),
            ],
            [InlineKeyboardButton(tr(user_id, "rss_view_now"), callback_data=f"rssview:{feed_id}")],
        ]
    )


async def handle_calendar(deps: WorldCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    body = await asyncio.to_thread(calendar_report)
    await message.reply_text(body, parse_mode=None)


async def handle_earthquakes(deps: WorldCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    ok, body = await asyncio.to_thread(recent_earthquakes)
    await message.reply_text(body if ok else deps.tr(uid, "world_error", detail=body), parse_mode=None)


async def dispatch_world_wizard(
    message: Message,
    user_id: int,
    text: str,
    deps: WorldCommandDeps,
) -> bool:
    """Text steps for weather / currency / RSS. Returns True if consumed."""
    from v2.core.menu_sections import MenuSection

    state = deps.get_state(user_id)
    step = state.get("step")

    if step == "await_weather_city":
        city = text.strip()
        if not city:
            await message.reply_text(deps.tr(user_id, "weather_ask_city"), parse_mode=None)
            return True
        ok, body = await asyncio.to_thread(weather_report, city)
        ok2, aq = await asyncio.to_thread(air_quality_report, city)
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
        ok, body = await asyncio.to_thread(currency_convert, amount, parts[0], parts[1])
        deps.clear_state(user_id)
        await message.reply_text(body if ok else deps.tr(user_id, "world_error", detail=body), parse_mode=None)
        return True

    if step == "await_rss_url":
        raw = deps.extract_first_url(text) or text.strip()
        if not raw.startswith(("http://", "https://")) and "." not in raw:
            await message.reply_text(deps.tr(user_id, "rss_bad_url"), parse_mode=None)
            return True
        url, kind, hint = resolve_feed_url(raw)
        if not url:
            await message.reply_text(deps.tr(user_id, "rss_bad_url"), parse_mode=None)
            return True
        ok, body, h = await asyncio.to_thread(fetch_feed, url, 5)
        if not ok:
            await message.reply_text(deps.tr(user_id, "world_error", detail=body), parse_mode=None)
            return True
        label = raw[:80] if kind == "rss" else f"[{kind}] {raw[:70]}"
        feed_id = deps.queue.add_feed(user_id, url, label=label)
        if h:
            deps.queue.update_feed_hash(feed_id, h)
        deps.clear_state(user_id)
        intro = deps.tr(user_id, "rss_added", feed_id=feed_id)
        if hint:
            intro += f"\n\n{hint}"
        await message.reply_text(
            intro
            + "\n\n"
            + body[:3500]
            + "\n\n"
            + deps.tr(user_id, "rss_push_ask"),
            reply_markup=_rss_push_keyboard(user_id, feed_id, deps.tr),
            parse_mode=None,
        )
        return True

    return False


async def start_weather_wizard(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_weather_city"})
    await message.reply_text(deps.tr(uid, "weather_ask_city"), parse_mode=None)


async def start_currency_wizard(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_currency_amount"})
    await message.reply_text(deps.tr(uid, "currency_ask_amount"), parse_mode=None)


async def start_rss_wizard(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_state_preserving_menu(uid, {"step": "await_feed_url"})
    await message.reply_text(deps.tr(uid, "feed_ask_url"), parse_mode=None)


async def list_rss_feeds(deps: WorldCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    rows = deps.queue.list_feeds(uid)
    if not rows:
        await message.reply_text(deps.tr(uid, "rss_list_empty"), parse_mode=None)
        return
    lines = [deps.tr(uid, "rss_list_title")]
    for r in rows:
        push = "🔔" if int(r.get("push_enabled") or 0) else "🔕"
        lines.append(f"{push} `#{r['id']}` — {r.get('label') or r.get('feed_url')}")
    await message.reply_text("\n".join(lines), parse_mode=None)


async def handle_rss_push_callback(
    deps: WorldCommandDeps,
    client: Any,
    callback_query: Any,
    action: str,
    feed_id: int,
) -> bool:
    uid = callback_query.from_user.id
    if action == "on":
        deps.queue.set_feed_push(feed_id, uid, True)
        await callback_query.answer(deps.tr(uid, "rss_push_enabled"))
    elif action == "off":
        deps.queue.set_feed_push(feed_id, uid, False)
        await callback_query.answer(deps.tr(uid, "rss_push_disabled"))
    else:
        row = next((f for f in deps.queue.list_feeds(uid) if int(f["id"]) == feed_id), None)
        if not row:
            await callback_query.answer(deps.tr(uid, "rss_not_found"), show_alert=True)
            return True
        ok, body, h = await asyncio.to_thread(fetch_feed, row["feed_url"], 8)
        await callback_query.answer()
        await callback_query.message.reply_text(
            body if ok else deps.tr(uid, "world_error", detail=body),
            parse_mode=None,
        )
        if ok and h:
            deps.queue.update_feed_hash(feed_id, h)
        return True
    return True


async def poll_rss_pushes(client: Any, queue: Any, tr: TranslateFn) -> None:
    """Background: notify users when push-enabled feed content changes."""
    feeds = queue.list_push_feeds()
    for row in feeds:
        fid = int(row["id"])
        uid = int(row["telegram_user_id"])
        url = row["feed_url"]
        ok, body, h = await asyncio.to_thread(fetch_feed, url, 5)
        if not ok or not h:
            continue
        prev = (row.get("last_content_hash") or "").strip()
        if prev and prev == h:
            continue
        queue.update_feed_hash(fid, h)
        if not prev:
            continue
        try:
            label = row.get("label") or url
            await client.send_message(
                uid,
                tr(uid, "rss_push_new", label=label) + "\n\n" + body[:3000],
                parse_mode=None,
            )
        except Exception:
            pass
