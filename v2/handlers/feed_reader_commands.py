"""Feed Reader hub: RSS, YouTube channel, X/Twitter via RSS bridges."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.toolkit.rss_light import fetch_feed
from v2.toolkit.rss_resolve import resolve_feed_url

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class FeedReaderDeps:
    tr: TranslateFn
    queue: Any
    get_state: Callable[[int], dict]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    extract_first_url: Callable[[str], Optional[str]]


def _feed_actions_keyboard(user_id: int, feed_id: int, push_on: bool, tr: TranslateFn) -> InlineKeyboardMarkup:
    push_label = tr(user_id, "rss_push_off") if push_on else tr(user_id, "rss_push_on")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "rss_view_now"), callback_data=f"feedview:{feed_id}"),
                InlineKeyboardButton(push_label, callback_data=f"feedpush:toggle:{feed_id}"),
            ],
            [InlineKeyboardButton(tr(user_id, "feed_delete"), callback_data=f"feeddel:{feed_id}")],
        ]
    )


def _feeds_list_keyboard(user_id: int, rows: list[dict], tr: TranslateFn) -> InlineKeyboardMarkup:
    buttons = []
    for r in rows[:8]:
        fid = int(r["id"])
        label = (r.get("label") or r.get("feed_url") or "")[:28]
        buttons.append(
            [InlineKeyboardButton(f"#{fid} {label}", callback_data=f"feedview:{fid}")]
        )
    buttons.append(
        [InlineKeyboardButton(tr(user_id, "feed_add_btn"), callback_data="feedmenu:add")]
    )
    return InlineKeyboardMarkup(buttons)


async def handle_show_feed_menu(deps: FeedReaderDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    await message.reply_text(
        deps.tr(uid, "feed_menu_title"),
        reply_markup=_feeds_list_keyboard(uid, deps.queue.list_feeds(uid), deps.tr),
        parse_mode=None,
    )


async def start_add_feed_wizard(deps: FeedReaderDeps, message: Message) -> None:
    uid = message.from_user.id
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
        await message.reply_text(deps.tr(user_id, "rss_bad_url"), parse_mode=None)
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
    feed_id = deps.queue.add_feed(user_id, resolved, label=label)
    if h:
        deps.queue.update_feed_hash(feed_id, h)
    deps.clear_state(user_id)

    intro = deps.tr(user_id, "feed_added", feed_id=feed_id, kind=kind)
    if hint:
        intro += f"\n\n{hint}"
    await message.reply_text(
        intro + "\n\n" + body[:3200] + "\n\n" + deps.tr(user_id, "rss_push_ask"),
        reply_markup=_feed_actions_keyboard(
            user_id, feed_id, push_on=False, tr=deps.tr
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
        lines.append(f"{push} `#{r['id']}` — {r.get('label') or r.get('feed_url')}")
    await message.reply_text(
        "\n".join(lines),
        reply_markup=_feeds_list_keyboard(uid, rows, deps.tr),
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
        deps.queue.set_feed_push(feed_id, uid, new_val)
        await callback_query.answer(
            deps.tr(uid, "rss_push_enabled" if new_val else "rss_push_disabled")
        )
        return True

    if action == "view":
        if not row:
            await callback_query.answer(deps.tr(uid, "rss_not_found"), show_alert=True)
            return True
        ok, body, h = await asyncio.to_thread(fetch_feed, row["feed_url"], 10)
        await callback_query.answer()
        push_on = bool(int(row.get("push_enabled") or 0))
        await callback_query.message.reply_text(
            body if ok else deps.tr(uid, "world_error", detail=body),
            reply_markup=_feed_actions_keyboard(uid, feed_id, push_on, deps.tr),
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
                    reply_markup=_feeds_list_keyboard(uid, deps.queue.list_feeds(uid), deps.tr),
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

    return False
