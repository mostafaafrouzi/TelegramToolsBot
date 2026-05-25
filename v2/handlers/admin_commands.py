"""Admin panel and maintenance slash commands (extracted from telebot)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, FrozenSet

from pyrogram.types import Message

from v2.billing.status import ALL_STATUSES, PAID
from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]
LogEventFn = Callable[..., None]


@dataclass(frozen=True)
class AdminCommandDeps:
    admin_ids: FrozenSet[int]
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    build_admin_menu: Callable[[int], Any]
    load_network_snapshot: Callable[[], dict]
    queue_count: Callable[[], int]
    queue_cancelled_count: Callable[[], int]
    queue_deleted_count: Callable[[], int]
    failed_count: Callable[[], int]
    max_file_mb_display: Callable[[], str]
    admin_disk_report_text: Callable[[], str]
    set_user_tier: Callable[[int, str, int], None]
    add_bonus_month_mb: Callable[[int, int], None]
    run_admin_cleanup_downloads: Callable[[], tuple[int, int]]
    list_v2_payments_for_user: Callable[[int, int], list[dict]]
    get_v2_payment_by_id: Callable[[int], dict | None]
    update_v2_payment_status: Callable[[int, str, str | None], None]
    maybe_grant_after_paid: Callable[[int], bool]
    run_billing_reconcile: Callable[[], dict]
    log_event: LogEventFn


async def dispatch_admin_wizard(
    deps: AdminCommandDeps,
    message: Message,
    user_id: int,
    state: dict,
    text: str,
) -> bool:
    if user_id not in deps.admin_ids:
        return False
    step = state.get("step")
    if not step or not str(step).startswith("admin_"):
        return False

    if step == "admin_tier_user":
        try:
            target = int(text.strip())
        except ValueError:
            await message.reply_text(deps.tr(user_id, "admin_wizard_need_user_id"), parse_mode=None)
            return True
        state = {"step": "admin_tier_tier", "admin_target_user_id": target}
        deps.set_menu_section(user_id, MenuSection.ADMIN)
        # Reuse the persistent state helper exposed by telebot through monkey patch below.
        message._admin_next_state = state  # type: ignore[attr-defined]
        await message.reply_text(deps.tr(user_id, "admin_wizard_tier_ask"), parse_mode=None)
        return True

    if step == "admin_tier_tier":
        tier = text.strip().lower()
        if tier not in ("guest", "free", "pro"):
            await message.reply_text(deps.tr(user_id, "admin_wizard_tier_ask"), parse_mode=None)
            return True
        target = int(state.get("admin_target_user_id") or 0)
        if tier == "pro":
            message._admin_next_state = {  # type: ignore[attr-defined]
                "step": "admin_tier_days",
                "admin_target_user_id": target,
                "admin_target_tier": tier,
            }
            await message.reply_text(deps.tr(user_id, "admin_wizard_days_ask"), parse_mode=None)
            return True
        deps.set_user_tier(target, tier, 0)
        message._admin_clear_state = True  # type: ignore[attr-defined]
        deps.log_event("admin_tier_wizard_ok", admin_id=user_id, target=target, tier=tier)
        await message.reply_text(deps.tr(user_id, "admin_wizard_tier_done", target=target, tier=tier), parse_mode=None)
        return True

    if step == "admin_tier_days":
        target = int(state.get("admin_target_user_id") or 0)
        tier = str(state.get("admin_target_tier") or "pro")
        try:
            days = max(1, int(text.strip()))
        except ValueError:
            await message.reply_text(deps.tr(user_id, "admin_wizard_days_ask"), parse_mode=None)
            return True
        exp = int(time.time()) + days * 86400
        deps.set_user_tier(target, tier, exp)
        message._admin_clear_state = True  # type: ignore[attr-defined]
        deps.log_event("admin_tier_wizard_ok", admin_id=user_id, target=target, tier=tier, days=days)
        await message.reply_text(deps.tr(user_id, "admin_wizard_tier_done", target=target, tier=tier), parse_mode=None)
        return True

    if step == "admin_bonus_user":
        try:
            target = int(text.strip())
        except ValueError:
            await message.reply_text(deps.tr(user_id, "admin_wizard_need_user_id"), parse_mode=None)
            return True
        message._admin_next_state = {"step": "admin_bonus_mb", "admin_target_user_id": target}  # type: ignore[attr-defined]
        await message.reply_text(deps.tr(user_id, "admin_wizard_bonus_ask"), parse_mode=None)
        return True

    if step == "admin_bonus_mb":
        target = int(state.get("admin_target_user_id") or 0)
        try:
            mb = int(text.strip())
        except ValueError:
            await message.reply_text(deps.tr(user_id, "admin_wizard_bonus_ask"), parse_mode=None)
            return True
        deps.add_bonus_month_mb(target, mb)
        message._admin_clear_state = True  # type: ignore[attr-defined]
        deps.log_event("admin_bonus_wizard_ok", admin_id=user_id, target=target, mb=mb)
        await message.reply_text(deps.tr(user_id, "admin_wizard_bonus_done", target=target, mb=mb), parse_mode=None)
        return True

    return False


async def handle_admin_panel(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    deps.set_menu_section(uid, MenuSection.ADMIN)
    net = deps.load_network_snapshot()
    await message.reply_text(
        deps.tr(
            uid,
            "admin_panel",
            qt=deps.queue_count(),
            cancelled=deps.queue_cancelled_count(),
            deleted=deps.queue_deleted_count(),
            failed=deps.failed_count(),
            net_mode=net.get("mode", "unknown"),
            net_reason=net.get("reason", "") or "---",
        )
        + "\n"
        + deps.tr(uid, "admin_max_file", mb=deps.max_file_mb_display())
        + "\n"
        + deps.tr(uid, "admin_plan_note")
        + "\n"
        + deps.tr(uid, "admin_clear_prefs_hint")
        + "\n"
        + deps.tr(uid, "admin_clear_state_mirrors_hint")
        + "\n"
        + deps.tr(uid, "admin_payment_lookup_hint")
        + "\n"
        + deps.tr(uid, "admin_payment_status_hint")
        + "\n"
        + deps.tr(uid, "admin_reconcile_billing_hint")
        + "\n\n"
        + deps.tr(uid, "rubika_update_hint")
        + "\n\n"
        + deps.admin_disk_report_text(),
        reply_markup=deps.build_admin_menu(uid),
        parse_mode=None,
    )


async def handle_admin_tier(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.reply_text(
            "Usage: `/admin_tier <telegram_user_id> <guest|free|pro> [days_valid_for_pro]`",
            parse_mode=None,
        )
        return
    try:
        target = int(parts[1].strip())
    except ValueError:
        await message.reply_text("Invalid user id.", parse_mode=None)
        return
    tier = parts[2].strip().lower()
    exp = 0
    if len(parts) >= 4:
        try:
            days = int(parts[3].strip())
            if tier == "pro" and days > 0:
                exp = int(time.time()) + days * 86400
        except ValueError:
            pass
    deps.set_user_tier(target, tier, exp)
    await message.reply_text(
        f"OK: user `{target}` tier=`{tier}` expires_at=`{exp}`",
        parse_mode=None,
    )


async def handle_admin_bonus(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.reply_text(
            "Usage: `/admin_bonus <telegram_user_id> <extra_month_mb>`",
            parse_mode=None,
        )
        return
    try:
        target = int(parts[1].strip())
        mb = int(parts[2].strip())
    except ValueError:
        await message.reply_text("Invalid numbers.", parse_mode=None)
        return
    deps.add_bonus_month_mb(target, mb)
    await message.reply_text(f"OK: +{mb} MB monthly bonus for user `{target}`", parse_mode=None)


async def handle_cleanup_downloads(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    n, freed = deps.run_admin_cleanup_downloads()
    deps.log_event("admin_cleanup_downloads", user_id=uid, files=n, bytes_freed=freed)
    await message.reply_text(
        deps.tr(uid, "cleanup_done", n=n, mb=f"{freed / (1024 * 1024):.2f}"),
        parse_mode=None,
    )


def _format_v2_payment_rows(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        lines.append(
            f"`{r.get('id')}` `{r.get('gateway','')}` {r.get('amount')} {r.get('currency','')} "
            f"`{r.get('status','')}` auth={r.get('authority') or '—'} ref={r.get('ref_id') or '—'} "
            f"t={r.get('created_at')}"
        )
    return "\n".join(lines)


async def handle_admin_payment_lookup(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply_text(
            "Usage: `/admin_payment_lookup <telegram_user_id> [limit]`",
            parse_mode=None,
        )
        return
    try:
        target = int(parts[1].strip())
    except ValueError:
        await message.reply_text("Invalid user id.", parse_mode=None)
        return
    lim = 15
    if len(parts) >= 3:
        try:
            lim = int(parts[2].strip())
        except ValueError:
            lim = 15
    lim = max(1, min(lim, 30))
    rows = deps.list_v2_payments_for_user(target, lim)
    if not rows:
        await message.reply_text(deps.tr(uid, "admin_payment_lookup_empty"), parse_mode=None)
        return
    body = deps.tr(uid, "admin_payment_lookup_title") + _format_v2_payment_rows(rows)
    await message.reply_text(body, parse_mode=None)


async def handle_admin_payment_status(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.reply_text(
            "Usage: `/admin_payment_status <payment_id> <status> [ref_id]`\n"
            f"status ∈ {{{', '.join(sorted(ALL_STATUSES))}}}",
            parse_mode=None,
        )
        return
    try:
        payment_id = int(parts[1].strip())
    except ValueError:
        await message.reply_text("Invalid payment id.", parse_mode=None)
        return
    status = parts[2].strip().lower()
    if status not in ALL_STATUSES:
        await message.reply_text(
            f"Invalid status. Use one of: {', '.join(sorted(ALL_STATUSES))}",
            parse_mode=None,
        )
        return
    ref_id: str | None = None
    if len(parts) >= 4:
        ref_id = parts[3].strip() or None
    row = deps.get_v2_payment_by_id(payment_id)
    if not row:
        await message.reply_text(f"No payment row for id `{payment_id}`.", parse_mode=None)
        return
    try:
        deps.update_v2_payment_status(payment_id, status, ref_id)
    except Exception as e:
        deps.log_event("admin_payment_status_failed", admin_id=uid, payment_id=payment_id, error=str(e))
        await message.reply_text(f"DB error: {e}", parse_mode=None)
        return
    deps.log_event(
        "admin_payment_status_ok",
        admin_id=uid,
        payment_id=payment_id,
        status=status,
        ref_id=ref_id or "",
    )
    granted = False
    if status == PAID:
        granted = bool(deps.maybe_grant_after_paid(payment_id))
    suffix = f" (+grant)" if granted else ""
    await message.reply_text(
        f"OK: payment `{payment_id}` → `{status}`"
        + (f" ref=`{ref_id}`" if ref_id else "")
        + suffix,
        parse_mode=None,
    )


async def handle_admin_reconcile_billing(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    try:
        stats = deps.run_billing_reconcile()
    except Exception as e:
        deps.log_event("admin_reconcile_billing_failed", admin_id=uid, error=str(e))
        await message.reply_text(f"Error: {e}", parse_mode=None)
        return
    deps.log_event("admin_reconcile_billing_ok", admin_id=uid, **stats)
    await message.reply_text(
        deps.tr(
            uid,
            "admin_reconcile_billing_result",
            expired=stats.get("expired", 0),
            scanned=stats.get("scanned", 0),
        ),
        parse_mode=None,
    )


def _format_timestamp(ts: int) -> str:
    from datetime import datetime, timezone
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


async def handle_admin_users_list(deps: AdminCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    if uid not in deps.admin_ids:
        await message.reply_text(deps.tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    page = 0
    if len(parts) >= 2:
        try:
            page = max(0, int(parts[1]) - 1)
        except ValueError:
            pass
    per_page = 15
    total = deps.count_users()
    users = deps.list_users(per_page, page * per_page)
    if not users:
        await message.reply_text(deps.tr(uid, "admin_users_list_empty"), parse_mode=None)
        return
    lines = [f"👥 کاربران ربات ({total} نفر) — صفحه {page + 1}\n"]
    for u in users:
        name = u.get("first_name") or "—"
        uname = f"@{u['username']}" if u.get("username") else ""
        last = _format_timestamp(u.get("last_seen_at", 0))
        lines.append(f"`{u['telegram_user_id']}` {name} {uname} — آخرین: {last}")
    kb_rows = []
    for u in users:
        name = u.get("first_name") or str(u["telegram_user_id"])
        kb_rows.append([InlineKeyboardButton(
            f"👤 {name} ({u['telegram_user_id']})",
            callback_data=f"adminuser:{u['telegram_user_id']}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"adminuserpage:{page}"))
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"adminuserpage:{page + 2}"))
    if nav:
        kb_rows.append(nav)
    await message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(kb_rows),
        parse_mode=None,
    )


async def handle_admin_user_detail_callback(
    deps: AdminCommandDeps, client: Any, callback_query: Any, target_user_id: int
) -> bool:
    uid = callback_query.from_user.id
    if uid not in deps.admin_ids:
        await callback_query.answer(deps.tr(uid, "admin_denied"), show_alert=True)
        return True
    info = deps.get_user_info(target_user_id)
    usage = deps.get_usage_snapshot(target_user_id)
    name = (info or {}).get("first_name", "—")
    uname = f"@{info['username']}" if info and info.get("username") else ""
    first = _format_timestamp((info or {}).get("first_seen_at", 0))
    last = _format_timestamp((info or {}).get("last_seen_at", 0))
    tier = usage.get("tier", "guest")
    month_used = usage.get("month_used_mb", 0)
    month_limit = usage.get("month_limit_mb", 0)
    text = (
        f"👤 {name} {uname}\n"
        f"ID: `{target_user_id}`\n"
        f"پلن: `{tier}`\n"
        f"مصرف ماهانه: `{month_used:.1f}` / `{month_limit}` MB\n"
        f"اولین ورود: {first}\n"
        f"آخرین فعالیت: {last}"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⬆️ ارتقای پلن", callback_data=f"adminusertier:{target_user_id}"),
            InlineKeyboardButton(f"➕ افزودن حجم", callback_data=f"adminuserbonus:{target_user_id}"),
        ],
        [InlineKeyboardButton(f"💳 پرداخت‌ها", callback_data=f"adminuserpay:{target_user_id}")],
    ])
    await callback_query.answer()
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode=None)
    except Exception:
        await callback_query.message.reply_text(text, reply_markup=kb, parse_mode=None)
    return True
