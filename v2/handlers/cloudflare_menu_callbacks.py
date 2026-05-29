"""Inline Cloudflare menu actions (cfmenu:*)."""

from __future__ import annotations

from typing import Any

from v2.handlers.cloudflare_commands import (
    CloudflareCommandDeps,
    handle_cf_disconnect,
    handle_cf_dns,
    handle_cf_status,
    handle_cf_zones,
)


async def dispatch_cf_menu_callback(
    deps: CloudflareCommandDeps,
    client: Any,
    callback_query: Any,
    action: str,
) -> bool:
    msg = callback_query.message
    if not msg:
        return False
    uid = callback_query.from_user.id

    if action == "status":
        await callback_query.answer()
        await handle_cf_status(deps, client, msg)
        return True
    if action == "zones":
        await callback_query.answer()
        await handle_cf_zones(deps, client, msg)
        return True
    if action == "dns_hint":
        await callback_query.answer()
        await msg.reply_text(deps.tr(uid, "cf_dns_usage"), parse_mode=None)
        return True
    if action == "disconnect":
        await callback_query.answer()
        await handle_cf_disconnect(deps, client, msg)
        return True
    return False
