"""Dispatch reply-keyboard pseudo-routes produced by menu_engine.resolve_reply_button_route."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, FrozenSet, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection

ClientRef = Any
MessageHandler = Callable[[ClientRef, Message], Awaitable[None]]
TranslateFn = Callable[[int, str], str]
MenuBuilder = Callable[[int], Any]


@dataclass(frozen=True)
class ReplyRouteDeps:
    admin_ids: FrozenSet[int]
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    menu_handler: MessageHandler
    help_handler: MessageHandler
    log_help_handler: MessageHandler
    rubika_connect_handler: MessageHandler
    rubika_status_handler: MessageHandler
    bale_status_handler: MessageHandler
    bale_connect_handler: MessageHandler
    bale_disconnect_handler: MessageHandler
    bale_set_chat_handler: MessageHandler
    drive_status_handler: MessageHandler
    drive_connect_handler: MessageHandler
    drive_disconnect_handler: MessageHandler
    ssh_list_handler: MessageHandler
    new_batch_handler: MessageHandler
    done_batch_handler: MessageHandler
    clear_queue_handler: MessageHandler
    queue_manage_handler: MessageHandler
    netstatus_handler: MessageHandler
    admin_handler: MessageHandler
    direct_mode_handler: MessageHandler
    plan_handler: MessageHandler
    usage_handler: MessageHandler
    purchase_handler: MessageHandler
    show_transfer_menu_handler: MessageHandler
    show_toolkit_menu_handler: MessageHandler
    show_toolkit_network_menu_handler: MessageHandler
    show_toolkit_crypto_menu_handler: MessageHandler
    show_rubika_menu_handler: MessageHandler
    show_bale_menu_handler: MessageHandler
    show_drive_menu_handler: MessageHandler
    show_ssh_menu_handler: MessageHandler
    show_files_menu_handler: MessageHandler
    show_link_direct_menu_handler: MessageHandler
    dns_lookup_handler: MessageHandler
    my_ip_handler: MessageHandler
    tcp_ping_handler: MessageHandler
    md5_handler: MessageHandler
    sha256_handler: MessageHandler
    b64_encode_handler: MessageHandler
    b64_decode_handler: MessageHandler
    build_plan_menu: MenuBuilder
    build_transfer_menu: MenuBuilder
    build_toolkit_menu: MenuBuilder
    build_rubika_menu: MenuBuilder
    build_files_menu: MenuBuilder
    build_settings_menu: MenuBuilder
    build_admin_menu: MenuBuilder


async def _run_slash(handler: MessageHandler, client: ClientRef, message: Message, command: str) -> None:
    message.text = command
    await handler(client, message)


async def dispatch_reply_keyboard_route(
    client: ClientRef,
    message: Message,
    user_id: int,
    mapped: Optional[str],
    deps: ReplyRouteDeps,
) -> bool:
    """Run handler for mapped reply route. Returns True if consumed."""
    if not mapped:
        return False
    tr = deps.tr

    if mapped == "/menu":
        await deps.menu_handler(client, message)
        return True
    if mapped == "/help":
        await deps.help_handler(client, message)
        return True
    if mapped == "/loghelp":
        await deps.log_help_handler(client, message)
        return True

    if mapped == "/show_plan_menu":
        deps.set_menu_section(user_id, MenuSection.PLAN)
        await message.reply_text(
            tr(user_id, "plan_menu_opened"),
            reply_markup=deps.build_plan_menu(user_id),
        )
        return True
    if mapped == "/show_transfer_menu":
        await deps.show_transfer_menu_handler(client, message)
        return True
    if mapped == "/show_toolkit_menu":
        await deps.show_toolkit_menu_handler(client, message)
        return True
    if mapped == "/show_toolkit_network_menu":
        await deps.show_toolkit_network_menu_handler(client, message)
        return True
    if mapped == "/show_toolkit_crypto_menu":
        await deps.show_toolkit_crypto_menu_handler(client, message)
        return True
    if mapped == "/show_rubika_menu":
        await deps.show_rubika_menu_handler(client, message)
        return True
    if mapped == "/show_bale_menu":
        await deps.show_bale_menu_handler(client, message)
        return True
    if mapped == "/show_drive_menu":
        await deps.show_drive_menu_handler(client, message)
        return True
    if mapped == "/show_ssh_menu":
        await deps.show_ssh_menu_handler(client, message)
        return True
    if mapped == "/show_files_menu":
        await deps.show_files_menu_handler(client, message)
        return True
    if mapped == "/show_link_direct_menu":
        await deps.show_link_direct_menu_handler(client, message)
        return True
    if mapped == "/show_settings_menu":
        deps.set_menu_section(user_id, MenuSection.SETTINGS)
        await message.reply_text(
            tr(user_id, "settings_menu_title"),
            reply_markup=deps.build_settings_menu(user_id),
        )
        return True
    if mapped == "/show_admin_menu":
        if user_id in deps.admin_ids:
            deps.set_menu_section(user_id, MenuSection.ADMIN)
            await message.reply_text(
                tr(user_id, "admin_menu_title"),
                reply_markup=deps.build_admin_menu(user_id),
            )
        else:
            await message.reply_text(tr(user_id, "admin_denied"))
        return True

    if mapped == "/plan":
        await _run_slash(deps.plan_handler, client, message, "/plan")
        return True
    if mapped == "/usage":
        await _run_slash(deps.usage_handler, client, message, "/usage")
        return True
    if mapped == "/purchase":
        await _run_slash(deps.purchase_handler, client, message, "/purchase")
        return True

    if mapped == "/rubika_connect":
        await deps.rubika_connect_handler(client, message)
        return True
    if mapped == "/rubika_status":
        await deps.rubika_status_handler(client, message)
        return True
    if mapped == "/bale_status":
        await deps.bale_status_handler(client, message)
        return True
    if mapped == "/bale_connect":
        await deps.bale_connect_handler(client, message)
        return True
    if mapped == "/bale_disconnect":
        await deps.bale_disconnect_handler(client, message)
        return True
    if mapped == "/bale_set_chat":
        await deps.bale_set_chat_handler(client, message)
        return True
    if mapped == "/drive_status":
        await deps.drive_status_handler(client, message)
        return True
    if mapped == "/drive_connect":
        await deps.drive_connect_handler(client, message)
        return True
    if mapped == "/drive_disconnect":
        await deps.drive_disconnect_handler(client, message)
        return True
    if mapped == "/drive_download_help":
        await message.reply_text(tr(user_id, "drive_download_usage"), parse_mode=None)
        return True
    if mapped == "/ssh_list":
        await deps.ssh_list_handler(client, message)
        return True
    if mapped == "/ssh_add_help":
        await message.reply_text(tr(user_id, "ssh_add_usage"), parse_mode=None)
        return True
    if mapped == "/ssh_put_help":
        await message.reply_text(tr(user_id, "ssh_put_usage"), parse_mode=None)
        return True
    if mapped == "/ssh_get_help":
        await message.reply_text(tr(user_id, "ssh_get_usage"), parse_mode=None)
        return True

    if mapped == "/dns":
        await _run_slash(deps.dns_lookup_handler, client, message, "/dns")
        return True
    if mapped == "/myip":
        await _run_slash(deps.my_ip_handler, client, message, "/myip")
        return True
    if mapped == "/ping":
        await _run_slash(deps.tcp_ping_handler, client, message, "/ping")
        return True
    if mapped == "/md5":
        await _run_slash(deps.md5_handler, client, message, "/md5")
        return True
    if mapped == "/sha256":
        await _run_slash(deps.sha256_handler, client, message, "/sha256")
        return True
    if mapped == "/b64e":
        await _run_slash(deps.b64_encode_handler, client, message, "/b64e")
        return True
    if mapped == "/b64d":
        await _run_slash(deps.b64_decode_handler, client, message, "/b64d")
        return True

    if mapped == "/newbatch":
        await deps.new_batch_handler(client, message)
        return True
    if mapped == "/done":
        await deps.done_batch_handler(client, message)
        return True
    if mapped == "/delall":
        await deps.clear_queue_handler(client, message)
        return True
    if mapped == "/queue":
        await deps.queue_manage_handler(client, message)
        return True
    if mapped == "/netstatus":
        await deps.netstatus_handler(client, message)
        return True
    if mapped == "/admin":
        await deps.admin_handler(client, message)
        return True
    for dm_cmd in (
        "/directmode on",
        "/directmode off",
        "/directmode rubika on",
        "/directmode rubika off",
        "/directmode bale on",
        "/directmode bale off",
        "/directmode drive on",
        "/directmode drive off",
    ):
        if mapped == dm_cmd:
            await _run_slash(deps.direct_mode_handler, client, message, dm_cmd)
            return True
    if mapped == "/quick_send_prompt":
        deps.set_state_preserving_menu(user_id, {"step": "await_quick_message"})
        await message.reply_text(tr(user_id, "prompt_quick_message"))
        return True
    return False
