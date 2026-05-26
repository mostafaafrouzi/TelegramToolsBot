"""Media message pipeline extracted from telebot."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.handlers.media_dest_handler import MediaDestHandlerDeps, prompt_media_destination
from v2.transfer.bale_client import BALE_MAX_BYTES
from v2.transfer.user_credentials import load_bale_credentials, load_drive_credentials

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class MediaHandlerDeps:
    tr: TranslateFn
    base_dir: Path
    queue: Any
    get_user_session: Callable[[int], Optional[str]]
    get_menu_section: Callable[[int], Optional[str]]
    get_direct_mode_target: Callable[[int], Optional[str]]
    get_bale_credentials: Callable[[int], tuple[Optional[str], Optional[str]]]
    get_state: Callable[[int], dict]
    set_state_preserving_menu: Callable[..., None]
    save_drive_sa_file: Callable[[int, Path], Any]
    get_ssh_server: Callable[[int, int], Optional[dict]]
    get_media: Callable[[Message], tuple[str, Any]]
    build_download_filename: Callable[[Message, str, Any], str]
    download_dir: Path
    download_progress: Callable[..., Any]
    effective_max_file_bytes: Callable[[int], Optional[int]]
    effective_max_mb_display: Callable[[int], str]
    fmt_mb_bytes: Callable[[int], str]
    load_settings: Callable[[], dict]
    get_batch: Callable[[int], dict]
    set_batch: Callable[[int, dict], None]
    pretty_size: Callable[[int], str]
    queue_or_confirm: Callable[..., Any]
    push_task_direct: Callable[[Message, dict], Any]
    log_event: Callable[..., None]


async def handle_media_message(deps: MediaHandlerDeps, client: Any, message: Message) -> None:
    user_id = message.from_user.id
    state = deps.get_state(user_id)
    section = (deps.get_menu_section(user_id) or MenuSection.MAIN.value).strip().lower()

    if section == MenuSection.LINK_DIRECT.value:
        await message.reply_text(deps.tr(user_id, "link_media_hint"), parse_mode=None)
        return

    if section == MenuSection.CLOUDFLARE.value:
        if state.get("step") == "await_cloudflare_token":
            await message.reply_text(deps.tr(user_id, "cf_ask_token"), parse_mode=None)
            return
        await message.reply_text(deps.tr(user_id, "cf_media_hint"), parse_mode=None)
        return

    if state.get("step") == "await_drive_sa_json":
        if not message.document:
            await message.reply_text(deps.tr(user_id, "drive_sa_need_document"), parse_mode=None)
            return
        fname = (message.document.file_name or "sa.json").lower()
        if not fname.endswith(".json"):
            await message.reply_text(deps.tr(user_id, "drive_sa_need_json"), parse_mode=None)
            return
        tmp = deps.download_dir / f"drive_sa_upload_{user_id}_{int(time.time())}.json"
        try:
            downloaded = await client.download_media(message, file_name=str(tmp))
            if not downloaded:
                raise RuntimeError("download failed")
            ok, err = await deps.save_drive_sa_file(user_id, Path(downloaded))
            if not ok:
                await message.reply_text(
                    deps.tr(user_id, "drive_sa_invalid", error=err),
                    parse_mode=None,
                )
                return
            deps.set_state_preserving_menu(user_id, {"step": "await_drive_folder_id"})
            await message.reply_text(deps.tr(user_id, "drive_ask_folder_id"), parse_mode=None)
        except Exception as e:
            await message.reply_text(deps.tr(user_id, "media_error", error=str(e)), parse_mode=None)
        return

    # SSH put: after /ssh_put <id> <remote_path>, next file is uploaded.
    if state.get("step") == "await_ssh_put_file":
        server_id = int(state.get("ssh_server_id") or 0)
        remote_path = str(state.get("ssh_remote_path") or "")
        srv = deps.get_ssh_server(user_id, server_id)
        if not srv:
            await message.reply_text(deps.tr(user_id, "ssh_server_not_found"), parse_mode=None)
            return
        if not srv.get("ssh_secret") and not srv.get("ssh_key_path"):
            await message.reply_text(deps.tr(user_id, "ssh_auth_missing"), parse_mode=None)
            return
        await _download_and_queue(
            client,
            message,
            user_id,
            deps=deps,
            task_type="ssh_put",
            extra={
                "ssh_server": {
                    "host": srv["host"],
                    "port": srv["port"],
                    "ssh_user": srv["ssh_user"],
                    "ssh_secret": srv.get("ssh_secret"),
                    "ssh_key_path": srv.get("ssh_key_path"),
                },
                "remote_path": remote_path,
            },
            require_rubika=False,
            batch_allowed=False,
        )
        return

    task_type = "local_file"
    require_rubika = True
    extra: dict = {}

    direct_target = (deps.get_direct_mode_target(user_id) or "").strip().lower()
    if direct_target in ("bale", "drive", "rubika"):
        section = direct_target

    if section == MenuSection.BALE.value or section == "bale":
        task_type = "transfer_to_bale"
        require_rubika = False
        bale = load_bale_credentials(deps.queue, user_id)
        if not bale.ready:
            await message.reply_text(deps.tr(user_id, "bale_not_connected"), parse_mode=None)
            return
        extra["bale_chat_id"] = bale.chat_id
        extra["bale_bot_token"] = bale.bot_token
    elif section == MenuSection.DRIVE.value or section == "drive":
        task_type = "transfer_to_drive"
        require_rubika = False
        drive = load_drive_credentials(deps.queue, deps.base_dir, user_id)
        if not drive.ready:
            await message.reply_text(deps.tr(user_id, "drive_not_connected"), parse_mode=None)
            return
        extra["drive_sa_path"] = str(drive.service_account_path)
        extra["drive_folder_id"] = drive.folder_id

    session_name = deps.get_user_session(user_id) if require_rubika else None
    if require_rubika and not session_name:
        await message.reply_text(deps.tr(user_id, "media_need_rubika"), parse_mode=None)
        return

    async def _queue_after_dest_pick(client, message, user_id, **kwargs):
        await _download_and_queue(client, message, user_id, deps=deps, **kwargs)

    mdest = MediaDestHandlerDeps(
        tr=deps.tr,
        base_dir=deps.base_dir,
        queue=deps.queue,
        get_user_session=deps.get_user_session,
        get_direct_mode_target=deps.get_direct_mode_target,
        get_menu_section=deps.get_menu_section,
        download_and_queue_media=_queue_after_dest_pick,
    )
    if await prompt_media_destination(mdest, message, user_id):
        return

    await _download_and_queue(
        client,
        message,
        user_id,
        deps=deps,
        task_type=task_type,
        extra=extra,
        require_rubika=require_rubika,
        session_name=session_name,
        batch_allowed=require_rubika and task_type == "local_file",
    )


async def _download_and_queue(
    client: Any,
    message: Message,
    user_id: int,
    *,
    deps: MediaHandlerDeps,
    task_type: str,
    extra: dict,
    require_rubika: bool,
    session_name: Optional[str] = None,
    batch_allowed: bool = True,
    status_message: Optional[Message] = None,
) -> None:
    media_type, media = deps.get_media(message)
    if not media:
        await message.reply_text(deps.tr(user_id, "media_bad_type"), parse_mode=None)
        return

    download_name = deps.build_download_filename(message, media_type, media)
    download_path = deps.download_dir / download_name
    status = status_message
    if not status:
        status = await message.reply_text(deps.tr(user_id, "media_download_status"), parse_mode=None)

    try:
        started_at = time.time()
        progress_state = {"last_update": 0, "user_id": user_id}

        downloaded = await client.download_media(
            message,
            file_name=str(download_path),
            progress=deps.download_progress,
            progress_args=(status, download_name, started_at, progress_state),
        )
        if not downloaded:
            raise RuntimeError("Download failed.")

        downloaded_path = Path(downloaded)
        if not downloaded_path.exists():
            raise RuntimeError("Downloaded file not found.")

        file_size = downloaded_path.stat().st_size
        lim_b = deps.effective_max_file_bytes(user_id)
        if lim_b is not None and file_size > lim_b:
            try:
                downloaded_path.unlink()
            except Exception:
                pass
            await status.edit_text(
                deps.tr(
                    user_id,
                    "file_too_large",
                    max_mb=deps.effective_max_mb_display(user_id),
                    size_mb=deps.fmt_mb_bytes(file_size),
                ),
                parse_mode=None,
            )
            return
        if task_type == "transfer_to_bale" and file_size > BALE_MAX_BYTES:
            try:
                downloaded_path.unlink()
            except Exception:
                pass
            await status.edit_text(
                deps.tr(
                    user_id,
                    "bale_file_too_large",
                    max_mb=BALE_MAX_BYTES // (1024 * 1024),
                    size_mb=deps.fmt_mb_bytes(file_size),
                ),
                parse_mode=None,
            )
            return

        settings = deps.load_settings()
        batch = deps.get_batch(user_id)
        if batch_allowed and batch.get("active"):
            files = batch.get("files", [])
            files.append(str(downloaded_path))
            batch["files"] = files
            deps.set_batch(user_id, batch)
            raw_tot = 0
            for pstr in files:
                try:
                    pp = Path(pstr)
                    if pp.exists():
                        raw_tot += pp.stat().st_size
                except OSError:
                    pass
            await status.edit_text(
                deps.tr(
                    user_id,
                    "media_zip_added",
                    n=len(files),
                    raw_mb=deps.fmt_mb_bytes(raw_tot),
                ),
                parse_mode=None,
            )
            return

        task = {
            "type": task_type,
            "path": str(downloaded_path),
            "caption": message.caption or "",
            "file_name": download_name,
            "file_size": file_size,
            "safe_mode": settings.get("safe_mode", False),
            "zip_password": settings.get("zip_password", ""),
            "telegram_user_id": user_id,
            "chat_id": message.chat.id,
            **extra,
        }
        if session_name:
            task["rubika_session"] = session_name

        await status.edit_text(
            deps.tr(
                user_id,
                "media_file_ready",
                name=download_name,
                size=deps.pretty_size(file_size),
            ),
            parse_mode=None,
        )

        if task_type == "local_file":
            summary = deps.tr(user_id, "file_prepared_summary", name=download_name)
            queued_or_pending = await deps.queue_or_confirm(message, task, summary, status_message=status)
            if queued_or_pending is False:
                try:
                    downloaded_path.unlink()
                except Exception:
                    pass
        else:
            queued = await deps.push_task_direct(message, task, status_message=status)
            if queued is False:
                try:
                    downloaded_path.unlink()
                except Exception:
                    pass

        deps.log_event(
            "media_prepared",
            user_id=user_id,
            file_name=download_name,
            file_size=file_size,
            task_type=task_type,
        )

    except Exception as e:
        deps.log_event("media_prepare_failed", user_id=user_id, error=str(e))
        await status.edit_text(deps.tr(user_id, "media_error", error=str(e)), parse_mode=None)
