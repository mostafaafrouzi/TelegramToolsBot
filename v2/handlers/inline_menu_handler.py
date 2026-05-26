"""Dispatch inline menu callbacks (imenu:*)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, FrozenSet, Optional

from pyrogram.errors import MessageNotModified

from v2.core import inline_menus
from v2.core.nav import maybe_disable_direct_mode
from v2.handlers.world_commands import (
    handle_calendar,
    handle_earthquakes,
    list_rss_feeds,
    start_currency_wizard,
    start_rss_wizard,
    start_weather_wizard,
)

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class InlineMenuDeps:
    tr: TranslateFn
    admin_ids: FrozenSet[int]
    miniapp_base_url: str
    get_direct_mode_target: Callable[[int], Optional[str]]
    set_direct_mode_target: Callable[[int, Optional[str]], None]
    set_state_preserving_menu: Callable[..., None]
    direct_mode_handler: Callable[..., Awaitable[None]]
    netstatus_handler: Callable[..., Awaitable[None]]
    plan_handler: Callable[..., Awaitable[None]]
    usage_handler: Callable[..., Awaitable[None]]
    purchase_handler: Callable[..., Awaitable[None]]
    help_handler: Callable[..., Awaitable[None]]
    my_id_handler: Callable[..., Awaitable[None]]
    world_deps: Any
    show_rubika_menu_handler: Callable[..., Awaitable[None]]
    show_bale_menu_handler: Callable[..., Awaitable[None]]
    show_drive_menu_handler: Callable[..., Awaitable[None]]
    show_files_menu_handler: Callable[..., Awaitable[None]]
    show_link_direct_menu_handler: Callable[..., Awaitable[None]]
    admin_handler: Callable[..., Awaitable[None]]


_IMENU_ACTIONS = frozenset(
    {
        "dns",
        "ping",
        "ipinfo",
        "whois",
        "md5",
        "sha256",
        "b64e",
        "b64d",
    }
)

_STEP_BY_ACTION = {
    "dns": "await_toolkit_dns",
    "ping": "await_toolkit_ping",
    "ipinfo": "await_toolkit_ipinfo",
    "whois": "await_toolkit_whois",
    "md5": "await_toolkit_md5",
    "sha256": "await_toolkit_sha256",
    "b64e": "await_toolkit_b64e",
    "b64d": "await_toolkit_b64d",
}

_HINT_BY_ACTION = {
    "dns": "toolkit_dns_send_only",
    "ping": "toolkit_ping_send_only",
    "ipinfo": "toolkit_ipinfo_send_only",
    "whois": "toolkit_whois_send_only",
    "md5": "toolkit_md5_send_only",
    "sha256": "toolkit_sha256_send_only",
    "b64e": "toolkit_b64e_send_only",
    "b64d": "toolkit_b64d_send_only",
}


async def show_inline_menu(
    deps: InlineMenuDeps,
    client: Any,
    message: Any,
    user_id: int,
    key: str,
    *,
    edit: bool = False,
) -> None:
    resolved = inline_menus.resolve_inline_menu(
        key,
        user_id,
        deps.tr,
        is_admin=user_id in deps.admin_ids,
        webapp_url=deps.miniapp_base_url,
    )
    if not resolved:
        return
    body, kb = resolved
    if edit and hasattr(message, "edit_text"):
        try:
            await message.edit_text(body, reply_markup=kb, parse_mode=None)
        except MessageNotModified:
            pass
    else:
        await message.reply_text(body, reply_markup=kb, parse_mode=None)


async def dispatch_inline_menu_callback(
    deps: InlineMenuDeps,
    client: Any,
    callback_query: Any,
    key: str,
) -> bool:
    user_id = callback_query.from_user.id
    msg = callback_query.message
    k = (key or "").strip().lower()

    if k in _IMENU_ACTIONS:
        deps.set_state_preserving_menu(user_id, {"step": _STEP_BY_ACTION[k]})
        hint = deps.tr(user_id, _HINT_BY_ACTION.get(k, "text_unhandled_hint"))
        await callback_query.answer()
        try:
            await msg.edit_text(hint, reply_markup=None, parse_mode=None)
        except Exception:
            await msg.reply_text(hint, parse_mode=None)
        return True

    if k == "myid":
        await callback_query.answer()
        await deps.my_id_handler(client, msg)
        return True

    if k == "myip_hint":
        await callback_query.answer()
        await msg.edit_text(deps.tr(user_id, "miniapp_setup_hint"), parse_mode=None)
        return True

    if k == "weather":
        await callback_query.answer()
        await start_weather_wizard(deps.world_deps, msg)
        return True
    if k == "calendar":
        await callback_query.answer()
        await handle_calendar(deps.world_deps, client, msg)
        return True
    if k == "currency":
        await callback_query.answer()
        await start_currency_wizard(deps.world_deps, msg)
        return True
    if k == "quake":
        await callback_query.answer()
        await handle_earthquakes(deps.world_deps, client, msg)
        return True
    if k == "rss":
        await callback_query.answer()
        await start_rss_wizard(deps.world_deps, msg)
        return True
    if k == "rss_list":
        await callback_query.answer()
        await list_rss_feeds(deps.world_deps, msg)
        return True

    if k in ("dm_rubika", "dm_bale", "dm_drive"):
        await callback_query.answer()
        msg.text = f"/directmode {k[3:]} on"
        await deps.direct_mode_handler(client, msg)
        return True

    if k == "netstatus":
        await callback_query.answer()
        await deps.netstatus_handler(client, msg)
        return True
    if k == "plan_show":
        await callback_query.answer()
        await deps.plan_handler(client, msg)
        return True
    if k == "usage":
        await callback_query.answer()
        await deps.usage_handler(client, msg)
        return True
    if k == "purchase":
        await callback_query.answer()
        await deps.purchase_handler(client, msg)
        return True
    if k == "help":
        await callback_query.answer()
        await deps.help_handler(client, msg)
        return True

    if k == "rubika":
        await callback_query.answer()
        await deps.show_rubika_menu_handler(client, msg)
        return True
    if k == "bale":
        await callback_query.answer()
        await deps.show_bale_menu_handler(client, msg)
        return True
    if k == "drive":
        await callback_query.answer()
        await deps.show_drive_menu_handler(client, msg)
        return True
    if k == "files":
        await callback_query.answer()
        await deps.show_files_menu_handler(client, msg)
        return True
    if k == "link":
        await callback_query.answer()
        await deps.show_link_direct_menu_handler(client, msg)
        return True
    if k == "admin":
        if user_id not in deps.admin_ids:
            await callback_query.answer(deps.tr(user_id, "admin_denied"), show_alert=True)
            return True
        await callback_query.answer()
        await deps.admin_handler(client, msg)
        return True

    hub_keys = frozenset(
        {
            "main",
            "toolkit",
            "toolkit_net",
            "toolkit_crypto",
            "world",
            "transfer",
            "settings",
            "plan",
            "link",
        }
    )
    if k in hub_keys:
        if k != "main":
            maybe_disable_direct_mode(
                user_id, deps.get_direct_mode_target, deps.set_direct_mode_target
            )
        await callback_query.answer()
        await show_inline_menu(deps, client, msg, user_id, k, edit=True)
        return True

    return False
