"""Admin broadcast, stats, service status, and log helpers."""

from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, FrozenSet, Optional

from pyrogram.types import Message

from v2.core.admin_audience import admin_stats_blob, resolve_audience
from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]
LogEventFn = Callable[..., None]


@dataclass(frozen=True)
class AdminOpsDeps:
    admin_ids: FrozenSet[int]
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    build_admin_broadcast_menu: Callable[[int], Any]
    build_admin_menu: Callable[[int], Any]
    list_known_chat_ids: Callable[[], list[int]]
    list_activity_user_ids: Callable[[], list[int]]
    list_new_user_ids: Callable[[int], list[int]]
    list_inactive_user_ids: Callable[[int], list[int]]
    list_tier_user_ids: Callable[[str], list[int]]
    list_expiring_user_ids: Callable[[int], list[int]]
    list_expired_user_ids: Callable[[], list[int]]
    count_users: Callable[[], int]
    tier_counts: Callable[[], dict[str, int]]
    service_unit: str
    queue_dir: Path
    base_dir: Path
    log_event: LogEventFn
    get_job_summary: Callable[[str], str] | None = None


def _deny(deps: AdminOpsDeps, uid: int) -> bool:
    return uid not in deps.admin_ids


def _audience(deps: AdminOpsDeps, segment: str) -> tuple[list[int], str]:
    return resolve_audience(
        segment,
        list_known_chat_ids=deps.list_known_chat_ids,
        list_activity_user_ids=deps.list_activity_user_ids,
        list_new_user_ids=deps.list_new_user_ids,
        list_inactive_user_ids=deps.list_inactive_user_ids,
        list_tier_user_ids=deps.list_tier_user_ids,
        list_expiring_user_ids=deps.list_expiring_user_ids,
        list_expired_user_ids=deps.list_expired_user_ids,
    )


async def handle_admin_stats(deps: AdminOpsDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if _deny(deps, uid):
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    deps.set_menu_section(uid, MenuSection.ADMIN)
    blob = admin_stats_blob(
        count_users=deps.count_users,
        list_new_user_ids=deps.list_new_user_ids,
        list_inactive_user_ids=deps.list_inactive_user_ids,
        tier_counts=deps.tier_counts,
        list_known_chat_ids=deps.list_known_chat_ids,
        list_expiring_user_ids=deps.list_expiring_user_ids,
        list_expired_user_ids=deps.list_expired_user_ids,
    )
    await message.reply_text(
        deps.tr(uid, "admin_stats_body", **{k: blob[k] for k in blob if k != "ts"}),
        parse_mode=None,
    )


async def handle_show_admin_broadcast_menu(deps: AdminOpsDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if _deny(deps, uid):
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    deps.set_menu_section(uid, MenuSection.ADMIN)
    await message.reply_text(
        deps.tr(uid, "admin_broadcast_menu_title"),
        reply_markup=deps.build_admin_broadcast_menu(uid),
        parse_mode=None,
    )


async def start_broadcast_segment(deps: AdminOpsDeps, message: Message, segment: str) -> None:
    uid = message.from_user.id
    if _deny(deps, uid):
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    ids, label = _audience(deps, segment)
    deps.set_menu_section(uid, MenuSection.ADMIN)
    deps.set_state_preserving_menu(
        uid,
        {
            "step": "admin_broadcast_body",
            "admin_broadcast_segment": segment,
            "admin_broadcast_count": len(ids),
        },
    )
    await message.reply_text(
        deps.tr(
            uid,
            "admin_broadcast_ask_body",
            segment=segment,
            label=label,
            count=len(ids),
        ),
        parse_mode=None,
    )


async def dispatch_admin_ops_wizard(
    deps: AdminOpsDeps,
    client: Any,
    message: Message,
    user_id: int,
    state: dict,
    text: str,
) -> bool:
    if user_id not in deps.admin_ids:
        return False
    step = state.get("step")
    if step == "admin_broadcast_body":
        body = (text or "").strip()
        if not body or body.startswith("/"):
            await message.reply_text(deps.tr(user_id, "admin_broadcast_body_empty"), parse_mode=None)
            return True
        if body.lower() in ("cancel", "لغو", "/cancel"):
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "admin_broadcast_cancelled"), parse_mode=None)
            return True
        segment = str(state.get("admin_broadcast_segment") or "all")
        ids, _label = _audience(deps, segment)
        deps.set_state_preserving_menu(
            user_id,
            {
                "step": "admin_broadcast_confirm",
                "admin_broadcast_segment": segment,
                "admin_broadcast_body": body,
                "admin_broadcast_count": len(ids),
            },
        )
        preview = body if len(body) <= 400 else body[:397] + "…"
        await message.reply_text(
            deps.tr(
                user_id,
                "admin_broadcast_confirm",
                segment=segment,
                count=len(ids),
                preview=preview,
            ),
            parse_mode=None,
        )
        return True

    if step == "admin_broadcast_confirm":
        ans = (text or "").strip().lower()
        if ans in ("cancel", "لغو", "no", "n", "خیر", "/cancel"):
            deps.clear_state(user_id)
            await message.reply_text(deps.tr(user_id, "admin_broadcast_cancelled"), parse_mode=None)
            return True
        if ans not in ("yes", "y", "بله", "ok", "ارسال", "send"):
            await message.reply_text(deps.tr(user_id, "admin_broadcast_confirm_hint"), parse_mode=None)
            return True
        segment = str(state.get("admin_broadcast_segment") or "all")
        body = str(state.get("admin_broadcast_body") or "").strip()
        ids, _label = _audience(deps, segment)
        deps.clear_state(user_id)
        if not body or not ids:
            await message.reply_text(deps.tr(user_id, "admin_broadcast_empty"), parse_mode=None)
            return True
        sent = 0
        failed = 0
        status = await message.reply_text(
            deps.tr(user_id, "admin_broadcast_sending", total=len(ids)),
            parse_mode=None,
        )
        for i, chat_id in enumerate(ids, start=1):
            try:
                await client.send_message(chat_id, body, parse_mode=None)
                sent += 1
            except Exception:
                failed += 1
            if i % 20 == 0:
                await asyncio.sleep(0.35)
                try:
                    await status.edit_text(
                        deps.tr(
                            user_id,
                            "admin_broadcast_progress",
                            done=i,
                            total=len(ids),
                            sent=sent,
                            failed=failed,
                        ),
                        parse_mode=None,
                    )
                except Exception:
                    pass
            else:
                await asyncio.sleep(0.05)
        deps.log_event(
            "admin_broadcast_done",
            admin_id=user_id,
            segment=segment,
            sent=sent,
            failed=failed,
            total=len(ids),
        )
        await message.reply_text(
            deps.tr(
                user_id,
                "admin_broadcast_done",
                sent=sent,
                failed=failed,
                total=len(ids),
                segment=segment,
            ),
            reply_markup=deps.build_admin_menu(user_id),
            parse_mode=None,
        )
        return True

    if step == "admin_job_lookup":
        job_id = (text or "").strip()
        deps.clear_state(user_id)
        if not job_id:
            await message.reply_text(deps.tr(user_id, "admin_job_ask"), parse_mode=None)
            return True
        summary = ""
        if deps.get_job_summary:
            try:
                summary = deps.get_job_summary(job_id) or ""
            except Exception as e:
                summary = f"error: {e}"
        await message.reply_text(
            summary or deps.tr(user_id, "admin_job_not_found", job_id=job_id),
            parse_mode=None,
        )
        return True

    return False


def service_status_text(unit: str = "tele2rub") -> str:
    lines: list[str] = []
    try:
        active = subprocess.check_output(
            ["systemctl", "is-active", unit],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=5,
        ).strip()
    except Exception as e:
        active = f"n/a ({e})"
    lines.append(f"unit: {unit}")
    lines.append(f"active: {active}")
    try:
        show = subprocess.check_output(
            [
                "systemctl",
                "show",
                unit,
                "-p",
                "MainPID",
                "-p",
                "ActiveEnterTimestamp",
                "-p",
                "NRestarts",
                "--no-pager",
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=5,
        ).strip()
        lines.append(show)
    except Exception:
        pass
    try:
        since = subprocess.check_output(
            ["systemctl", "show", "-p", "ActiveEnterTimestamp", "--value", unit],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if since and since not in ("n/a", "0"):
            j = subprocess.check_output(
                ["journalctl", "-u", unit, "--since", since, "-n", "25", "--no-pager"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=8,
            )
            lines.append("--- journal ---")
            lines.append(j[-3500:])
    except Exception as e:
        lines.append(f"journal: {e}")
    return "\n".join(lines)[:3900]


def recent_logs_text(queue_dir: Path, *, lines: int = 40) -> str:
    parts: list[str] = []
    for name in ("bot_events.jsonl", "worker_events.jsonl"):
        path = queue_dir / name
        if not path.is_file():
            parts.append(f"[{name}] missing")
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = raw[-max(1, min(200, lines)) :]
            parts.append(f"[{name}] last {len(tail)} lines")
            parts.append("\n".join(tail)[-1800:])
        except Exception as e:
            parts.append(f"[{name}] {e}")
    return "\n\n".join(parts)[:3900]


async def handle_admin_service_status(deps: AdminOpsDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if _deny(deps, uid):
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    text = await asyncio.to_thread(service_status_text, deps.service_unit)
    await message.reply_text(
        deps.tr(uid, "admin_service_status_body", detail=text),
        parse_mode=None,
    )


async def handle_admin_tail_logs(deps: AdminOpsDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if _deny(deps, uid):
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    text = await asyncio.to_thread(recent_logs_text, deps.queue_dir, lines=30)
    await message.reply_text(
        deps.tr(uid, "admin_tail_logs_body", detail=text),
        parse_mode=None,
    )


async def handle_admin_job_help(deps: AdminOpsDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if _deny(deps, uid):
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    deps.set_state_preserving_menu(uid, {"step": "admin_job_lookup"})
    await message.reply_text(deps.tr(uid, "admin_job_ask"), parse_mode=None)
