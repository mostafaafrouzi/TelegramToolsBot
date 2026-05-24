"""Transfer hub menus: Rubika, Bale, Google Drive, SSH, files/queue (see docs/v2/05)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.transfer.bale_adapter import BaleTransferAdapter
from v2.transfer.bale_client import validate_chat
from v2.transfer.drive_adapter import GoogleDriveTransferAdapter
from v2.transfer.drive_client import list_files as drive_list_files
from v2.transfer.ssh_client import sftp_list
from v2.transfer.user_credentials import load_bale_credentials, load_drive_credentials

TranslateFn = Callable[..., str]
MenuBuilder = Callable[[int], Any]


@dataclass(frozen=True)
class TransferHubDeps:
    tr: TranslateFn
    base_dir: Path
    queue: Any
    set_menu_section: Callable[[int, MenuSection], None]
    build_transfer_menu: MenuBuilder
    build_rubika_menu: MenuBuilder
    build_files_menu: MenuBuilder
    build_bale_menu: MenuBuilder
    build_drive_menu: MenuBuilder
    build_ssh_menu: MenuBuilder
    get_bale_credentials: Callable[[int], tuple[Optional[str], Optional[str]]]
    set_bale_chat_id: Callable[[int, str], None]
    list_ssh_servers: Callable[[int], list[dict]]
    get_ssh_server: Callable[[int, int], Optional[dict]]
    ssh_add_server: Callable[..., tuple[bool, str]]
    ssh_delete_server: Callable[[int, int], bool]


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
        deps.tr(uid, "bale_menu_title") + "\n\n" + deps.tr(uid, "bale_active_hint"),
        reply_markup=deps.build_bale_menu(uid),
    )


async def handle_bale_status(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.BALE)
    creds = load_bale_credentials(deps.queue, uid)
    if not creds.bot_token:
        await message.reply_text(deps.tr(uid, "bale_not_connected"), parse_mode=None)
        return
    ok, detail = BaleTransferAdapter().healthcheck(creds.bot_token)
    chat_detail = ""
    if creds.chat_id:
        chat_ok, chat_msg = validate_chat(creds.bot_token, creds.chat_id)
        chat_detail = f" chat={'ok' if chat_ok else 'bad'}:{chat_msg}"
    if not creds.chat_id:
        await message.reply_text(
            deps.tr(uid, "bale_status_no_chat", detail=detail if ok else detail),
            parse_mode=None,
        )
        return
    await message.reply_text(
        deps.tr(uid, "bale_status_ok", chat_id=creds.chat_id, detail=f"{detail}{chat_detail}"),
        parse_mode=None,
    )


async def handle_bale_set_chat(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    token, _chat = deps.get_bale_credentials(uid)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text(deps.tr(uid, "bale_set_chat_usage"), parse_mode=None)
        return
    if not token:
        await message.reply_text(deps.tr(uid, "bale_not_connected"), parse_mode=None)
        return
    chat_id = parts[1].strip()
    ok, detail = validate_chat(token, chat_id)
    if not ok:
        await message.reply_text(deps.tr(uid, "bale_chat_invalid", detail=detail), parse_mode=None)
        return
    deps.set_bale_chat_id(uid, chat_id)
    await message.reply_text(deps.tr(uid, "bale_set_chat_saved", chat_id=chat_id) + f"\n{detail}", parse_mode=None)


async def handle_show_drive_menu(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)
    await message.reply_text(
        deps.tr(uid, "drive_menu_title") + "\n\n" + deps.tr(uid, "drive_active_hint"),
        reply_markup=deps.build_drive_menu(uid),
    )


async def handle_drive_status(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)
    dc = load_drive_credentials(deps.queue, deps.base_dir, uid)
    if not dc.ready:
        await message.reply_text(deps.tr(uid, "drive_not_connected"), parse_mode=None)
        return
    ok, detail = GoogleDriveTransferAdapter().healthcheck(
        service_account_path=str(dc.service_account_path),
        folder_id=dc.folder_id,
    )


async def handle_drive_ls(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)
    dc = load_drive_credentials(deps.queue, deps.base_dir, uid)
    if not dc.ready:
        await message.reply_text(deps.tr(uid, "drive_not_connected"), parse_mode=None)
        return
    parts = (message.text or "").split(maxsplit=1)
    folder_id = parts[1].strip() if len(parts) > 1 and parts[1].strip() else dc.folder_id
    ok, detail = drive_list_files(
        service_account_path=str(dc.service_account_path),
        folder_id=folder_id,
    )
    await message.reply_text(
        deps.tr(uid, "drive_ls_result", detail=detail) if ok else deps.tr(uid, "drive_ls_error", error=detail),
        parse_mode=None,
    )
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
    parts = (message.text or "").split(maxsplit=5)
    if len(parts) < 5:
        await message.reply_text(deps.tr(uid, "ssh_add_usage"), parse_mode=None)
        return
    label, host, port_s, ssh_user = parts[1], parts[2], parts[3], parts[4]
    ssh_secret = parts[5] if len(parts) >= 6 else ""
    try:
        port = int(port_s)
    except ValueError:
        await message.reply_text(deps.tr(uid, "ssh_add_usage"), parse_mode=None)
        return
    ok, msg = deps.ssh_add_server(uid, label, host, port, ssh_user, ssh_secret=ssh_secret)
    if not ok:
        await message.reply_text(msg, parse_mode=None)
        return
    await message.reply_text(deps.tr(uid, "ssh_add_ok", label=label, host=host, port=port), parse_mode=None)


async def handle_ssh_del(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(deps.tr(uid, "ssh_del_usage"), parse_mode=None)
        return
    try:
        server_id = int(parts[1].strip())
    except ValueError:
        await message.reply_text(deps.tr(uid, "ssh_del_usage"), parse_mode=None)
        return
    if not deps.ssh_delete_server(uid, server_id):
        await message.reply_text(deps.tr(uid, "ssh_server_not_found"), parse_mode=None)
        return
    await message.reply_text(deps.tr(uid, "ssh_del_ok", id=server_id), parse_mode=None)


async def handle_ssh_ls(deps: TransferHubDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.reply_text(deps.tr(uid, "ssh_ls_usage"), parse_mode=None)
        return
    try:
        server_id = int(parts[1])
    except ValueError:
        await message.reply_text(deps.tr(uid, "ssh_ls_usage"), parse_mode=None)
        return
    remote_path = parts[2].strip() if len(parts) >= 3 else "."
    srv = deps.get_ssh_server(uid, server_id)
    if not srv:
        await message.reply_text(deps.tr(uid, "ssh_server_not_found"), parse_mode=None)
        return
    if not srv.get("ssh_secret") and not srv.get("ssh_key_path"):
        await message.reply_text(deps.tr(uid, "ssh_auth_missing"), parse_mode=None)
        return
    ok, detail = sftp_list(
        srv.get("host", ""),
        int(srv.get("port") or 22),
        srv.get("ssh_user", ""),
        remote_path,
        password=srv.get("ssh_secret"),
        key_filename=srv.get("ssh_key_path"),
    )
    await message.reply_text(
        deps.tr(uid, "ssh_ls_result", path=remote_path, detail=detail)
        if ok
        else deps.tr(uid, "ssh_ls_error", error=detail),
        parse_mode=None,
    )


async def handle_ssh_put_command(
    deps: TransferHubDeps,
    client: Any,
    message: Message,
    *,
    set_state_preserving_menu: Callable[..., None],
) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text(deps.tr(uid, "ssh_put_usage"), parse_mode=None)
        return
    try:
        server_id = int(parts[1])
    except ValueError:
        await message.reply_text(deps.tr(uid, "ssh_put_usage"), parse_mode=None)
        return
    remote_path = parts[2].strip()
    if not deps.get_ssh_server(uid, server_id):
        await message.reply_text(deps.tr(uid, "ssh_server_not_found"), parse_mode=None)
        return
    set_state_preserving_menu(
        uid,
        {"step": "await_ssh_put_file", "ssh_server_id": server_id, "ssh_remote_path": remote_path},
    )
    await message.reply_text(deps.tr(uid, "ssh_put_await_file"), parse_mode=None)


async def handle_drive_download_command(
    deps: TransferHubDeps,
    client: Any,
    message: Message,
    *,
    push_task_direct: Callable[..., Any],
) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text(deps.tr(uid, "drive_download_usage"), parse_mode=None)
        return
    dc = load_drive_credentials(deps.queue, deps.base_dir, uid)
    if not dc.ready:
        await message.reply_text(deps.tr(uid, "drive_not_connected"), parse_mode=None)
        return
    file_id = parts[1].strip()
    task = {
        "type": "drive_download",
        "drive_file_id": file_id,
        "telegram_user_id": uid,
        "chat_id": message.chat.id,
        "drive_sa_path": str(dc.service_account_path),
    }
    await push_task_direct(message, task)


async def handle_ssh_get_command(
    deps: TransferHubDeps,
    client: Any,
    message: Message,
    *,
    push_task_direct: Callable[..., Any],
) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text(deps.tr(uid, "ssh_get_usage"), parse_mode=None)
        return
    try:
        server_id = int(parts[1])
    except ValueError:
        await message.reply_text(deps.tr(uid, "ssh_get_usage"), parse_mode=None)
        return
    srv = deps.get_ssh_server(uid, server_id)
    if not srv:
        await message.reply_text(deps.tr(uid, "ssh_server_not_found"), parse_mode=None)
        return
    if not srv.get("ssh_secret") and not srv.get("ssh_key_path"):
        await message.reply_text(deps.tr(uid, "ssh_auth_missing"), parse_mode=None)
        return
    task = {
        "type": "ssh_get",
        "remote_path": parts[2].strip(),
        "telegram_user_id": uid,
        "chat_id": message.chat.id,
        "ssh_server": {
            "host": srv["host"],
            "port": srv["port"],
            "ssh_user": srv["ssh_user"],
            "ssh_secret": srv.get("ssh_secret"),
            "ssh_key_path": srv.get("ssh_key_path"),
        },
    }
    await push_task_direct(message, task)
