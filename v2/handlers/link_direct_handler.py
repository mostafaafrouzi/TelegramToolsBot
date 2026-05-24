"""Link/video direct-download section: probe → pick destination → verify → download → queue."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.core.menu_sections import MenuSection
from v2.transfer.bale_client import BALE_MAX_BYTES
from v2.transfer.link_direct import LinkMetadata, download_to_path, probe_metadata
from v2.transfer.user_credentials import load_bale_credentials, load_drive_credentials

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class LinkDirectHandlerDeps:
    tr: TranslateFn
    base_dir: Path
    download_dir: Path
    queue: Any
    extract_first_url: Callable[[str], Optional[str]]
    get_menu_section: Callable[[int], Optional[str]]
    get_state: Callable[[int], dict]
    set_state_preserving_menu: Callable[..., None]
    get_user_session: Callable[[int], Optional[str]]
    load_settings: Callable[[], dict]
    effective_max_file_bytes: Callable[[int], Optional[int]]
    effective_max_mb_display: Callable[[int], str]
    fmt_mb_bytes: Callable[[int], str]
    pretty_size: Callable[[int], str]
    gate_quota: Callable[..., Any]
    queue_or_confirm: Callable[..., Any]
    push_task_direct: Callable[..., Any]
    log_event: Callable[..., None]


def _forget_pending_meta(deps: LinkDirectHandlerDeps, user_id: int) -> None:
    _pending_link_meta.pop(user_id, None)
    try:
        deps.set_state_preserving_menu(user_id, {})
    except Exception:
        pass


def _remember_pending_meta(deps: LinkDirectHandlerDeps, user_id: int, meta: LinkMetadata) -> None:
    _pending_link_meta[user_id] = meta
    try:
        deps.set_state_preserving_menu(user_id, {"pending_link_meta": asdict(meta)})
    except Exception:
        pass


def _pending_meta(deps: LinkDirectHandlerDeps, user_id: int) -> Optional[LinkMetadata]:
    meta = _pending_link_meta.get(user_id)
    if meta:
        return meta
    raw = deps.get_state(user_id).get("pending_link_meta")
    if not isinstance(raw, dict):
        return None
    try:
        return LinkMetadata(**raw)
    except TypeError:
        return None


async def _reply_bale_limit(deps: LinkDirectHandlerDeps, message: Message, user_id: int, file_size: int) -> None:
    await message.reply_text(
        deps.tr(
            user_id,
            "bale_file_too_large",
            max_mb=BALE_MAX_BYTES // (1024 * 1024),
            size_mb=deps.fmt_mb_bytes(file_size),
        ),
        parse_mode=None,
    )


def _dest_keyboard(user_id: int, tr: TranslateFn) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "link_dest_rubika"), callback_data="linkdest:rubika"),
                InlineKeyboardButton(tr(user_id, "link_dest_bale"), callback_data="linkdest:bale"),
            ],
            [InlineKeyboardButton(tr(user_id, "link_dest_drive"), callback_data="linkdest:drive")],
            [InlineKeyboardButton(tr(user_id, "link_dest_cancel"), callback_data="linkdest:cancel")],
        ]
    )


_LINK_TYPE_KEYS = {
    "direct": "link_type_direct",
    "youtube": "link_type_youtube",
    "magnet": "link_type_magnet",
}


def _format_probe_summary(deps: LinkDirectHandlerDeps, user_id: int, meta: LinkMetadata) -> str:
    size_txt = deps.pretty_size(meta.size_bytes) if meta.size_bytes else deps.tr(user_id, "link_size_unknown")
    type_txt = deps.tr(user_id, _LINK_TYPE_KEYS.get(meta.link_type, "link_type_direct"))
    return deps.tr(
        user_id,
        "link_probe_summary",
        title=meta.title or "—",
        link_type=type_txt,
        size=size_txt,
    )


def verify_destination(
    dest: str,
    user_id: int,
    deps: LinkDirectHandlerDeps,
) -> tuple[bool, str, dict]:
    """Return (ok, error_i18n_key_or_empty, task_extra)."""
    if dest == "rubika":
        session = deps.get_user_session(user_id)
        if not session:
            return False, "link_need_rubika", {}
        return True, "", {"rubika_session": session}
    if dest == "bale":
        bale = load_bale_credentials(deps.queue, user_id)
        if not bale.ready:
            return False, "bale_not_connected", {}
        return True, "", {"bale_chat_id": bale.chat_id, "bale_bot_token": bale.bot_token}
    if dest == "drive":
        drive = load_drive_credentials(deps.queue, deps.base_dir, user_id)
        if not drive.ready:
            return False, "drive_not_connected", {}
        return True, "", {
            "drive_sa_path": str(drive.service_account_path),
            "drive_folder_id": drive.folder_id,
        }
    return False, "link_dest_invalid", {}


async def enqueue_downloaded_file(
    deps: LinkDirectHandlerDeps,
    message: Message,
    user_id: int,
    *,
    dest: str,
    local_path: Path,
    meta: LinkMetadata,
    extra: dict,
) -> None:
    file_size = local_path.stat().st_size
    if dest == "bale" and file_size > BALE_MAX_BYTES:
        try:
            local_path.unlink()
        except OSError:
            pass
        await _reply_bale_limit(deps, message, user_id, file_size)
        return

    lim = deps.effective_max_file_bytes(user_id)
    if lim is not None and file_size > lim:
        try:
            local_path.unlink()
        except OSError:
            pass
        await message.reply_text(
            deps.tr(
                user_id,
                "file_too_large",
                max_mb=deps.effective_max_mb_display(user_id),
                size_mb=deps.fmt_mb_bytes(file_size),
            ),
            parse_mode=None,
        )
        return

    settings = deps.load_settings()
    task: dict = {
        "path": str(local_path),
        "caption": "",
        "file_name": local_path.name,
        "file_size": file_size,
        "safe_mode": settings.get("safe_mode", False),
        "zip_password": settings.get("zip_password", ""),
        "telegram_user_id": user_id,
        "chat_id": message.chat.id,
        "source_url": meta.url,
        **extra,
    }

    if dest == "rubika":
        task["type"] = "local_file"
        summary = deps.tr(user_id, "file_prepared_summary", name=local_path.name)
        if not await deps.gate_quota(message, user_id, task):
            try:
                local_path.unlink()
            except OSError:
                pass
            return
        status = await message.reply_text(deps.tr(user_id, "link_download_done_queue"), parse_mode=None)
        await deps.queue_or_confirm(message, task, summary, status_message=status)
    elif dest == "bale":
        task["type"] = "transfer_to_bale"
        if not await deps.gate_quota(message, user_id, task):
            try:
                local_path.unlink()
            except OSError:
                pass
            return
        status = await message.reply_text(deps.tr(user_id, "link_download_done_queue"), parse_mode=None)
        await deps.push_task_direct(message, task, status_message=status)
    else:
        task["type"] = "transfer_to_drive"
        if not await deps.gate_quota(message, user_id, task):
            try:
                local_path.unlink()
            except OSError:
                pass
            return
        status = await message.reply_text(deps.tr(user_id, "link_download_done_queue"), parse_mode=None)
        await deps.push_task_direct(message, task, status_message=status)

    deps.log_event(
        "link_direct_queued",
        user_id=user_id,
        dest=dest,
        file_name=local_path.name,
        file_size=file_size,
        url=meta.url,
    )


async def handle_link_direct_text(
    deps: LinkDirectHandlerDeps,
    client: Any,
    message: Message,
    user_id: int,
    text: str,
) -> bool:
    """Handle URL in link_direct menu section. Returns True if consumed."""
    section = (deps.get_menu_section(user_id) or "").strip().lower()
    if section != MenuSection.LINK_DIRECT.value:
        return False

    url = deps.extract_first_url(text)
    if not url:
        await message.reply_text(deps.tr(user_id, "link_send_url"), parse_mode=None)
        return True

    status = await message.reply_text(deps.tr(user_id, "link_probing"), parse_mode=None)
    meta = await asyncio.to_thread(probe_metadata, url)

    if not meta.downloadable:
        key = "link_probe_unsupported"
        if meta.detail == "yt_dlp_not_installed":
            key = "link_ytdlp_missing"
        elif meta.link_type == "magnet":
            key = "link_magnet_unsupported"
        await status.edit_text(deps.tr(user_id, key, detail=meta.detail), parse_mode=None)
        return True

    summary = _format_probe_summary(deps, user_id, meta)
    try:
        await status.edit_text(
            f"{summary}\n\n{deps.tr(user_id, 'link_pick_dest')}",
            reply_markup=_dest_keyboard(user_id, deps.tr),
            parse_mode=None,
        )
    except MessageNotModified:
        pass

    # Callback data cannot safely carry long URLs; persist enough metadata for restart recovery.
    _remember_pending_meta(deps, user_id, meta)
    return True


async def handle_link_dest_callback(
    deps: LinkDirectHandlerDeps,
    client: Any,
    callback_query: Any,
    dest: str,
) -> bool:
    user_id = callback_query.from_user.id
    meta = _pending_meta(deps, user_id)
    if not meta:
        await callback_query.answer(deps.tr(user_id, "link_session_expired"), show_alert=True)
        return True

    if dest == "cancel":
        _forget_pending_meta(deps, user_id)
        await callback_query.answer()
        try:
            await callback_query.message.edit_text(deps.tr(user_id, "link_cancelled"), reply_markup=None)
        except Exception:
            pass
        return True

    ok, err_key, extra = verify_destination(dest, user_id, deps)
    if not ok:
        await callback_query.answer(deps.tr(user_id, err_key), show_alert=True)
        return True

    if dest == "bale" and meta.size_bytes and meta.size_bytes > BALE_MAX_BYTES:
        await callback_query.answer(
            deps.tr(
                user_id,
                "bale_file_too_large",
                max_mb=BALE_MAX_BYTES // (1024 * 1024),
                size_mb=deps.fmt_mb_bytes(int(meta.size_bytes)),
            ),
            show_alert=True,
        )
        return True

    _forget_pending_meta(deps, user_id)
    await callback_query.answer()
    anchor = callback_query.message
    try:
        await anchor.edit_text(deps.tr(user_id, "link_downloading"), reply_markup=None, parse_mode=None)
    except Exception:
        pass

    async def _progress(msg: str) -> None:
        try:
            await anchor.edit_text(deps.tr(user_id, "link_downloading") + f"\n{msg}", parse_mode=None)
        except Exception:
            pass

    try:
        local_path = await asyncio.to_thread(
            download_to_path,
            meta.url,
            deps.download_dir,
            metadata=meta,
            progress_cb=lambda m: None,  # sync thread — skip live edits to avoid asyncio issues
        )
    except Exception as e:
        deps.log_event("link_direct_download_failed", user_id=user_id, error=str(e))
        try:
            await anchor.edit_text(deps.tr(user_id, "link_download_failed", error=str(e)), parse_mode=None)
        except Exception:
            await callback_query.message.reply_text(
                deps.tr(user_id, "link_download_failed", error=str(e)),
                parse_mode=None,
            )
        return True

    await enqueue_downloaded_file(deps, anchor, user_id, dest=dest, local_path=local_path, meta=meta, extra=extra)
    return True


# Per-user pending metadata between probe and destination pick (cleared on use).
_pending_link_meta: dict[int, LinkMetadata] = {}


async def handle_link_direct_for_direct_mode(
    deps: LinkDirectHandlerDeps,
    message: Message,
    user_id: int,
    url: str,
    dest: str,
) -> bool:
    """Direct-send mode: verify dest, download, queue — no inline picker."""
    ok, err_key, extra = verify_destination(dest, user_id, deps)
    if not ok:
        await message.reply_text(deps.tr(user_id, err_key), parse_mode=None)
        return True

    status = await message.reply_text(deps.tr(user_id, "link_probing"), parse_mode=None)
    meta = await asyncio.to_thread(probe_metadata, url)
    if not meta.downloadable:
        await status.edit_text(deps.tr(user_id, "link_probe_unsupported", detail=meta.detail), parse_mode=None)
        return True

    if dest == "bale" and meta.size_bytes and meta.size_bytes > BALE_MAX_BYTES:
        await status.edit_text(
            deps.tr(
                user_id,
                "bale_file_too_large",
                max_mb=BALE_MAX_BYTES // (1024 * 1024),
                size_mb=deps.fmt_mb_bytes(int(meta.size_bytes)),
            ),
            parse_mode=None,
        )
        return True

    try:
        await status.edit_text(deps.tr(user_id, "link_downloading"), parse_mode=None)
    except MessageNotModified:
        pass

    try:
        local_path = await asyncio.to_thread(
            download_to_path,
            meta.url,
            deps.download_dir,
            metadata=meta,
        )
    except Exception as e:
        await status.edit_text(deps.tr(user_id, "link_download_failed", error=str(e)), parse_mode=None)
        return True

    await enqueue_downloaded_file(deps, message, user_id, dest=dest, local_path=local_path, meta=meta, extra=extra)
    try:
        await status.delete()
    except Exception:
        pass
    return True
