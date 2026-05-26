"""Toolkit slash commands (feature-flagged)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.toolkit.dns_light import resolve_hostname
from v2.toolkit.google_search_light import google_search
from v2.toolkit.ipinfo_light import get_ip_info
from v2.toolkit.myip_light import get_public_ip
from v2.toolkit.ping_light import tcp_ping
from v2.toolkit.text_utils_light import (
    b64_decode_str,
    b64_encode_str,
    clip_input,
    md5_hex,
    payload_after_command,
    sha256_hex,
)
from v2.toolkit.whois_light import rdap_lookup

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class ToolkitCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[[int, dict], None]
    clear_state: Callable[[int], None]
    toolkit_network_light_enabled: bool
    toolkit_utility_light_enabled: bool
    toolkit_quota_try: Callable[[int], tuple[bool, str]]
    toolkit_quota_commit: Callable[[int], None]
    miniapp_base_url: str = ""


async def _guard_toolkit_quota_try(deps: ToolkitCommandDeps, message: Message, uid: int) -> bool:
    ok, msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(msg, parse_mode=None)
        return False
    return True


async def handle_dns_lookup(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_dns"})
        await message.reply_text(deps.tr(uid, "toolkit_dns_send_only"), parse_mode=None)
        return
    host = parts[1].strip()
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    ok, body = resolve_hostname(host)
    if not ok:
        await message.reply_text(
            deps.tr(uid, "toolkit_dns_error", host=host, error=body),
            parse_mode=None,
        )
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(
        deps.tr(uid, "toolkit_dns_result", host=host, ips=body),
        parse_mode=None,
    )


async def handle_my_ip(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    base = (getattr(deps, "miniapp_base_url", None) or "").strip()
    if base:
        url = f"{base.rstrip('/')}/miniapp/myip.html"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(deps.tr(uid, "btn_open_myip_app"), web_app=WebAppInfo(url=url))]]
        )
        await message.reply_text(deps.tr(uid, "miniapp_myip_open"), reply_markup=kb, parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    ok, body = get_public_ip()
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_myip_error", error=body), parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(
        deps.tr(uid, "toolkit_myip_server_fallback", ip=body),
        parse_mode=None,
    )


async def handle_tcp_ping(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_ping"})
        await message.reply_text(deps.tr(uid, "toolkit_ping_send_only"), parse_mode=None)
        return
    host = parts[1].strip()
    port = 443
    if len(parts) >= 3:
        try:
            port = int(parts[2].strip())
        except ValueError:
            await message.reply_text(deps.tr(uid, "toolkit_ping_usage"), parse_mode=None)
            return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    ok, body = tcp_ping(host, port=port)
    if not ok:
        await message.reply_text(
            deps.tr(uid, "toolkit_ping_error", host=host, port=port, error=body),
            parse_mode=None,
        )
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(
        deps.tr(uid, "toolkit_ping_result", host=host, port=port, ms=body),
        parse_mode=None,
    )


async def handle_ipinfo(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_ipinfo"})
        await message.reply_text(deps.tr(uid, "toolkit_ipinfo_send_only"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    ok, body = get_ip_info(parts[1].strip())
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_ipinfo_error", error=body), parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_ipinfo_result", data=body), parse_mode=None)


async def handle_whois(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_whois"})
        await message.reply_text(deps.tr(uid, "toolkit_whois_send_only"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    ok, body = rdap_lookup(parts[1].strip())
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_whois_error", error=body), parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_whois_result", data=body), parse_mode=None)


async def handle_my_id(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    user = message.from_user
    username = f"@{user.username}" if getattr(user, "username", None) else "-"
    await message.reply_text(
        deps.tr(
            uid,
            "toolkit_myid_result",
            user_id=uid,
            username=username,
            chat_id=message.chat.id,
        ),
        parse_mode=None,
    )


async def handle_google_search(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    text = message.text or ""
    image = text.split(maxsplit=1)[0].lower().lstrip("/") == "gisearch"
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(deps.tr(uid, "toolkit_gsearch_usage"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    ok, body = google_search(parts[1].strip(), image=image)
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_gsearch_error", error=body), parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_gsearch_result", data=body), parse_mode=None)


async def handle_md5(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    raw = payload_after_command(message.text or "")
    if not raw.strip():
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_md5"})
        await message.reply_text(deps.tr(uid, "toolkit_md5_send_only"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    text, trunc = clip_input(raw)
    h = md5_hex(text)
    extra = "\n" + deps.tr(uid, "toolkit_input_truncated") if trunc else ""
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_md5_result", digest=h) + extra, parse_mode=None)


async def handle_sha256(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    raw = payload_after_command(message.text or "")
    if not raw.strip():
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_sha256"})
        await message.reply_text(deps.tr(uid, "toolkit_sha256_send_only"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    text, trunc = clip_input(raw)
    h = sha256_hex(text)
    extra = "\n" + deps.tr(uid, "toolkit_input_truncated") if trunc else ""
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_sha256_result", digest=h) + extra, parse_mode=None)


async def handle_b64_encode(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    raw = payload_after_command(message.text or "")
    if not raw.strip():
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_b64e"})
        await message.reply_text(deps.tr(uid, "toolkit_b64e_send_only"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    text, trunc = clip_input(raw)
    out = b64_encode_str(text)
    extra = "\n" + deps.tr(uid, "toolkit_input_truncated") if trunc else ""
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_b64e_result", data=out) + extra, parse_mode=None)


async def handle_b64_decode(deps: ToolkitCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    raw = payload_after_command(message.text or "")
    if not raw.strip():
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_b64d"})
        await message.reply_text(deps.tr(uid, "toolkit_b64d_send_only"), parse_mode=None)
        return
    if not await _guard_toolkit_quota_try(deps, message, uid):
        return
    text, trunc = clip_input(raw)
    ok, out = b64_decode_str(text)
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_b64d_error", error=out), parse_mode=None)
        return
    extra = "\n" + deps.tr(uid, "toolkit_input_truncated") if trunc else ""
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_b64d_result", data=out) + extra, parse_mode=None)
