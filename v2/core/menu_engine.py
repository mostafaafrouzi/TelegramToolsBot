"""Menu rendering and reply-keyboard routing (hierarchical, icon labels)."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup

Translator = Callable[[int, str], str]

# i18n key -> internal route (resolved against tr(user_id, key)).
_I18N_BUTTON_ROUTES: Dict[str, str] = {
    # Main
    "btn_main_transfer": "/show_transfer_menu",
    "btn_main_toolkit": "/show_toolkit_menu",
    "btn_main_plan_section": "/show_plan_menu",
    "btn_main_settings": "/show_settings_menu",
    "btn_main_help": "/help",
    "btn_main_admin": "/show_admin_menu",
    "btn_back_main": "/menu",
    "btn_back_transfer": "/show_transfer_menu",
    "btn_back_toolkit": "/show_toolkit_menu",
    # Transfer destinations
    "btn_transfer_rubika": "/show_rubika_menu",
    "btn_transfer_bale": "/show_bale_menu",
    "btn_transfer_drive": "/show_drive_menu",
    "btn_transfer_ssh": "/show_ssh_menu",
    "btn_transfer_files": "/show_files_menu",
    # Rubika
    "btn_rub_connect": "/rubika_connect",
    "btn_rub_status": "/rubika_status",
    # Bale
    "btn_bale_connect": "/bale_connect",
    "btn_bale_status": "/bale_status",
    "btn_bale_disconnect": "/bale_disconnect",
    # Drive
    "btn_drive_connect": "/drive_connect",
    "btn_drive_status": "/drive_status",
    "btn_drive_disconnect": "/drive_disconnect",
    "btn_drive_download_help": "/drive_download_help",
    # SSH
    "btn_ssh_list": "/ssh_list",
    "btn_ssh_add_help": "/ssh_add_help",
    # Files / queue
    "btn_zip_start": "/newbatch",
    "btn_zip_end": "/done",
    "btn_send_content": "/quick_send_prompt",
    "btn_queue": "/queue",
    "btn_clear_all": "/delall",
    # Toolkit hub
    "btn_toolkit_network": "/show_toolkit_network_menu",
    "btn_toolkit_crypto": "/show_toolkit_crypto_menu",
    "btn_tool_dns": "/dns",
    "btn_tool_myip": "/myip",
    "btn_tool_ping": "/ping",
    "btn_tool_md5": "/md5",
    "btn_tool_sha256": "/sha256",
    "btn_tool_b64e": "/b64e",
    "btn_tool_b64d": "/b64d",
    # Settings / plan
    "btn_direct_on": "/directmode on",
    "btn_direct_off": "/directmode off",
    "btn_netstatus": "/netstatus",
    "btn_plan_plan": "/plan",
    "btn_plan_usage": "/usage",
    "btn_plan_buy": "/purchase",
    "btn_admin_panel": "/admin",
}

# Literal button text (slashes, aliases) — language-independent.
_STATIC_BUTTON_ROUTES: Dict[str, str] = {
    "menu": "/menu",
    "منو": "/menu",
    "help": "/help",
    "راهنما": "/help",
    "راهنمای لاگ": "/loghelp",
    "/plan": "/plan",
    "/usage": "/usage",
    "/purchase": "/purchase",
    "/queue": "/queue",
    "/dns": "/dns",
    "/myip": "/myip",
    "/ping": "/ping",
    "/md5": "/md5",
    "/sha256": "/sha256",
    "/b64e": "/b64e",
    "/b64d": "/b64d",
    "/ssh_list": "/ssh_list",
    "/ssh_add": "/ssh_add_help",
    "/ssh_put": "/ssh_put_help",
    "/ssh_get": "/ssh_get_help",
    "/drive_download": "/drive_download_help",
    "/drive_status": "/drive_status",
    "/drive_connect": "/drive_connect",
    "/drive_disconnect": "/drive_disconnect",
    "/bale_status": "/bale_status",
    "/bale_connect": "/bale_connect",
    "/bale_disconnect": "/bale_disconnect",
    "/bale_set_chat": "/bale_set_chat",
    "/rubika_connect": "/rubika_connect",
    "/rubika_status": "/rubika_status",
}


def resolve_reply_button_route(
    text: str,
    user_id: Optional[int] = None,
    tr: Optional[Translator] = None,
) -> Optional[str]:
    """Return internal route for a reply-keyboard label."""
    raw = (text or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if low in _STATIC_BUTTON_ROUTES:
        return _STATIC_BUTTON_ROUTES[low]
    if raw in _STATIC_BUTTON_ROUTES:
        return _STATIC_BUTTON_ROUTES[raw]
    if user_id is not None and tr is not None:
        for i18n_key, route in _I18N_BUTTON_ROUTES.items():
            if raw == tr(user_id, i18n_key):
                return route
    return None


def _reply(rows: List[List[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(label) for label in row] for row in rows],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def build_main_menu(user_id: int, tr: Translator, is_admin: bool) -> ReplyKeyboardMarkup:
    rows: List[List[str]] = [
        [tr(user_id, "btn_main_transfer")],
        [tr(user_id, "btn_main_toolkit")],
        [tr(user_id, "btn_main_plan_section")],
        [tr(user_id, "btn_main_settings"), tr(user_id, "btn_main_help")],
    ]
    if is_admin:
        rows.append([tr(user_id, "btn_main_admin")])
    return _reply(rows)


def build_plan_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_plan_plan"), tr(user_id, "btn_plan_usage")],
            [tr(user_id, "btn_plan_buy")],
            [tr(user_id, "btn_queue")],
            [tr(user_id, "btn_back_main")],
        ]
    )


def build_transfer_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_transfer_rubika")],
            [tr(user_id, "btn_transfer_bale"), tr(user_id, "btn_transfer_drive")],
            [tr(user_id, "btn_transfer_ssh")],
            [tr(user_id, "btn_transfer_files")],
            [tr(user_id, "btn_back_main")],
        ]
    )


def build_rubika_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_rub_connect"), tr(user_id, "btn_rub_status")],
            [tr(user_id, "btn_back_transfer"), tr(user_id, "btn_back_main")],
        ]
    )


def build_bale_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_bale_connect"), tr(user_id, "btn_bale_status")],
            [tr(user_id, "btn_bale_disconnect")],
            [tr(user_id, "btn_back_transfer"), tr(user_id, "btn_back_main")],
        ]
    )


def build_drive_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_drive_connect"), tr(user_id, "btn_drive_status")],
            [tr(user_id, "btn_drive_download_help"), tr(user_id, "btn_drive_disconnect")],
            [tr(user_id, "btn_back_transfer"), tr(user_id, "btn_back_main")],
        ]
    )


def build_ssh_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_ssh_list"), tr(user_id, "btn_ssh_add_help")],
            [tr(user_id, "btn_back_transfer"), tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_toolkit_network")],
            [tr(user_id, "btn_toolkit_crypto")],
            [tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_network_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_dns"), tr(user_id, "btn_tool_myip")],
            [tr(user_id, "btn_tool_ping")],
            [tr(user_id, "btn_back_toolkit"), tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_crypto_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_md5"), tr(user_id, "btn_tool_sha256")],
            [tr(user_id, "btn_tool_b64e"), tr(user_id, "btn_tool_b64d")],
            [tr(user_id, "btn_back_toolkit"), tr(user_id, "btn_back_main")],
        ]
    )


def build_files_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_zip_start"), tr(user_id, "btn_zip_end")],
            [tr(user_id, "btn_send_content")],
            [tr(user_id, "btn_queue"), tr(user_id, "btn_clear_all")],
            [tr(user_id, "btn_back_transfer"), tr(user_id, "btn_back_main")],
        ]
    )


def build_settings_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_direct_on"), tr(user_id, "btn_direct_off")],
            [tr(user_id, "btn_netstatus")],
            [tr(user_id, "btn_back_main")],
        ]
    )


def build_admin_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_admin_panel"), "/version"],
            [tr(user_id, "btn_main_plan_section")],
            [tr(user_id, "btn_back_main")],
        ]
    )
