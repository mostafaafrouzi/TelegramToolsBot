"""Link/video direct-download section: probe → pick destination → verify → download → queue."""

from __future__ import annotations

import asyncio
import time
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


def _quality_keyboard(user_id: int, tr: TranslateFn) -> InlineKeyboardMarkup:
    """Inline quality picker for YouTube (best / 1080p / 720p / 480p / audio-only)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(user_id, "link_quality_best"), callback_data="linkquality:best"),
                InlineKeyboardButton(tr(user_id, "link_quality_1080"), callback_data="linkquality:1080"),
            ],
            [
                InlineKeyboardButton(tr(user_id, "link_quality_720"), callback_data="linkquality:720"),
                InlineKeyboardButton(tr(user_id, "link_quality_480"), callback_data="linkquality:480"),
            ],
            [InlineKeyboardButton(tr(user_id, "link_quality_audio_only"), callback_data="linkquality:audio")],
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


#
# Pending user selections (between probe -> quality pick -> destination pick).
#
_pending_link_meta: dict[int, LinkMetadata] = {}
_pending_link_quality: dict[int, str] = {}
_pending_link_audio_only: dict[int, bool] = {}


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
            "drive_sa_path": str(drive.service_account_path) if drive.service_account_path else "",
            "drive_oauth_path": str(drive.oauth_token_path) if drive.oauth_token_path else "",
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
    if dest == "bale" and file_size > BALE_MAX_BYTES:
        try:
            local_path.unlink()
        except OSError:
            pass
        await message.reply_text(
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
        queued_or_pending = await deps.queue_or_confirm(message, task, summary, status_message=status)
        if queued_or_pending is False:
            try:
                local_path.unlink()
            except OSError:
                pass
    elif dest == "bale":
        task["type"] = "transfer_to_bale"
        if not await deps.gate_quota(message, user_id, task):
            try:
                local_path.unlink()
            except OSError:
                pass
            return
        status = await message.reply_text(deps.tr(user_id, "link_download_done_queue"), parse_mode=None)
        queued = await deps.push_task_direct(message, task, status_message=status)
        if queued is False:
            try:
                local_path.unlink()
            except OSError:
                pass
    else:
        task["type"] = "transfer_to_drive"
        if not await deps.gate_quota(message, user_id, task):
            try:
                local_path.unlink()
            except OSError:
                pass
            return
        status = await message.reply_text(deps.tr(user_id, "link_download_done_queue"), parse_mode=None)
        queued = await deps.push_task_direct(message, task, status_message=status)
        if queued is False:
            try:
                local_path.unlink()
            except OSError:
                pass

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
        if meta.link_type == "youtube":
            await status.edit_text(
                f"{summary}\n\n{deps.tr(user_id, 'link_pick_quality')}",
                reply_markup=_quality_keyboard(user_id, deps.tr),
                parse_mode=None,
            )
        else:
            await status.edit_text(
                f"{summary}\n\n{deps.tr(user_id, 'link_pick_dest')}",
                reply_markup=_dest_keyboard(user_id, deps.tr),
                parse_mode=None,
            )
    except MessageNotModified:
        pass

    # Stash URL metadata in reply_to message id — callback uses inline data only (url in callback too long).
    # Store pending in a module-level cache keyed by user_id (simple; cleared on pick/cancel).
    _pending_link_meta[user_id] = meta
    return True


async def handle_link_quality_callback(
    deps: LinkDirectHandlerDeps,
    client: Any,
    callback_query: Any,
    quality: str,
) -> bool:
    user_id = callback_query.from_user.id
    anchor = callback_query.message

    # Quality selection doesn't depend on meta existence (dest callback will validate meta).
    q = (quality or "").strip().lower()
    if q in ("audio", "audio_only", "onlyaudio"):
        _pending_link_quality[user_id] = "best"
        _pending_link_audio_only[user_id] = True
        reply_text = deps.tr(user_id, "link_quality_audio_set")
    else:
        _pending_link_audio_only[user_id] = False
        if not q or q == "best":
            _pending_link_quality[user_id] = "best"
            reply_text = deps.tr(user_id, "link_quality_best_set")
        else:
            # e.g. "1080", "720", "480"
            _pending_link_quality[user_id] = q
            reply_text = deps.tr(user_id, "link_quality_set", quality=q)

    await callback_query.answer()
    if not anchor:
        return True

    try:
        await anchor.edit_text(
            reply_text,
            reply_markup=_dest_keyboard(user_id, deps.tr),
            parse_mode=None,
        )
    except MessageNotModified:
        pass
    return True


async def handle_link_dest_callback(
    deps: LinkDirectHandlerDeps,
    client: Any,
    callback_query: Any,
    dest: str,
) -> bool:
    user_id = callback_query.from_user.id
    meta = _pending_link_meta.pop(user_id, None)
    if not meta:
        await callback_query.answer(deps.tr(user_id, "link_session_expired"), show_alert=True)
        return True

    if dest == "cancel":
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

    quality = _pending_link_quality.pop(user_id, "best")
    audio_only = _pending_link_audio_only.pop(user_id, False)

    try:
        loop = asyncio.get_running_loop()
        last_update_ts = 0.0

        def _progress_cb(m: str) -> None:
            nonlocal last_update_ts
            now = time.time()
            # throttle edits (and avoid chatty updates while ytdlp downloads)
            if now - last_update_ts < 2.0:
                return
            last_update_ts = now

            # schedule async edit on the event loop (thread-safe)
            try:
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(_progress(m))
                )
            except Exception:
                pass

        local_path = await asyncio.to_thread(
            download_to_path,
            meta.url,
            deps.download_dir,
            metadata=meta,
            progress_cb=_progress_cb,
            quality=quality,
            audio_only=audio_only,
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
