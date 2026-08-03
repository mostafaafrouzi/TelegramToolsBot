"""Cloudflare tool commands (read + DNS create/delete with confirm)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.cloudflare_client import (
    create_dns_record,
    delete_dns_record,
    list_dns_records,
    list_dns_records_rows,
    list_zones,
    list_zones_rows,
    verify_token,
)
from v2.core.interaction_log import log_interaction
from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]

_CF_DNS_TYPES = frozenset({"A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "CAA"})


def _log_bot_reply(user_id: int, text: str, *, handler: str) -> None:
    log_interaction("bot_reply", user_id=user_id, handler=handler, text=text)


@dataclass(frozen=True)
class CloudflareCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    get_state: Callable[[int], dict]
    get_token: Callable[[int], Optional[str]]
    upsert_token: Callable[[int, str], None]
    clear_token: Callable[[int], None]
    build_cloudflare_menu: Callable[[int], Any]
    log_event: Callable[..., None]


async def dispatch_cloudflare_wizard(message: Message, user_id: int, state: dict, text: str, deps: CloudflareCommandDeps) -> bool:
    step = state.get("step")
    if step == "await_cloudflare_token":
        token = text.strip()
        try:
            ok, detail = await asyncio.to_thread(verify_token, token)
        except Exception as e:
            await message.reply_text(deps.tr(user_id, "cf_token_invalid", detail=str(e)[:500]), parse_mode=None)
            return True
        if not ok:
            await message.reply_text(deps.tr(user_id, "cf_token_invalid", detail=detail), parse_mode=None)
            return True
        deps.upsert_token(user_id, token)
        deps.clear_state(user_id)
        deps.log_event("cloudflare_connect_ok", user_id=user_id)
        await message.reply_text(
            deps.tr(user_id, "cf_connected_ok", detail=detail),
            reply_markup=deps.build_cloudflare_menu(user_id),
            parse_mode=None,
        )
        return True

    if step == "await_cf_dns_type":
        typ = text.strip().upper()
        if typ not in _CF_DNS_TYPES:
            await message.reply_text(deps.tr(user_id, "cf_dns_ask_type"), parse_mode=None)
            return True
        zone_id = str(state.get("cf_zone_id") or "")
        deps.set_state_preserving_menu(
            user_id,
            {"step": "await_cf_dns_name", "cf_zone_id": zone_id, "cf_dns_type": typ},
        )
        await message.reply_text(deps.tr(user_id, "cf_dns_ask_name"), parse_mode=None)
        return True

    if step == "await_cf_dns_name":
        name = text.strip()
        if not name:
            await message.reply_text(deps.tr(user_id, "cf_dns_ask_name"), parse_mode=None)
            return True
        deps.set_state_preserving_menu(
            user_id,
            {
                "step": "await_cf_dns_content",
                "cf_zone_id": state.get("cf_zone_id"),
                "cf_dns_type": state.get("cf_dns_type"),
                "cf_dns_name": name,
            },
        )
        await message.reply_text(deps.tr(user_id, "cf_dns_ask_content"), parse_mode=None)
        return True

    if step == "await_cf_dns_content":
        content = text.strip()
        if not content:
            await message.reply_text(deps.tr(user_id, "cf_dns_ask_content"), parse_mode=None)
            return True
        typ = str(state.get("cf_dns_type") or "")
        name = str(state.get("cf_dns_name") or "")
        zone_id = str(state.get("cf_zone_id") or "")
        deps.set_state_preserving_menu(
            user_id,
            {
                "step": "await_cf_dns_confirm",
                "cf_zone_id": zone_id,
                "cf_dns_type": typ,
                "cf_dns_name": name,
                "cf_dns_content": content,
            },
        )
        await message.reply_text(
            deps.tr(user_id, "cf_dns_confirm_create", type=typ, name=name, content=content),
            parse_mode=None,
        )
        return True

    if step == "await_cf_dns_confirm":
        ans = text.strip().lower()
        if ans not in ("yes", "y", "ok", "بله", "آره", "اره"):
            if ans in ("no", "n", "cancel", "لغو", "خیر"):
                deps.clear_state(user_id)
                await message.reply_text(deps.tr(user_id, "wizard_cancelled"), parse_mode=None)
                return True
            await message.reply_text(
                deps.tr(
                    user_id,
                    "cf_dns_confirm_create",
                    type=state.get("cf_dns_type"),
                    name=state.get("cf_dns_name"),
                    content=state.get("cf_dns_content"),
                ),
                parse_mode=None,
            )
            return True
        token = deps.get_token(user_id)
        if not token:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "cf_not_connected"), parse_mode=None)
            return True
        ok, detail = await asyncio.to_thread(
            create_dns_record,
            token,
            str(state.get("cf_zone_id") or ""),
            type_=str(state.get("cf_dns_type") or ""),
            name=str(state.get("cf_dns_name") or ""),
            content=str(state.get("cf_dns_content") or ""),
        )
        deps.clear_state(user_id)
        deps.log_event("cloudflare_dns_create", user_id=user_id, ok=ok)
        await message.reply_text(
            deps.tr(user_id, "cf_dns_write_ok", detail=detail)
            if ok
            else deps.tr(user_id, "cf_error", error=detail),
            parse_mode=None,
        )
        return True

    return False


async def handle_show_cloudflare_menu(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
    token = deps.get_token(uid)
    if token:
        body = deps.tr(uid, "cf_menu_connected")
        inline = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(deps.tr(uid, "btn_cf_status"), callback_data="cfmenu:status"),
                    InlineKeyboardButton(deps.tr(uid, "btn_cf_zones"), callback_data="cfmenu:zones"),
                ],
                [
                    InlineKeyboardButton(deps.tr(uid, "btn_cf_dns_help"), callback_data="cfmenu:dns_hint"),
                    InlineKeyboardButton(deps.tr(uid, "btn_cf_dns_add"), callback_data="cfmenu:dns_add"),
                ],
                [
                    InlineKeyboardButton(deps.tr(uid, "btn_cf_disconnect"), callback_data="cfmenu:disconnect"),
                ],
            ]
        )
        await message.reply_text(body, reply_markup=inline, parse_mode=None)
        await message.reply_text(
            deps.tr(uid, "cf_quick_help"),
            reply_markup=deps.build_cloudflare_menu(uid),
            parse_mode=None,
        )
        return
    await message.reply_text(
        deps.tr(uid, "cf_menu_title"),
        reply_markup=deps.build_cloudflare_menu(uid),
        parse_mode=None,
    )


def _cf_connect_token_from_message(text: str) -> str:
    """Only treat text after ``/cf_connect`` as a token (not reply-keyboard labels)."""
    raw = (text or "").strip()
    if not raw.lower().startswith("/cf_connect"):
        return ""
    parts = raw.split(maxsplit=1)
    return parts[1].strip() if len(parts) >= 2 else ""


async def handle_cf_connect(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
    token = _cf_connect_token_from_message(message.text or "")
    if token:
        try:
            ok, detail = await asyncio.to_thread(verify_token, token)
        except Exception as e:
            await message.reply_text(deps.tr(uid, "cf_token_invalid", detail=str(e)[:500]), parse_mode=None)
            return
        if not ok:
            await message.reply_text(deps.tr(uid, "cf_token_invalid", detail=detail), parse_mode=None)
            return
        deps.upsert_token(uid, token)
        deps.clear_state(uid)
        deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
        deps.log_event("cloudflare_connect_ok", user_id=uid)
        await message.reply_text(deps.tr(uid, "cf_connected_ok", detail=detail), reply_markup=deps.build_cloudflare_menu(uid), parse_mode=None)
        return
    deps.set_state_preserving_menu(uid, {"step": "await_cloudflare_token"})
    body = deps.tr(uid, "cf_ask_token")
    _log_bot_reply(uid, body, handler="cf_connect_prompt")
    await message.reply_text(body, parse_mode=None)


async def handle_cf_disconnect(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.clear_token(uid)
    deps.set_state_preserving_menu(uid, {})
    deps.log_event("cloudflare_disconnect", user_id=uid)
    await message.reply_text(deps.tr(uid, "cf_disconnected"), reply_markup=deps.build_cloudflare_menu(uid), parse_mode=None)


async def handle_cf_status(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
    token = deps.get_token(uid)
    if not token:
        await message.reply_text(deps.tr(uid, "cf_not_connected"), parse_mode=None)
        return
    ok, detail = await asyncio.to_thread(verify_token, token)
    await message.reply_text(
        deps.tr(uid, "cf_status_ok", detail=detail) if ok else deps.tr(uid, "cf_status_bad", detail=detail),
        parse_mode=None,
    )


async def handle_cf_zones(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
    token = deps.get_token(uid)
    if not token:
        await message.reply_text(deps.tr(uid, "cf_not_connected"), parse_mode=None)
        return
    ok, detail = await asyncio.to_thread(list_zones, token)
    await message.reply_text(
        deps.tr(uid, "cf_zones_result", detail=detail) if ok else deps.tr(uid, "cf_error", error=detail),
        parse_mode=None,
    )


async def handle_cf_dns(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
    token = deps.get_token(uid)
    if not token:
        await message.reply_text(deps.tr(uid, "cf_not_connected"), parse_mode=None)
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) >= 2 and parts[1].strip():
        zone_id = parts[1].strip()
        name = parts[2].strip() if len(parts) >= 3 else ""
        ok, detail = await asyncio.to_thread(list_dns_records, token, zone_id, name=name)
        await message.reply_text(
            deps.tr(uid, "cf_dns_result", detail=detail) if ok else deps.tr(uid, "cf_error", error=detail),
            parse_mode=None,
        )
        return
    await prompt_cf_dns_zone_picker(deps, message)


async def prompt_cf_dns_zone_picker(
    deps: CloudflareCommandDeps,
    message: Message,
    *,
    mode: str = "list",
) -> None:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    uid = message.from_user.id
    token = deps.get_token(uid)
    if not token:
        await message.reply_text(deps.tr(uid, "cf_not_connected"), parse_mode=None)
        return
    ok, rows = await asyncio.to_thread(list_zones_rows, token)
    if not ok:
        await message.reply_text(deps.tr(uid, "cf_error", error=str(rows)), parse_mode=None)
        return
    if not rows:
        await message.reply_text(deps.tr(uid, "cf_zones_empty"), parse_mode=None)
        return
    prefix = "cfdnsadd" if mode == "add" else ("cfdnsdelz" if mode == "del" else "cfdns")
    buttons = []
    for z in rows[:12]:
        zid = z.get("id") or ""
        name = (z.get("name") or zid)[:40]
        if not zid:
            continue
        buttons.append([InlineKeyboardButton(name, callback_data=f"{prefix}:{zid}")])
    prompt_key = "cf_dns_pick_zone_add" if mode == "add" else ("cf_dns_pick_zone_del" if mode == "del" else "cf_dns_pick_zone")
    await message.reply_text(
        deps.tr(uid, prompt_key),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=None,
    )


async def handle_cf_dns_zone_callback(
    deps: CloudflareCommandDeps,
    client: Any,
    callback_query: Any,
    zone_id: str,
) -> bool:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    uid = callback_query.from_user.id
    token = deps.get_token(uid)
    if not token:
        await callback_query.answer(deps.tr(uid, "cf_not_connected"), show_alert=True)
        return True
    await callback_query.answer()
    ok, detail = await asyncio.to_thread(list_dns_records, token, zone_id)
    body = deps.tr(uid, "cf_dns_result", detail=detail) if ok else deps.tr(uid, "cf_error", error=detail)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(deps.tr(uid, "btn_cf_dns_add"), callback_data=f"cfdnsadd:{zone_id}"),
                InlineKeyboardButton(deps.tr(uid, "btn_cf_dns_del"), callback_data=f"cfdnsdelz:{zone_id}"),
            ]
        ]
    )
    await callback_query.message.reply_text(body, reply_markup=kb, parse_mode=None)
    return True


async def handle_cf_dns_add_zone_callback(
    deps: CloudflareCommandDeps,
    client: Any,
    callback_query: Any,
    zone_id: str,
) -> bool:
    uid = callback_query.from_user.id
    if not deps.get_token(uid):
        await callback_query.answer(deps.tr(uid, "cf_not_connected"), show_alert=True)
        return True
    await callback_query.answer()
    deps.set_state_preserving_menu(uid, {"step": "await_cf_dns_type", "cf_zone_id": zone_id})
    await callback_query.message.reply_text(deps.tr(uid, "cf_dns_ask_type"), parse_mode=None)
    return True


async def handle_cf_dns_del_zone_callback(
    deps: CloudflareCommandDeps,
    client: Any,
    callback_query: Any,
    zone_id: str,
) -> bool:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    uid = callback_query.from_user.id
    token = deps.get_token(uid)
    if not token:
        await callback_query.answer(deps.tr(uid, "cf_not_connected"), show_alert=True)
        return True
    await callback_query.answer()
    ok, rows = await asyncio.to_thread(list_dns_records_rows, token, zone_id, limit=20)
    if not ok:
        await callback_query.message.reply_text(deps.tr(uid, "cf_error", error=str(rows)), parse_mode=None)
        return True
    if not rows:
        await callback_query.message.reply_text(deps.tr(uid, "cf_dns_empty"), parse_mode=None)
        return True
    # Keep zone_id in state; callback only carries record id (Telegram 64-byte limit).
    deps.set_state_preserving_menu(uid, {"step": "await_cf_dns_del_pick", "cf_zone_id": zone_id})
    buttons = []
    for r in rows[:15]:
        rid = r.get("id") or ""
        if not rid:
            continue
        label = f"🗑 {r.get('type')} {(r.get('name') or '')[:28]}"
        buttons.append([InlineKeyboardButton(label[:60], callback_data=f"cfdnsdel:{rid}")])
    await callback_query.message.reply_text(
        deps.tr(uid, "cf_dns_pick_record_del"),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=None,
    )
    return True


async def handle_cf_dns_delete_callback(
    deps: CloudflareCommandDeps,
    client: Any,
    callback_query: Any,
    record_id: str,
) -> bool:
    uid = callback_query.from_user.id
    token = deps.get_token(uid)
    if not token:
        await callback_query.answer(deps.tr(uid, "cf_not_connected"), show_alert=True)
        return True
    zone_id = str(deps.get_state(uid).get("cf_zone_id") or "")
    await callback_query.answer()
    if not zone_id:
        await callback_query.message.reply_text(deps.tr(uid, "cf_dns_del_need_zone"), parse_mode=None)
        return True
    ok, detail = await asyncio.to_thread(delete_dns_record, token, zone_id, record_id)
    deps.clear_state(uid)
    deps.log_event("cloudflare_dns_delete", user_id=uid, ok=ok)
    await callback_query.message.reply_text(
        deps.tr(uid, "cf_dns_write_ok", detail=detail)
        if ok
        else deps.tr(uid, "cf_error", error=detail),
        parse_mode=None,
    )
    return True
