"""Inline (glass) menus — navigate within one message via edit_text."""

from __future__ import annotations

from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

Translator = Callable[[int, str], str]


def _row(*buttons: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return list(buttons)


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)


def build_inline_main(uid: int, tr: Translator, *, is_admin: bool) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "inline_main_title")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_main_transfer"), callback_data="imenu:transfer"),
            InlineKeyboardButton(tr(uid, "btn_main_toolkit"), callback_data="imenu:toolkit"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_main_link_direct"), callback_data="imenu:link"),
            InlineKeyboardButton(tr(uid, "btn_main_settings"), callback_data="imenu:settings"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_main_plan_section"), callback_data="imenu:plan"),
            InlineKeyboardButton(tr(uid, "btn_main_help"), callback_data="imenu:help"),
        ),
        _row(InlineKeyboardButton(tr(uid, "inline_world_menu"), callback_data="imenu:world")),
    ]
    if is_admin:
        rows.append(_row(InlineKeyboardButton(tr(uid, "btn_main_admin"), callback_data="imenu:admin")))
    return body, _kb(rows)


def build_inline_toolkit(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "toolkit_menu_title")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_toolkit_network"), callback_data="imenu:toolkit_net"),
            InlineKeyboardButton(tr(uid, "btn_toolkit_crypto"), callback_data="imenu:toolkit_crypto"),
        ),
        _row(InlineKeyboardButton(tr(uid, "inline_world_menu"), callback_data="imenu:world")),
        _row(InlineKeyboardButton(tr(uid, "btn_back_main"), callback_data="imenu:main")),
    ]
    return body, _kb(rows)


def build_inline_toolkit_network(uid: int, tr: Translator, *, webapp_url: str = "") -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "toolkit_network_menu_title")
    myip_btn: InlineKeyboardButton
    if webapp_url:
        from pyrogram.types import WebAppInfo

        myip_btn = InlineKeyboardButton(
            tr(uid, "btn_tool_myip"),
            web_app=WebAppInfo(url=f"{webapp_url.rstrip('/')}/miniapp/myip.html"),
        )
    else:
        myip_btn = InlineKeyboardButton(tr(uid, "btn_tool_myip"), callback_data="imenu:myip_hint")

    rows = [
        _row(myip_btn, InlineKeyboardButton(tr(uid, "btn_tool_dns"), callback_data="imenu:dns")),
        _row(
            InlineKeyboardButton(tr(uid, "btn_tool_ping"), callback_data="imenu:ping"),
            InlineKeyboardButton(tr(uid, "btn_tool_ipinfo"), callback_data="imenu:ipinfo"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_tool_whois"), callback_data="imenu:whois"),
            InlineKeyboardButton(tr(uid, "btn_tool_myid"), callback_data="imenu:myid"),
        ),
        _row(InlineKeyboardButton(tr(uid, "btn_back_toolkit"), callback_data="imenu:toolkit")),
    ]
    return body, _kb(rows)


def build_inline_toolkit_crypto(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "toolkit_crypto_menu_title")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_tool_md5"), callback_data="imenu:md5"),
            InlineKeyboardButton(tr(uid, "btn_tool_sha256"), callback_data="imenu:sha256"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_tool_b64e"), callback_data="imenu:b64e"),
            InlineKeyboardButton(tr(uid, "btn_tool_b64d"), callback_data="imenu:b64d"),
        ),
        _row(InlineKeyboardButton(tr(uid, "btn_back_toolkit"), callback_data="imenu:toolkit")),
    ]
    return body, _kb(rows)


def build_inline_world(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "inline_world_title")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_world_weather"), callback_data="imenu:weather"),
            InlineKeyboardButton(tr(uid, "btn_world_calendar"), callback_data="imenu:calendar"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_world_currency"), callback_data="imenu:currency"),
            InlineKeyboardButton(tr(uid, "btn_world_earthquake"), callback_data="imenu:quake"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_world_rss"), callback_data="imenu:rss"),
            InlineKeyboardButton(tr(uid, "btn_world_rss_list"), callback_data="imenu:rss_list"),
        ),
        _row(InlineKeyboardButton(tr(uid, "btn_back_main"), callback_data="imenu:main")),
    ]
    return body, _kb(rows)


def build_inline_transfer(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "transfer_menu_title")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_transfer_rubika"), callback_data="imenu:rubika"),
            InlineKeyboardButton(tr(uid, "btn_transfer_bale"), callback_data="imenu:bale"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_transfer_drive"), callback_data="imenu:drive"),
            InlineKeyboardButton(tr(uid, "btn_transfer_files"), callback_data="imenu:files"),
        ),
        _row(InlineKeyboardButton(tr(uid, "btn_back_main"), callback_data="imenu:main")),
    ]
    return body, _kb(rows)


def build_inline_settings(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "settings_menu_title")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_direct_rubika_on"), callback_data="imenu:dm_rubika"),
            InlineKeyboardButton(tr(uid, "btn_direct_bale_on"), callback_data="imenu:dm_bale"),
        ),
        _row(
            InlineKeyboardButton(tr(uid, "btn_direct_drive_on"), callback_data="imenu:dm_drive"),
            InlineKeyboardButton(tr(uid, "btn_netstatus"), callback_data="imenu:netstatus"),
        ),
        _row(InlineKeyboardButton(tr(uid, "btn_back_main"), callback_data="imenu:main")),
    ]
    return body, _kb(rows)


def build_inline_link(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "link_menu_opened")
    rows = [
        _row(InlineKeyboardButton(tr(uid, "btn_back_main"), callback_data="imenu:main")),
    ]
    return body, _kb(rows)


def build_inline_plan(uid: int, tr: Translator) -> tuple[str, InlineKeyboardMarkup]:
    body = tr(uid, "plan_menu_opened")
    rows = [
        _row(
            InlineKeyboardButton(tr(uid, "btn_plan_plan"), callback_data="imenu:plan_show"),
            InlineKeyboardButton(tr(uid, "btn_plan_usage"), callback_data="imenu:usage"),
        ),
        _row(InlineKeyboardButton(tr(uid, "btn_plan_buy"), callback_data="imenu:purchase")),
        _row(InlineKeyboardButton(tr(uid, "btn_back_main"), callback_data="imenu:main")),
    ]
    return body, _kb(rows)


_INLINE_BUILDERS = {
    "main": build_inline_main,
    "toolkit": build_inline_toolkit,
    "toolkit_net": build_inline_toolkit_network,
    "toolkit_crypto": build_inline_toolkit_crypto,
    "world": build_inline_world,
    "transfer": build_inline_transfer,
    "settings": build_inline_settings,
    "plan": build_inline_plan,
    "link": build_inline_link,
}


def resolve_inline_menu(
    key: str,
    uid: int,
    tr: Translator,
    *,
    is_admin: bool = False,
    webapp_url: str = "",
) -> Optional[tuple[str, InlineKeyboardMarkup]]:
    k = (key or "").strip().lower()
    if k == "main":
        return build_inline_main(uid, tr, is_admin=is_admin)
    if k == "toolkit_net":
        return build_inline_toolkit_network(uid, tr, webapp_url=webapp_url)
    fn = _INLINE_BUILDERS.get(k)
    if not fn:
        return None
    return fn(uid, tr)
