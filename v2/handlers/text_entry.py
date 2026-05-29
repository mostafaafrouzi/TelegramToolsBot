"""Primary text-message pipeline extracted from telebot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.core.nav import maybe_disable_direct_mode
from v2.toolkit.dns_light import resolve_hostname
from v2.toolkit.ipinfo_light import get_ip_info
from v2.toolkit.ping_light import smart_tcp_ping
from v2.toolkit.text_utils_light import (
    b64_decode_str,
    b64_encode_str,
    clip_input,
    md5_hex,
    sha256_hex,
)
from v2.toolkit.whois_light import rdap_lookup

TranslateFn = Callable[..., str]
ResolveRouteFn = Callable[[str], Optional[str]]
AsyncRouteFn = Callable[..., Awaitable[bool]]
AsyncWizardFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class TextEntryDeps:
    tr: TranslateFn
    get_state: Callable[[int], dict]
    set_menu_section: Callable[[int, MenuSection], None]
    build_plan_menu: Callable[[int], Any]
    resolve_reply_button_route: Callable[..., Optional[str]]
    dispatch_reply_keyboard_route: AsyncRouteFn
    reply_route_deps: Any
    clear_state: Callable[[int], None]
    enqueue_rubika_text_message: Callable[[Message, str], Awaitable[None]]
    dispatch_rubika_connect_wizard: AsyncWizardFn
    rubika_wizard_deps: Any
    dispatch_provider_connect_wizard: AsyncWizardFn
    provider_connect_wizard_deps: Any
    dispatch_cloudflare_wizard: AsyncWizardFn
    cloudflare_command_deps: Any
    dispatch_admin_wizard: AsyncWizardFn
    admin_command_deps: Any
    set_state_preserving_menu: Callable[..., None]
    toolkit_network_light_enabled: bool
    toolkit_utility_light_enabled: bool
    toolkit_quota_try: Callable[[int], tuple[bool, str]]
    toolkit_quota_commit: Callable[[int], None]
    dispatch_zip_batch_wizard: AsyncWizardFn
    zip_batch_wizard_deps: Any
    handle_zip_password_text: AsyncWizardFn
    zip_password_deps: Any
    handle_direct_mode_plain_text: AsyncWizardFn
    direct_mode_text_deps: Any
    handle_direct_url_sendlink_hint: AsyncWizardFn
    direct_url_hint_deps: Any
    handle_link_direct_text: AsyncWizardFn
    link_direct_deps: Any
    build_main_menu: Callable[[int], Any]
    dispatch_world_wizard: AsyncWizardFn
    dispatch_feed_wizard: AsyncWizardFn
    feed_reader_deps: Any
    dispatch_toolkit_net_extra_wizard: Callable[..., Awaitable[bool]]
    toolkit_net_extra_deps: Any
    dispatch_ssh_wizard: Callable[..., Awaitable[bool]]
    ssh_wizard_deps: Any
    world_command_deps: Any
    get_direct_mode_target: Callable[[int], Optional[str]]
    set_direct_mode_target: Callable[[int, Optional[str]], None]


async def handle_text_entry(deps: TextEntryDeps, client: Any, message: Message) -> None:
    text = message.text or ""
    user_id = message.from_user.id
    state = deps.get_state(user_id)

    section = None
    try:
        section = deps.get_state(user_id).get("menu_section")
    except Exception:
        section = None
    mapped = deps.resolve_reply_button_route(text, user_id, deps.tr, menu_section=section)
    if mapped and mapped not in ("/directmode",):
        maybe_disable_direct_mode(
            user_id, deps.get_direct_mode_target, deps.set_direct_mode_target
        )
    if await deps.dispatch_reply_keyboard_route(client, message, user_id, mapped, deps.reply_route_deps):
        return

    if state.get("step") == "await_quick_message":
        deps.clear_state(user_id)
        await deps.enqueue_rubika_text_message(message, text)
        return

    if await deps.dispatch_rubika_connect_wizard(
        message,
        user_id,
        state,
        text,
        deps.rubika_wizard_deps,
    ):
        return

    if await deps.dispatch_provider_connect_wizard(
        message,
        user_id,
        state,
        text,
        deps.provider_connect_wizard_deps,
    ):
        return

    state = deps.get_state(user_id)
    if state.get("step") == "await_cloudflare_token":
        if await deps.dispatch_cloudflare_wizard(
            message,
            user_id,
            state,
            text,
            deps.cloudflare_command_deps,
        ):
            return

    if await deps.dispatch_ssh_wizard(deps.ssh_wizard_deps, message, user_id, state, text):
        return

    if await deps.dispatch_feed_wizard(message, user_id, text, deps.feed_reader_deps):
        return

    if await deps.dispatch_world_wizard(message, user_id, text, deps.world_command_deps):
        return

    if await deps.dispatch_zip_batch_wizard(
        message,
        user_id,
        state,
        text,
        deps.zip_batch_wizard_deps,
    ):
        return

    # Toolkit "send only" input steps (after clicking menu buttons).
    if state.get("step") == "await_toolkit_ipinfo":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        ip = (text or "").strip()
        if not ip:
            await message.reply_text(deps.tr(user_id, "toolkit_ipinfo_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        ok, body = get_ip_info(ip)
        if not ok:
            await message.reply_text(deps.tr(user_id, "toolkit_ipinfo_error", error=body), parse_mode=None)
            deps.clear_state(user_id)
            return
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(deps.tr(user_id, "toolkit_ipinfo_result", data=body), parse_mode=None)
        return

    if state.get("step") == "await_toolkit_whois":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        target = (text or "").strip()
        if not target:
            await message.reply_text(deps.tr(user_id, "toolkit_whois_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        ok, body = rdap_lookup(target)
        if not ok:
            await message.reply_text(deps.tr(user_id, "toolkit_whois_error", error=body), parse_mode=None)
            deps.clear_state(user_id)
            return
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(deps.tr(user_id, "toolkit_whois_result", data=body), parse_mode=None)
        return

    if state.get("step") == "await_toolkit_dns":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        host = (text or "").strip()
        if not host:
            await message.reply_text(deps.tr(user_id, "toolkit_dns_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        ok, body = resolve_hostname(host)
        if not ok:
            await message.reply_text(deps.tr(user_id, "toolkit_dns_error", host=host, error=body), parse_mode=None)
            deps.clear_state(user_id)
            return
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(deps.tr(user_id, "toolkit_dns_result", host=host, ips=body), parse_mode=None)
        return

    if state.get("step") == "await_toolkit_ping":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        parts = (text or "").strip().split()
        host = parts[0] if parts else ""
        port: int | None = None
        if len(parts) >= 2:
            try:
                port = int(parts[1])
            except ValueError:
                port = None
        if not host:
            await message.reply_text(deps.tr(user_id, "toolkit_ping_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        ok, ms, used_port = smart_tcp_ping(host, port=port)
        if not ok:
            await message.reply_text(
                deps.tr(user_id, "toolkit_ping_error", host=host, port=used_port or 443, error=ms),
                parse_mode=None,
            )
            deps.clear_state(user_id)
            return
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(
            deps.tr(user_id, "toolkit_ping_result", host=host, port=used_port, ms=ms),
            parse_mode=None,
        )
        return

    if state.get("step") in (
        "await_toolkit_md5",
        "await_toolkit_sha256",
        "await_toolkit_b64e",
        "await_toolkit_b64d",
    ):
        if not deps.toolkit_utility_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_utility_disabled"), parse_mode=None)
            return
        raw = (text or "").strip()
        step = state.get("step")
        hint = {
            "await_toolkit_md5": "toolkit_md5_send_only",
            "await_toolkit_sha256": "toolkit_sha256_send_only",
            "await_toolkit_b64e": "toolkit_b64e_send_only",
            "await_toolkit_b64d": "toolkit_b64d_send_only",
        }.get(step, "text_unhandled_hint")
        if not raw:
            await message.reply_text(deps.tr(user_id, hint), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        inp, trunc = clip_input(raw)
        extra = "\n" + deps.tr(user_id, "toolkit_input_truncated") if trunc else ""
        if step == "await_toolkit_md5":
            out = md5_hex(inp)
            deps.toolkit_quota_commit(user_id)
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_md5_result", digest=out) + extra, parse_mode=None)
            return
        if step == "await_toolkit_sha256":
            out = sha256_hex(inp)
            deps.toolkit_quota_commit(user_id)
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_sha256_result", digest=out) + extra, parse_mode=None)
            return
        if step == "await_toolkit_b64e":
            out = b64_encode_str(inp)
            deps.toolkit_quota_commit(user_id)
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_b64e_result", data=out) + extra, parse_mode=None)
            return
        ok, out = b64_decode_str(inp)
        if not ok:
            await message.reply_text(deps.tr(user_id, "toolkit_b64d_error", error=out), parse_mode=None)
            deps.clear_state(user_id)
            return
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(deps.tr(user_id, "toolkit_b64d_result", data=out) + extra, parse_mode=None)
        return

    state = deps.get_state(user_id)
    step = state.get("step")
    if step and await deps.dispatch_toolkit_net_extra_wizard(
        deps.toolkit_net_extra_deps,
        message,
        user_id,
        text,
        step,
    ):
        return

    if step == "await_toolkit_rev_dns":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        ip = (text or "").strip()
        if not ip:
            await message.reply_text(deps.tr(user_id, "toolkit_rev_dns_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        from v2.toolkit.extra_tools_light import reverse_dns

        ok, body = reverse_dns(ip)
        if not ok:
            await message.reply_text(deps.tr(user_id, "toolkit_net_error", error=body), parse_mode=None)
            deps.clear_state(user_id)
            return
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(body, parse_mode=None)
        return

    if state.get("step") == "await_toolkit_mac":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        mac = (text or "").strip()
        if not mac:
            await message.reply_text(deps.tr(user_id, "toolkit_mac_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        from v2.toolkit.mac_light import mac_vendor_lookup

        ok, body = mac_vendor_lookup(mac)
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(
            body if ok else deps.tr(user_id, "toolkit_net_error", error=body),
            parse_mode=None,
        )
        return

    if state.get("step") == "await_toolkit_email":
        if not deps.toolkit_utility_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_utility_disabled"), parse_mode=None)
            return
        addr = (text or "").strip()
        if not addr:
            await message.reply_text(deps.tr(user_id, "toolkit_email_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        from v2.toolkit.email_light import validate_email

        ok, body = validate_email(addr)
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(
            body if ok else deps.tr(user_id, "toolkit_net_error", error=body),
            parse_mode=None,
        )
        return

    if state.get("step") == "await_toolkit_url_expand":
        if not deps.toolkit_network_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_network_disabled"), parse_mode=None)
            return
        url = (text or "").strip()
        if not url:
            await message.reply_text(deps.tr(user_id, "toolkit_url_expand_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        from v2.toolkit.extra_tools_light import expand_url

        ok, body = expand_url(url)
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(
            body if ok else deps.tr(user_id, "toolkit_net_error", error=body),
            parse_mode=None,
        )
        return

    if state.get("step") == "await_toolkit_timestamp":
        if not deps.toolkit_utility_light_enabled:
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "toolkit_utility_disabled"), parse_mode=None)
            return
        raw = (text or "").strip()
        if not raw:
            await message.reply_text(deps.tr(user_id, "toolkit_timestamp_send_only"), parse_mode=None)
            return
        ok, quota_msg = deps.toolkit_quota_try(user_id)
        if not ok:
            deps.clear_state(user_id)
            await message.reply_text(quota_msg, parse_mode=None)
            return
        from v2.toolkit.extra_tools_light import unix_timestamp_convert

        ok, body = unix_timestamp_convert(raw)
        deps.toolkit_quota_commit(user_id)
        deps.clear_state(user_id)
        await message.reply_text(
            body if ok else deps.tr(user_id, "toolkit_net_error", error=body),
            parse_mode=None,
        )
        return

    if await deps.handle_zip_password_text(message, user_id, text, deps.zip_password_deps):
        return

    if await deps.dispatch_admin_wizard(deps.admin_command_deps, message, user_id, state, text):
        next_state = getattr(message, "_admin_next_state", None)
        if isinstance(next_state, dict):
            deps.set_state_preserving_menu(user_id, next_state)
        elif getattr(message, "_admin_clear_state", False):
            deps.clear_state(user_id)
        return

    if await deps.handle_link_direct_text(deps.link_direct_deps, client, message, user_id, text):
        return

    if await deps.handle_direct_mode_plain_text(message, user_id, text, deps.direct_mode_text_deps):
        return

    if await deps.handle_direct_url_sendlink_hint(message, user_id, text, deps.direct_url_hint_deps):
        return

    await message.reply_text(
        deps.tr(user_id, "text_unhandled_hint"),
        reply_markup=deps.build_main_menu(user_id),
        parse_mode=None,
    )
