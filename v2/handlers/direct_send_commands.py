"""Direct-send settings (/directmode) with rubika | bale | drive targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]
DirectTarget = Optional[str]


@dataclass(frozen=True)
class DirectSendCommandDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    get_direct_mode_target: Callable[[int], DirectTarget]
    set_direct_mode_target: Callable[[int, Optional[str]], None]
    get_user_session: Callable[[int], Optional[str]]
    get_bale_ready: Callable[[int], bool]
    get_drive_ready: Callable[[int], bool]
    build_settings_menu: Callable[[int], Any]
    build_main_menu: Callable[[int], Any]


def _verify_target(deps: DirectSendCommandDeps, uid: int, target: str) -> Optional[str]:
    """Return i18n error key if not connected, else None."""
    if target == "rubika":
        if not deps.get_user_session(uid):
            return "direct_need_rubika"
    elif target == "bale":
        if not deps.get_bale_ready(uid):
            return "bale_not_connected"
    elif target == "drive":
        if not deps.get_drive_ready(uid):
            return "drive_not_connected"
    return None


async def handle_direct_mode(deps: DirectSendCommandDeps, client: Any, message: Message) -> None:
    uid = message.from_user.id
    parts = (message.text or "").split()
    # /directmode [rubika|bale|drive] [on|off]  OR  /directmode on|off (legacy → rubika)
    if len(parts) < 2:
        await message.reply_text(deps.tr(uid, "directmode_usage"))
        return

    deps.set_menu_section(uid, MenuSection.SETTINGS)
    arg1 = parts[1].strip().lower()
    arg2 = parts[2].strip().lower() if len(parts) > 2 else ""

    if arg1 in ("on", "off") and arg2 == "":
        target = "rubika"
        action = arg1
    elif arg1 in ("rubika", "bale", "drive"):
        target = arg1
        action = arg2 or "on"
    else:
        await message.reply_text(deps.tr(uid, "directmode_usage"))
        return

    if action == "off":
        current = deps.get_direct_mode_target(uid)
        if current and current != target:
            await message.reply_text(
                deps.tr(uid, "direct_off_wrong_target", active=current),
                reply_markup=deps.build_settings_menu(uid),
            )
            return
        deps.set_direct_mode_target(uid, None)
        await message.reply_text(
            deps.tr(uid, "direct_off"),
            reply_markup=deps.build_main_menu(uid),
        )
        return

    if action != "on":
        await message.reply_text(deps.tr(uid, "directmode_usage"))
        return

    err = _verify_target(deps, uid, target)
    if err:
        await message.reply_text(
            deps.tr(uid, err),
            reply_markup=deps.build_settings_menu(uid),
        )
        return

    current = deps.get_direct_mode_target(uid)
    if current and current != target:
        deps.set_direct_mode_target(uid, None)
        await message.reply_text(
            deps.tr(uid, "direct_switched_off", old=current),
            reply_markup=deps.build_settings_menu(uid),
            parse_mode=None,
        )

    deps.set_direct_mode_target(uid, target)
    await message.reply_text(
        deps.tr(uid, f"direct_on_{target}")
        + "\n\n"
        + deps.tr(uid, "direct_on_explain"),
        reply_markup=deps.build_settings_menu(uid),
        parse_mode=None,
    )
