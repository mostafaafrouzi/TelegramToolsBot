"""Extra utility commands (password, reverse DNS, URL expand, timestamp)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.toolkit.email_light import validate_email
from v2.toolkit.extra_tools_light import (
    expand_url,
    generate_password,
    lorem_ipsum,
    reverse_dns,
    unix_timestamp_convert,
)
from v2.toolkit.mac_light import mac_vendor_lookup
from v2.toolkit.text_utils_light import payload_after_command

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class ToolkitExtraDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[[int, dict], None]
    toolkit_utility_light_enabled: bool
    toolkit_network_light_enabled: bool
    toolkit_quota_try: Callable[[int], tuple[bool, str]]
    toolkit_quota_commit: Callable[[int], None]


async def handle_password(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    parts = (message.text or "").split()
    length = 16
    if len(parts) >= 2:
        try:
            length = int(parts[1])
        except ValueError:
            pass
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    pwd = generate_password(length)
    deps.toolkit_quota_commit(uid)
    await message.reply_text(deps.tr(uid, "toolkit_password_result", password=pwd), parse_mode=None)


async def handle_reverse_dns(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    ip = payload_after_command(message.text or "").strip()
    if not ip:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_rev_dns"})
        await message.reply_text(deps.tr(uid, "toolkit_rev_dns_send_only"), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = await asyncio.to_thread(reverse_dns, ip)
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body if ok else deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)


async def handle_url_expand(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    url = payload_after_command(message.text or "").strip()
    if not url:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_url_expand"})
        await message.reply_text(deps.tr(uid, "toolkit_url_expand_send_only"), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = await asyncio.to_thread(expand_url, url)
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body if ok else deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)


async def handle_timestamp(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    raw = payload_after_command(message.text or "").strip()
    if not raw:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_timestamp"})
        await message.reply_text(deps.tr(uid, "toolkit_timestamp_send_only"), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = unix_timestamp_convert(raw)
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body if ok else deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)


async def handle_mac_lookup(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    mac = payload_after_command(message.text or "").strip()
    if not mac:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_mac"})
        await message.reply_text(deps.tr(uid, "toolkit_mac_send_only"), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = await asyncio.to_thread(mac_vendor_lookup, mac)
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body if ok else deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)


async def handle_email_check(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    addr = payload_after_command(message.text or "").strip()
    if not addr:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_email"})
        await message.reply_text(deps.tr(uid, "toolkit_email_send_only"), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = validate_email(addr)
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body if ok else deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)


async def handle_lorem(deps: ToolkitExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    parts = (message.text or "").split()
    words = 40
    if len(parts) >= 2:
        try:
            words = int(parts[1])
        except ValueError:
            pass
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(lorem_ipsum(words), parse_mode=None)
