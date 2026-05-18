"""Transfer hub menus: Rubika, Bale, Google Drive, SSH, files/queue (see docs/v2/05)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.transfer.bale_adapter import BaleTransferAdapter
from v2.transfer.drive_adapter import GoogleDriveTransferAdapter

TranslateFn = Callable[..., str]
MenuBuilder = Callable[[int], Any]


@dataclass(frozen=True)
class TransferHubDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    build_transfer_menu: MenuBuilder
    build_rubika_menu: MenuBuilder
    build_files_menu: MenuBuilder
    build_bale_menu: MenuBuilder
    build_drive_menu: MenuBuilder
    build_ssh_menu: MenuBuilder
    get_bale_chat_id: Callable[[int], Optional[str]]
    set_bale_chat_id: Callable[[int, str], None]
    list_ssh_servers: Callable[[int], list[dict]]
    ssh_add_server: Callable[[int, str, str, int, str], tuple[bool, str]]


def _bale_token_configured() -> bool:
    return bool((os.getenv("BALE_BOT_TOKEN") or "").strip())


def _drive_configured() -> bool:
    return bool(
        (os.getenv("GOOGLE_DRIVE_CLIENT_ID") or "").strip()
        and (os.getenv("GOOGLE_DRIVE_CLIENT_SECRET") or "").strip()
    )


async def handle_show_transfer_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.TRANSFER)
    await message.reply_text(
        deps.tr(uid, "transfer_menu_title"),
        reply_markup=deps.build_transfer_menu(uid),
    )


async def handle_show_rubika_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.RUBIKA)
    await message.reply_text(
        deps.tr(uid, "rubika_menu_title"),
        reply_markup=deps.build_rubika_menu(uid),
    )


async def handle_show_files_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.FILES)
    await message.reply_text(
        deps.tr(uid, "files_menu_title"),
        reply_markup=deps.build_files_menu(uid),
    )


async def handle_show_bale_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.BALE)
    await message.reply_text(
        deps.tr(uid, "bale_menu_title"),
        reply_markup=deps.build_bale_menu(uid),
    )


async def handle_bale_status(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.BALE)
    chat_id = deps.get_bale_chat_id(uid)
    ok, detail = BaleTransferAdapter().healthcheck()
    if not _bale_token_configured():
        await message.reply_text(deps.tr(uid, "bale_not_configured_server"), parse_mode=None)
        return
    if not chat_id:
        await message.reply_text(
            deps.tr(uid, "bale_status_no_chat", detail=detail if ok else detail),
            parse_mode=None,
        )
        return
    await message.reply_text(
        deps.tr(uid, "bale_status_ok", chat_id=chat_id, detail=detail),
        parse_mode=None,
    )


async def handle_bale_set_chat(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text(deps.tr(uid, "bale_set_chat_usage"), parse_mode=None)
        return
    deps.set_bale_chat_id(uid, parts[1].strip())
    await message.reply_text(deps.tr(uid, "bale_set_chat_saved", chat_id=parts[1].strip()), parse_mode=None)


async def handle_show_drive_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)
    await message.reply_text(
        deps.tr(uid, "drive_menu_title"),
        reply_markup=deps.build_drive_menu(uid),
    )


async def handle_drive_status(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)
    ok, detail = GoogleDriveTransferAdapter().healthcheck()
    if not _drive_configured():
        await message.reply_text(deps.tr(uid, "drive_not_configured"), parse_mode=None)
        return
    await message.reply_text(
        deps.tr(uid, "drive_status_line", ok="yes" if ok else "no", detail=detail),
        parse_mode=None,
    )


async def handle_show_ssh_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.SSH)
    await message.reply_text(
        deps.tr(uid, "ssh_menu_title"),
        reply_markup=deps.build_ssh_menu(uid),
    )


async def handle_ssh_list(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    rows = deps.list_ssh_servers(uid)
    if not rows:
        await message.reply_text(deps.tr(uid, "ssh_list_empty"), parse_mode=None)
        return
    lines = [deps.tr(uid, "ssh_list_title")]
    for r in rows:
        lines.append(
            deps.tr(
                uid,
                "ssh_list_row",
                id=r["id"],
                label=r["label"],
                host=r["host"],
                port=r["port"],
                user=r["ssh_user"],
            )
        )
    await message.reply_text("\n".join(lines), parse_mode=None)


async def handle_ssh_add(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split()
    if len(parts) < 5:
        await message.reply_text(deps.tr(uid, "ssh_add_usage"), parse_mode=None)
        return
    label, host, port_s, ssh_user = parts[1], parts[2], parts[3], parts[4]
    try:
        port = int(port_s)
    except ValueError:
        await message.reply_text(deps.tr(uid, "ssh_add_usage"), parse_mode=None)
        return
    ok, msg = deps.ssh_add_server(uid, label, host, port, ssh_user)
    if not ok:
        await message.reply_text(msg, parse_mode=None)
        return
    await message.reply_text(deps.tr(uid, "ssh_add_ok", label=label, host=host, port=port), parse_mode=None)
