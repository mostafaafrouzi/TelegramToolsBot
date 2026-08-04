"""Multi-step wizard for paid alert subscriptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.alerts import store
from v2.core.menu_sections import MenuSection
from v2.core.msg_format import reply_plain
from v2.core.upgrade_cta import buy_pro_keyboard

TranslateFn = Callable[..., str]
IsPaidFn = Callable[[int], bool]


@dataclass(frozen=True)
class AlertCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    get_state: Callable[[int], dict]
    is_paid_user: IsPaidFn


async def start_alert_wizard(deps: AlertCommandDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.WORLD)
    if not deps.is_paid_user(uid):
        await reply_plain(
            message,
            deps.tr(uid, "alerts_paid_only"),
            reply_markup=buy_pro_keyboard(uid, deps.tr),
        )
        return
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💵 ارز", callback_data="alertkind:fx"),
                InlineKeyboardButton("🥇 طلا", callback_data="alertkind:gold"),
            ],
            [
                InlineKeyboardButton("🌤 آب‌وهوا", callback_data="alertkind:weather"),
                InlineKeyboardButton("🌍 زلزله", callback_data="alertkind:quake"),
            ],
            [InlineKeyboardButton("📋 لیست هشدارها", callback_data="alertkind:list")],
        ]
    )
    await reply_plain(message, deps.tr(uid, "alerts_pick_kind"), reply_markup=kb)


async def handle_alert_kind_callback(
    deps: AlertCommandDeps, client: Any, callback_query: Any, kind: str
) -> bool:
    uid = callback_query.from_user.id
    await callback_query.answer()
    if not deps.is_paid_user(uid):
        await reply_plain(
            callback_query.message,
            deps.tr(uid, "alerts_paid_only"),
            reply_markup=buy_pro_keyboard(uid, deps.tr),
        )
        return True
    if kind == "list":
        rows = store.list_alerts(uid)
        if not rows:
            await reply_plain(callback_query.message, deps.tr(uid, "alerts_empty"))
            return True
        lines = [deps.tr(uid, "alerts_list_title")]
        for r in rows:
            lines.append(
                f"#{r['id']} · {r['kind']} · {r['asset'] or '-'} · {r['schedule']}"
                + (f" · spike≥{r['spike_pct']}%" if r.get("spike_pct") is not None else "")
            )
        await reply_plain(callback_query.message, "\n".join(lines))
        return True
    deps.set_state_preserving_menu(
        uid, {"step": "await_alert_asset", "alert_kind": kind}
    )
    if kind == "quake":
        # For quake: skip free-text city; ask Richter filter via buttons
        deps.set_state_preserving_menu(
            uid,
            {
                "step": "await_alert_schedule",
                "alert_kind": "quake",
                "alert_asset": "",
            },
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ساعتی", callback_data="alertsch:hourly"),
                    InlineKeyboardButton("روزانه", callback_data="alertsch:daily"),
                    InlineKeyboardButton("هفتگی", callback_data="alertsch:weekly"),
                ]
            ]
        )
        await reply_plain(
            callback_query.message, deps.tr(uid, "alerts_ask_schedule"), reply_markup=kb
        )
        return True
    hint = {
        "fx": "alerts_ask_fx_asset",
        "gold": "alerts_ask_gold_asset",
        "weather": "alerts_ask_weather_city",
        "quake": "alerts_ask_quake_city",
    }.get(kind, "alerts_ask_fx_asset")
    await reply_plain(callback_query.message, deps.tr(uid, hint))
    return True


async def dispatch_alert_wizard(
    deps: AlertCommandDeps, message: Message, user_id: int, text: str
) -> bool:
    state = deps.get_state(user_id)
    step = state.get("step")
    if step == "await_alert_asset":
        asset = text.strip()
        if not asset:
            await reply_plain(message, deps.tr(user_id, "alerts_ask_fx_asset"))
            return True
        deps.set_state_preserving_menu(
            user_id,
            {
                "step": "await_alert_schedule",
                "alert_kind": state.get("alert_kind"),
                "alert_asset": asset,
            },
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ساعتی", callback_data="alertsch:hourly"),
                    InlineKeyboardButton("روزانه", callback_data="alertsch:daily"),
                    InlineKeyboardButton("هفتگی", callback_data="alertsch:weekly"),
                ]
            ]
        )
        await reply_plain(message, deps.tr(user_id, "alerts_ask_schedule"), reply_markup=kb)
        return True
    if step == "await_alert_spike":
        raw = text.strip().replace("%", "")
        spike = None
        if raw not in ("-", "—", "no", "خیر", "0"):
            try:
                spike = float(raw.replace(",", "."))
            except ValueError:
                await reply_plain(message, deps.tr(user_id, "alerts_ask_spike"))
                return True
        ok, err = store.add_alert(
            user_id,
            kind=str(state.get("alert_kind") or "fx"),
            asset=str(state.get("alert_asset") or ""),
            schedule=str(state.get("alert_schedule") or "daily"),
            spike_pct=spike,
        )
        deps.clear_state(user_id)
        if not ok:
            await reply_plain(message, deps.tr(user_id, "alerts_add_fail", detail=err))
            return True
        await reply_plain(message, deps.tr(user_id, "alerts_added_ok"))
        return True
    return False


async def handle_alert_schedule_callback(
    deps: AlertCommandDeps, client: Any, callback_query: Any, schedule: str
) -> bool:
    uid = callback_query.from_user.id
    state = deps.get_state(uid)
    await callback_query.answer()
    if state.get("step") != "await_alert_schedule":
        return True
    kind = str(state.get("alert_kind") or "fx")
    if kind == "quake":
        deps.set_state_preserving_menu(
            uid,
            {
                "step": "await_alert_quake_mag",
                "alert_kind": "quake",
                "alert_asset": state.get("alert_asset") or "",
                "alert_schedule": schedule,
            },
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("≥ ۴", callback_data="alertqmag:4"),
                    InlineKeyboardButton("≥ ۴.۵", callback_data="alertqmag:4.5"),
                    InlineKeyboardButton("≥ ۵", callback_data="alertqmag:5"),
                ],
                [
                    InlineKeyboardButton("≥ ۵.۵", callback_data="alertqmag:5.5"),
                    InlineKeyboardButton("≥ ۶", callback_data="alertqmag:6"),
                ],
            ]
        )
        await reply_plain(
            callback_query.message, deps.tr(uid, "alerts_ask_quake_mag"), reply_markup=kb
        )
        return True
    deps.set_state_preserving_menu(
        uid,
        {
            "step": "await_alert_spike",
            "alert_kind": state.get("alert_kind"),
            "alert_asset": state.get("alert_asset"),
            "alert_schedule": schedule,
        },
    )
    await reply_plain(callback_query.message, deps.tr(uid, "alerts_ask_spike"))
    return True


async def handle_alert_quake_mag_callback(
    deps: AlertCommandDeps, client: Any, callback_query: Any, mag_s: str
) -> bool:
    uid = callback_query.from_user.id
    state = deps.get_state(uid)
    await callback_query.answer()
    if state.get("step") != "await_alert_quake_mag":
        return True
    try:
        mag = float(mag_s)
    except ValueError:
        mag = 4.5
    ok, err = store.add_alert(
        uid,
        kind="quake",
        asset=str(state.get("alert_asset") or ""),
        schedule=str(state.get("alert_schedule") or "daily"),
        spike_pct=mag,  # reuse spike_pct column as min Richter
    )
    deps.clear_state(uid)
    if not ok:
        await reply_plain(callback_query.message, deps.tr(uid, "alerts_add_fail", detail=err))
        return True
    await reply_plain(
        callback_query.message,
        deps.tr(uid, "alerts_quake_added_ok", mag=f"{mag:g}"),
    )
    return True
