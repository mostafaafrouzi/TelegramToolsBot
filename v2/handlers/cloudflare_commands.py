"""Cloudflare tool commands (EazyFlare-style read-only MVP, per-user token)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.cloudflare_client import list_dns_records, list_zones, verify_token
from v2.core.interaction_log import log_interaction
from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]


def _log_bot_reply(user_id: int, text: str, *, handler: str) -> None:
    log_interaction("bot_reply", user_id=user_id, handler=handler, text=text)


@dataclass(frozen=True)
class CloudflareCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    get_token: Callable[[int], Optional[str]]
    upsert_token: Callable[[int, str], None]
    clear_token: Callable[[int], None]
    build_cloudflare_menu: Callable[[int], Any]
    log_event: Callable[..., None]


async def dispatch_cloudflare_wizard(message: Message, user_id: int, state: dict, text: str, deps: CloudflareCommandDeps) -> bool:
    if state.get("step") != "await_cloudflare_token":
        return False
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


async def handle_show_cloudflare_menu(deps: CloudflareCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.CLOUDFLARE)
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
    if len(parts) < 2:
        await message.reply_text(deps.tr(uid, "cf_dns_usage"), parse_mode=None)
        return
    zone_id = parts[1].strip()
    name = parts[2].strip() if len(parts) >= 3 else ""
    ok, detail = await asyncio.to_thread(list_dns_records, token, zone_id, name=name)
    await message.reply_text(
        deps.tr(uid, "cf_dns_result", detail=detail) if ok else deps.tr(uid, "cf_error", error=detail),
        parse_mode=None,
    )
