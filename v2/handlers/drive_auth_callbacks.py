"""Inline callbacks for Drive connect: service account vs OAuth."""

from __future__ import annotations

from typing import Any

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from v2.core.menu_sections import MenuSection
from v2.handlers.drive_oauth_flow import notify_oauth_failure
from v2.handlers.provider_connect_wizards import ProviderConnectWizardDeps
from v2.toolkit.drive_oauth_light import build_auth_url, oauth_configured
from v2.transfer.user_credentials import default_drive_sa_path


async def dispatch_drive_auth_callback(
    deps: ProviderConnectWizardDeps,
    client: Any,
    callback_query: Any,
    action: str,
) -> bool:
    uid = callback_query.from_user.id
    deps.set_menu_section(uid, MenuSection.DRIVE)

    if action == "sa":
        sa = default_drive_sa_path(deps.base_dir, uid)
        if sa.is_file():
            from v2.toolkit.drive_light import service_account_email

            email = service_account_email(sa)
            deps.set_state_preserving_menu(uid, {"step": "await_drive_folder_id"})
            await callback_query.answer()
            await callback_query.message.reply_text(
                deps.tr(uid, "drive_sa_already_uploaded", email=email or "—"),
                parse_mode=None,
            )
            return True
        deps.set_state_preserving_menu(uid, {"step": "await_drive_sa_json"})
        await callback_query.answer()
        await callback_query.message.reply_text(deps.tr(uid, "drive_ask_sa_json"), parse_mode=None)
        deps.log_event("drive_connect_sa", user_id=uid)
        return True

    if action == "oauth":
        if not oauth_configured():
            await callback_query.answer(deps.tr(uid, "drive_oauth_not_configured"), show_alert=True)
            return True
        ok, url_or_err = build_auth_url(uid)
        if not ok:
            await callback_query.answer(str(url_or_err)[:180], show_alert=True)
            return True
        deps.set_state_preserving_menu(uid, {"step": "await_drive_oauth_code"})
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(deps.tr(uid, "btn_drive_oauth_open"), url=url_or_err)]]
        )
        await callback_query.answer()
        await callback_query.message.reply_text(
            deps.tr(uid, "drive_oauth_start"),
            reply_markup=kb,
            parse_mode=None,
            disable_web_page_preview=True,
        )
        deps.log_event("drive_connect_oauth", user_id=uid)
        return True

    return False
