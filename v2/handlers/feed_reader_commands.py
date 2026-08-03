"""Feed Reader hub: RSS, YouTube channel, X/Twitter via RSS bridges."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.toolkit.rss_light import (
    encode_seen_ids,
    fetch_feed,
    fetch_feed_items,
    format_items_body,
    new_items_since,
)
from v2.toolkit.rss_resolve import resolve_feed_url

TranslateFn = Callable[..., str]
LogEventFn = Callable[..., None]

_FEED_PAGE_SIZE = 8


@dataclass(frozen=True)
class FeedReaderDeps:
    tr: TranslateFn
    queue: Any
    get_state: Callable[[int], dict]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    extract_first_url: Callable[[str], Optional[str]]
    get_user_tier: Callable[[int], str] | None = None
    feed_max_for_user: Callable[[int], int] | None = None
    feed_push_allowed: Callable[[int], bool] | None = None
    set_menu_section: Callable[..., None] | None = None


def _feed_limit_for_user(deps: FeedReaderDeps, user_id: int) -> int:
    if deps.feed_max_for_user:
        try:
            return max(1, int(deps.feed_max_for_user(user_id)))
        except Exception:
            pass
    try:
        free_lim = int((os.getenv("WORLD_FEED_LIMIT_FREE") or "20").strip() or "20")
    except ValueError:
        free_lim = 20
    try:
        pro_lim = int((os.getenv("WORLD_FEED_LIMIT_PRO") or "50").strip() or "50")
    except ValueError:
        pro_lim = 50
    tier = "free"
    if deps.get_user_tier:
        try:
            tier = (deps.get_user_tier(user_id) or "free").lower()
        except Exception:
            tier = "free"
    if tier == "star":
        return max(pro_lim, 100)
    return pro_lim if tier == "pro" else free_lim


def _push_allowed(deps: FeedReaderDeps, user_id: int) -> bool:
    if deps.feed_push_allowed:
        try:
            return bool(deps.feed_push_allowed(user_id))
        except Exception:
            return True
    return True


def _feed_actions_keyboard(
    user_id: int,
    feed_id: int,
    push_on: bool,
    digest_on: bool,
    tr: TranslateFn,
) -> InlineKeyboardMarkup:
    push_label = tr(user_id, "rss_push_off") if push_on else tr(user_id, "rss_push_on")
    digest_label = (
        tr(user_id, "feed_digest_off") if digest_on else tr(user_id, "feed_digest_on")
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "rss_view_now"), callback_data=f"feedview:{feed_id}"),
                InlineKeyboardButton(push_label, callback_data=f"feedpush:toggle:{feed_id}"),
            ],
            [
                InlineKeyboardButton(
                    digest_label, callback_data=f"feeddigest:toggle:{feed_id}"
                )
            ],
            [InlineKeyboardButton(tr(user_id, "feed_delete"), callback_data=f"feeddel:{feed_id}")],
        ]
    )


def _feeds_list_keyboard(
    user_id: int,
    rows: list[dict],
    tr: TranslateFn,
    *,
    page: int = 0,
) -> InlineKeyboardMarkup:
    total = len(rows)
    pages = max(1, (total + _FEED_PAGE_SIZE - 1) // _FEED_PAGE_SIZE) if total else 1
    page = max(0, min(int(page), pages - 1))
    start = page * _FEED_PAGE_SIZE
    chunk = rows[start : start + _FEED_PAGE_SIZE]
    buttons = []
    for r in chunk:
        fid = int(r["id"])
        label = (r.get("label") or r.get("feed_url") or "")[:28]
        push = "🔔" if int(r.get("push_enabled") or 0) else "🔕"
        dig = "📰" if int(r.get("digest_enabled") or 0) else "📄"
        buttons.append(
            [InlineKeyboardButton(f"{push}{dig} #{fid} {label}", callback_data=f"feedview:{fid}")]
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(tr(user_id, "feed_page_prev"), callback_data=f"feedpage:{page - 1}")
        )
    if page < pages - 1:
        nav.append(
            InlineKeyboardButton(tr(user_id, "feed_page_next"), callback_data=f"feedpage:{page + 1}")
        )
    if nav:
        buttons.append(nav)
    buttons.append(
        [InlineKeyboardButton(tr(user_id, "feed_add_btn"), callback_data="feedmenu:add")]
    )
    return InlineKeyboardMarkup(buttons)


async def handle_show_feed_menu(deps: FeedReaderDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if deps.set_menu_section:
        try:
            from v2.core.menu_sections import MenuSection

            deps.set_menu_section(uid, MenuSection.FEED)
        except Exception:
            pass
    rows = deps.queue.list_feeds(uid)
    lim = _feed_limit_for_user(deps, uid)
    hour = _digest_hour_tehran()
    body = (
        deps.tr(uid, "feed_menu_title")
        + "\n\n"
        + deps.tr(uid, "feed_digest_hint")
        + "\n"
        + deps.tr(uid, "feed_digest_schedule", hour=hour)
        + "\n"
        + deps.tr(uid, "feed_quota_line", used=len(rows), limit=lim)
    )
    if not rows:
        body += "\n\n" + deps.tr(uid, "feed_empty_state")
    await message.reply_text(
        body,
        reply_markup=_feeds_list_keyboard(uid, rows, deps.tr, page=0),
        parse_mode=None,
    )


async def start_add_feed_wizard(deps: FeedReaderDeps, message: Message) -> None:
    uid = message.from_user.id
    if deps.set_menu_section:
        try:
            from v2.core.menu_sections import MenuSection

            deps.set_menu_section(uid, MenuSection.FEED)
        except Exception:
            pass
    deps.set_state_preserving_menu(uid, {"step": "await_feed_url"})
    await message.reply_text(deps.tr(uid, "feed_ask_url"), parse_mode=None)


async def dispatch_feed_wizard(
    message: Message,
    user_id: int,
    text: str,
    deps: FeedReaderDeps,
) -> bool:
    state = deps.get_state(user_id)
    if state.get("step") not in ("await_feed_url", "await_rss_url"):
        return False

    raw = deps.extract_first_url(text) or text.strip()
    if not raw.startswith(("http://", "https://")) and "." not in raw:
        await message.reply_text(deps.tr(user_id, "rss_bad_url"), parse_mode=None)
        return True

    resolved, kind, hint = resolve_feed_url(raw)
    if not resolved:
        await message.reply_text(
            deps.tr(user_id, "feed_resolve_failed", url=raw[:200]),
            parse_mode=None,
        )
        return True

    existing = deps.queue.find_feed_by_url(user_id, resolved)
    if existing:
        deps.clear_state(user_id)
        push_on = bool(int(existing.get("push_enabled") or 0))
        digest_on = bool(int(existing.get("digest_enabled") or 0))
        await message.reply_text(
            deps.tr(user_id, "feed_already_added", feed_id=existing["id"]),
            reply_markup=_feed_actions_keyboard(
                user_id, int(existing["id"]), push_on, digest_on, deps.tr
            ),
            parse_mode=None,
        )
        return True

    lim = _feed_limit_for_user(deps, user_id)
    if deps.queue.count_feeds(user_id) >= lim:
        deps.clear_state(user_id)
        from v2.core.upgrade_cta import buy_pro_keyboard

        await message.reply_text(
            deps.tr(user_id, "feed_limit_reached", limit=lim),
            reply_markup=buy_pro_keyboard(user_id, deps.tr),
            parse_mode=None,
        )
        return True

    ok, body, h = await asyncio.to_thread(fetch_feed, resolved, 6)
    if not ok:
        await message.reply_text(
            deps.tr(user_id, "feed_fetch_failed", detail=body, url=resolved),
            parse_mode=None,
        )
        return True

    label = raw[:80]
    if kind != "rss":
        label = f"[{kind}] {label}"[:120]
    feed_id = deps.queue.add_feed(user_id, resolved, label=label, digest_enabled=True)
    if h:
        deps.queue.update_feed_hash(feed_id, h)
    deps.clear_state(user_id)

    intro = deps.tr(user_id, "feed_added", feed_id=feed_id, kind=kind)
    if hint:
        intro += f"\n\n{hint}"
    await message.reply_text(
        intro + "\n\n" + body[:3200] + "\n\n" + deps.tr(user_id, "rss_push_ask"),
        reply_markup=_feed_actions_keyboard(
            user_id, feed_id, push_on=False, digest_on=True, tr=deps.tr
        ),
        parse_mode=None,
    )
    return True


async def list_feeds_inline(deps: FeedReaderDeps, message: Message) -> None:
    uid = message.from_user.id
    rows = deps.queue.list_feeds(uid)
    if not rows:
        await message.reply_text(deps.tr(uid, "rss_list_empty"), parse_mode=None)
        return
    lines = [deps.tr(uid, "rss_list_title")]
    for r in rows:
        push = "🔔" if int(r.get("push_enabled") or 0) else "🔕"
        dig = "📰" if int(r.get("digest_enabled") or 0) else "📄"
        lines.append(f"{push}{dig} `#{r['id']}` — {r.get('label') or r.get('feed_url')}")
    await message.reply_text(
        "\n".join(lines),
        reply_markup=_feeds_list_keyboard(uid, rows, deps.tr, page=0),
        parse_mode=None,
    )


async def handle_feed_callback(
    deps: FeedReaderDeps,
    client: Any,
    callback_query: Any,
    action: str,
    feed_id: int,
) -> bool:
    uid = callback_query.from_user.id
    rows = deps.queue.list_feeds(uid)
    row = next((f for f in rows if int(f["id"]) == feed_id), None)

    if action in ("toggle", "on", "off"):
        if not row:
            await callback_query.answer(deps.tr(uid, "rss_not_found"), show_alert=True)
            return True
        if action == "on":
            new_val = True
        elif action == "off":
            new_val = False
        else:
            new_val = not bool(int(row.get("push_enabled") or 0))
        if new_val and not _push_allowed(deps, uid):
            await callback_query.answer(deps.tr(uid, "feed_push_plan_blocked"), show_alert=True)
            return True
        deps.queue.set_feed_push(feed_id, uid, new_val)
        await callback_query.answer(
            deps.tr(uid, "rss_push_enabled" if new_val else "rss_push_disabled")
        )
        digest_on = bool(int(row.get("digest_enabled") or 0))
        try:
            await callback_query.message.edit_reply_markup(
                reply_markup=_feed_actions_keyboard(uid, feed_id, new_val, digest_on, deps.tr)
            )
        except Exception:
            pass
        return True

    if action == "digest_toggle":
        if not row:
            await callback_query.answer(deps.tr(uid, "rss_not_found"), show_alert=True)
            return True
        new_val = not bool(int(row.get("digest_enabled") or 0))
        deps.queue.set_feed_digest(feed_id, uid, new_val)
        await callback_query.answer(
            deps.tr(uid, "feed_digest_enabled" if new_val else "feed_digest_disabled")
        )
        push_on = bool(int(row.get("push_enabled") or 0))
        try:
            await callback_query.message.edit_reply_markup(
                reply_markup=_feed_actions_keyboard(uid, feed_id, push_on, new_val, deps.tr)
            )
        except Exception:
            pass
        return True

    if action == "view":
        if not row:
            await callback_query.answer(deps.tr(uid, "rss_not_found"), show_alert=True)
            return True
        ok, body, h = await asyncio.to_thread(fetch_feed, row["feed_url"], 10)
        await callback_query.answer()
        push_on = bool(int(row.get("push_enabled") or 0))
        digest_on = bool(int(row.get("digest_enabled") or 0))
        await callback_query.message.reply_text(
            body if ok else deps.tr(uid, "world_error", detail=body),
            reply_markup=_feed_actions_keyboard(uid, feed_id, push_on, digest_on, deps.tr),
            parse_mode=None,
        )
        if ok and h:
            deps.queue.update_feed_hash(feed_id, h)
        return True

    if action == "del":
        if deps.queue.delete_feed(feed_id, uid):
            await callback_query.answer(deps.tr(uid, "feed_deleted"))
            try:
                await callback_query.message.edit_text(
                    deps.tr(uid, "feed_deleted"),
                    reply_markup=_feeds_list_keyboard(
                        uid, deps.queue.list_feeds(uid), deps.tr, page=0
                    ),
                    parse_mode=None,
                )
            except Exception:
                pass
        else:
            await callback_query.answer(deps.tr(uid, "rss_not_found"), show_alert=True)
        return True

    if action == "add":
        await callback_query.answer()
        await start_add_feed_wizard(deps, callback_query.message)
        return True

    if action == "page":
        await callback_query.answer()
        page = max(0, int(feed_id))
        try:
            await callback_query.message.edit_reply_markup(
                reply_markup=_feeds_list_keyboard(
                    uid, deps.queue.list_feeds(uid), deps.tr, page=page
                )
            )
        except Exception:
            pass
        return True

    return False


async def poll_rss_pushes(
    client: Any,
    queue: Any,
    tr: TranslateFn,
    *,
    log_event: LogEventFn | None = None,
    feed_push_allowed: Callable[[int], bool] | None = None,
) -> None:
    """Background: notify users when push-enabled feeds have new items."""
    log = log_event or (lambda *a, **k: None)
    feeds = queue.list_push_feeds()
    for row in feeds:
        fid = int(row["id"])
        uid = int(row["telegram_user_id"])
        if feed_push_allowed and not feed_push_allowed(uid):
            continue
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
    """Once per Tehran calendar day at configured hour; stamp persisted in SQLite."""
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
    feeds = queue.list_digest_feeds() if hasattr(queue, "list_digest_feeds") else queue.list_push_feeds()
    by_user: dict[int, list[dict]] = {}
    for row in feeds:
        by_user.setdefault(int(row["telegram_user_id"]), []).append(row)

    for uid, rows in by_user.items():
        if hasattr(queue, "feed_digest_was_sent") and queue.feed_digest_was_sent(uid, day_key):
            continue
        blocks = [tr(uid, "world_digest_title", date=day_key)]
        for row in rows[:12]:
            url = row["feed_url"]
            label = row.get("label") or url
            ok, items, _seen = await asyncio.to_thread(fetch_feed_items, url, 3)
            if not ok or not items:
                continue
            blocks.append(f"📰 {label}\n" + format_items_body(items[:3]))
        if len(blocks) <= 1:
            if hasattr(queue, "feed_digest_mark_sent"):
                queue.feed_digest_mark_sent(uid, day_key)
            continue
        try:
            await client.send_message(uid, "\n\n".join(blocks)[:3900], parse_mode=None)
            if hasattr(queue, "feed_digest_mark_sent"):
                queue.feed_digest_mark_sent(uid, day_key)
            log("world_digest_sent", user_id=uid, feeds=len(rows))
        except Exception as e:
            log("world_digest_failed", user_id=uid, error=str(e)[:200])
