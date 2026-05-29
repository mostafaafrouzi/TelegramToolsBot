"""Extended network toolkit commands (HTTP headers, status, port, subnet, etc.)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.toolkit.net_extra_light import (
    blacklist_check_report,
    http_headers_report,
    port_check_report,
    ssl_cert_report,
    subnet_calc_report,
    website_status_report,
)
from v2.toolkit.text_utils_light import payload_after_command

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class ToolkitNetExtraDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[[int, dict], None]
    toolkit_network_light_enabled: bool
    toolkit_quota_try: Callable[[int], tuple[bool, str]]
    toolkit_quota_commit: Callable[[int], None]


async def _run_tool(
    deps: ToolkitNetExtraDeps,
    message: Message,
    fn,
    arg: str,
    *,
    usage_key: str,
    send_only_key: str,
    step: str,
) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    raw = (arg or payload_after_command(message.text or "")).strip()
    if not raw:
        deps.set_state_preserving_menu(uid, {"step": step})
        await message.reply_text(deps.tr(uid, send_only_key), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = await asyncio.to_thread(fn, raw)
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body, parse_mode=None)


async def handle_http_headers(deps: ToolkitNetExtraDeps, client: Any, message: Message) -> None:
    await _run_tool(
        deps,
        message,
        http_headers_report,
        payload_after_command(message.text or ""),
        usage_key="toolkit_http_headers_usage",
        send_only_key="toolkit_http_headers_send_only",
        step="await_toolkit_http_headers",
    )


async def handle_website_status(deps: ToolkitNetExtraDeps, client: Any, message: Message) -> None:
    await _run_tool(
        deps,
        message,
        website_status_report,
        payload_after_command(message.text or ""),
        usage_key="toolkit_website_status_usage",
        send_only_key="toolkit_website_status_send_only",
        step="await_toolkit_website_status",
    )


async def handle_port_check(deps: ToolkitNetExtraDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    if not deps.toolkit_network_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_network_disabled"), parse_mode=None)
        return
    raw = payload_after_command(message.text or "").strip()
    if not raw:
        deps.set_state_preserving_menu(uid, {"step": "await_toolkit_port_check"})
        await message.reply_text(deps.tr(uid, "toolkit_port_check_send_only"), parse_mode=None)
        return
    parts = raw.split()
    if len(parts) < 2:
        await message.reply_text(deps.tr(uid, "toolkit_port_check_send_only"), parse_mode=None)
        return
    host, port_s = parts[0], parts[1]
    try:
        port = int(port_s)
    except ValueError:
        await message.reply_text(deps.tr(uid, "toolkit_port_check_send_only"), parse_mode=None)
        return
    ok, quota_msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(quota_msg, parse_mode=None)
        return
    ok, body = await asyncio.to_thread(port_check_report, host, port)
    if not ok:
        await message.reply_text(deps.tr(uid, "toolkit_net_error", error=body), parse_mode=None)
        return
    deps.toolkit_quota_commit(uid)
    await message.reply_text(body, parse_mode=None)


async def handle_subnet_calc(deps: ToolkitNetExtraDeps, client: Any, message: Message) -> None:
    await _run_tool(
        deps,
        message,
        subnet_calc_report,
        payload_after_command(message.text or ""),
        usage_key="toolkit_subnet_usage",
        send_only_key="toolkit_subnet_send_only",
        step="await_toolkit_subnet",
    )


async def handle_blacklist_check(deps: ToolkitNetExtraDeps, client: Any, message: Message) -> None:
    await _run_tool(
        deps,
        message,
        blacklist_check_report,
        payload_after_command(message.text or ""),
        usage_key="toolkit_blacklist_usage",
        send_only_key="toolkit_blacklist_send_only",
        step="await_toolkit_blacklist",
    )


async def handle_ssl_check(deps: ToolkitNetExtraDeps, client: Any, message: Message) -> None:
    await _run_tool(
        deps,
        message,
        ssl_cert_report,
        payload_after_command(message.text or ""),
        usage_key="toolkit_ssl_usage",
        send_only_key="toolkit_ssl_send_only",
        step="await_toolkit_ssl",
    )
