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
    "btn_main_link_direct": "/show_link_direct_menu",
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
    "btn_toolkit_text": "/show_toolkit_text_menu",
    "btn_toolkit_gen": "/show_toolkit_gen_menu",
    "btn_toolkit_conv": "/show_toolkit_conv_menu",
    # Network tools
    "btn_tool_dns": "/tool dns",
    "btn_tool_myip": "/tool myip",
    "btn_tool_ping": "/tool ping",
    "btn_tool_port": "/tool port",
    "btn_tool_ssl": "/tool ssl",
    "btn_tool_rdns": "/tool rdns",
    "btn_tool_ipinfo": "/tool ipinfo",
    "btn_tool_headers": "/tool headers",
    "btn_tool_whois": "/tool whois",
    # Crypto / encoding tools
    "btn_tool_md5": "/tool md5",
    "btn_tool_sha1": "/tool sha1",
    "btn_tool_sha256": "/tool sha256",
    "btn_tool_sha512": "/tool sha512",
    "btn_tool_b64e": "/tool b64e",
    "btn_tool_b64d": "/tool b64d",
    "btn_tool_urle": "/tool urle",
    "btn_tool_urld": "/tool urld",
    "btn_tool_jwt": "/tool jwt",
    # Text tools
    "btn_tool_count": "/tool count",
    "btn_tool_upper": "/tool upper",
    "btn_tool_lower": "/tool lower",
    "btn_tool_title": "/tool title",
    "btn_tool_reverse": "/tool reverse",
    "btn_tool_slug": "/tool slug",
    "btn_tool_trim": "/tool trim",
    # Generator tools
    "btn_tool_uuid": "/tool uuid",
    "btn_tool_password": "/tool password",
    "btn_tool_token": "/tool token",
    "btn_tool_random_num": "/tool random_num",
    "btn_tool_lorem": "/tool lorem",
    # Converter tools
    "btn_tool_now": "/tool now",
    "btn_tool_ts2date": "/tool ts2date",
    "btn_tool_date2ts": "/tool date2ts",
    "btn_tool_base": "/tool base",
    "btn_tool_color": "/tool color",
    "btn_tool_size": "/tool size",
    "btn_tool_json": "/tool json",
    "btn_tool_calc": "/tool calc",
    # Direct send / plan
    "btn_direct_rubika_on": "/directmode rubika on",
    "btn_direct_bale_on": "/directmode bale on",
    "btn_direct_drive_on": "/directmode drive on",
    "btn_direct_rubika_off": "/directmode rubika off",
    "btn_direct_bale_off": "/directmode bale off",
    "btn_direct_drive_off": "/directmode drive off",
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
        [tr(user_id, "btn_main_transfer"), tr(user_id, "btn_main_link_direct")],
        [tr(user_id, "btn_main_toolkit")],
        [tr(user_id, "btn_main_settings"), tr(user_id, "btn_main_plan_section")],
        [tr(user_id, "btn_main_help")],
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
            [tr(user_id, "btn_transfer_rubika"), tr(user_id, "btn_transfer_bale")],
            [tr(user_id, "btn_transfer_drive"), tr(user_id, "btn_transfer_ssh")],
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
            [tr(user_id, "btn_toolkit_network"), tr(user_id, "btn_toolkit_crypto")],
            [tr(user_id, "btn_toolkit_text"), tr(user_id, "btn_toolkit_gen")],
            [tr(user_id, "btn_toolkit_conv")],
            [tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_network_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_myip"), tr(user_id, "btn_tool_dns")],
            [tr(user_id, "btn_tool_ping"), tr(user_id, "btn_tool_port")],
            [tr(user_id, "btn_tool_ssl"), tr(user_id, "btn_tool_rdns")],
            [tr(user_id, "btn_tool_ipinfo"), tr(user_id, "btn_tool_headers")],
            [tr(user_id, "btn_tool_whois")],
            [tr(user_id, "btn_back_toolkit"), tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_crypto_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_md5"), tr(user_id, "btn_tool_sha1")],
            [tr(user_id, "btn_tool_sha256"), tr(user_id, "btn_tool_sha512")],
            [tr(user_id, "btn_tool_b64e"), tr(user_id, "btn_tool_b64d")],
            [tr(user_id, "btn_tool_urle"), tr(user_id, "btn_tool_urld")],
            [tr(user_id, "btn_tool_jwt")],
            [tr(user_id, "btn_back_toolkit"), tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_text_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_count"), tr(user_id, "btn_tool_trim")],
            [tr(user_id, "btn_tool_upper"), tr(user_id, "btn_tool_lower")],
            [tr(user_id, "btn_tool_title"), tr(user_id, "btn_tool_reverse")],
            [tr(user_id, "btn_tool_slug")],
            [tr(user_id, "btn_back_toolkit"), tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_gen_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_uuid"), tr(user_id, "btn_tool_token")],
            [tr(user_id, "btn_tool_password"), tr(user_id, "btn_tool_random_num")],
            [tr(user_id, "btn_tool_lorem")],
            [tr(user_id, "btn_back_toolkit"), tr(user_id, "btn_back_main")],
        ]
    )


def build_toolkit_conv_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_tool_now")],
            [tr(user_id, "btn_tool_ts2date"), tr(user_id, "btn_tool_date2ts")],
            [tr(user_id, "btn_tool_base"), tr(user_id, "btn_tool_color")],
            [tr(user_id, "btn_tool_size"), tr(user_id, "btn_tool_json")],
            [tr(user_id, "btn_tool_calc")],
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


def build_link_direct_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply([[tr(user_id, "btn_back_main")]])


def build_settings_menu(
    user_id: int,
    tr: Translator,
    direct_target: Optional[str] = None,
) -> ReplyKeyboardMarkup:
    """Direct-send menu: ON buttons for inactive targets; OFF only for active target."""
    target = (direct_target or "").strip().lower()
    rows: List[List[str]] = []
    on_row: List[str] = []
    if target != "rubika":
        on_row.append(tr(user_id, "btn_direct_rubika_on"))
    if target != "bale":
        on_row.append(tr(user_id, "btn_direct_bale_on"))
    if target != "drive":
        on_row.append(tr(user_id, "btn_direct_drive_on"))
    if on_row:
        rows.append(on_row[:2])
        if len(on_row) > 2:
            rows.append(on_row[2:])
    if target == "rubika":
        rows.append([tr(user_id, "btn_direct_rubika_off")])
    elif target == "bale":
        rows.append([tr(user_id, "btn_direct_bale_off")])
    elif target == "drive":
        rows.append([tr(user_id, "btn_direct_drive_off")])
    rows.append([tr(user_id, "btn_netstatus")])
    rows.append([tr(user_id, "btn_back_main")])
    return _reply(rows)


def build_admin_menu(user_id: int, tr: Translator) -> ReplyKeyboardMarkup:
    return _reply(
        [
            [tr(user_id, "btn_admin_panel"), "/version"],
            [tr(user_id, "btn_main_plan_section")],
            [tr(user_id, "btn_back_main")],
        ]
    )
