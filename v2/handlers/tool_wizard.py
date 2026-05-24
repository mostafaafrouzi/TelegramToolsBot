"""Single-step tool wizard: user taps a tool button → bot asks for input → user
sends a plain message → bot runs the tool and answers.

This avoids forcing users to type `/dns example.com` style commands.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from pyrogram.types import Message

from v2.toolkit.dns_light import resolve_hostname
from v2.toolkit.myip_light import get_public_ip
from v2.toolkit.ping_light import tcp_ping
from v2.toolkit.text_utils_light import (
    b64_decode_str,
    b64_encode_str,
    clip_input,
    md5_hex,
    sha256_hex,
)
from v2.toolkit.extended_tools import (
    base_convert,
    clean_whitespace,
    color_convert,
    count_text,
    date_to_ts,
    generate_password,
    generate_token_hex,
    generate_uuid,
    http_headers,
    ip_geo,
    json_format,
    jwt_decode,
    lorem_ipsum,
    now_panel,
    port_check,
    random_number,
    reverse_dns,
    reverse_text,
    safe_calc,
    sha1_hex,
    sha512_hex,
    size_convert,
    slugify,
    ssl_info,
    to_lower,
    to_title,
    to_upper,
    ts_to_date,
    url_decode,
    url_encode,
    whois_lookup,
)

TranslateFn = Callable[..., str]


@dataclass(frozen=True)
class ToolWizardDeps:
    tr: TranslateFn
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    toolkit_network_light_enabled: bool
    toolkit_utility_light_enabled: bool
    toolkit_quota_try: Callable[[int], tuple[bool, str]]
    toolkit_quota_commit: Callable[[int], None]


# ---------------------------------------------------------------------------
# Catalog: tool_id -> (prompt_key, runner)
# ---------------------------------------------------------------------------

def _run_dns(value: str) -> tuple[bool, str]:
    return resolve_hostname(value.strip())


def _run_ping(value: str) -> tuple[bool, str]:
    parts = value.strip().split()
    if not parts:
        return False, "empty"
    host = parts[0]
    port = 443
    if len(parts) >= 2:
        try:
            port = int(parts[1])
        except ValueError:
            return False, "invalid port"
    return tcp_ping(host, port=port)


def _run_port(value: str) -> tuple[bool, str]:
    parts = value.strip().replace(":", " ").split()
    if len(parts) < 2:
        return False, "use 'host port' e.g. example.com 80"
    try:
        port = int(parts[1])
    except ValueError:
        return False, "invalid port"
    return port_check(parts[0], port)


def _run_ssl(value: str) -> tuple[bool, str]:
    parts = value.strip().replace(":", " ").split()
    if not parts:
        return False, "empty"
    host = parts[0]
    port = 443
    if len(parts) >= 2:
        try:
            port = int(parts[1])
        except ValueError:
            return False, "invalid port"
    return ssl_info(host, port=port)


def _run_md5(value: str) -> tuple[bool, str]:
    text, _ = clip_input(value)
    return True, md5_hex(text)


def _run_sha1(value: str) -> tuple[bool, str]:
    text, _ = clip_input(value)
    return True, sha1_hex(text)


def _run_sha256(value: str) -> tuple[bool, str]:
    text, _ = clip_input(value)
    return True, sha256_hex(text)


def _run_sha512(value: str) -> tuple[bool, str]:
    text, _ = clip_input(value)
    return True, sha512_hex(text)


def _run_b64e(value: str) -> tuple[bool, str]:
    text, _ = clip_input(value)
    return True, b64_encode_str(text)


def _run_b64d(value: str) -> tuple[bool, str]:
    text, _ = clip_input(value)
    return b64_decode_str(text)


def _run_urle(value: str) -> tuple[bool, str]:
    return True, url_encode(value)


def _run_urld(value: str) -> tuple[bool, str]:
    return url_decode(value)


def _run_count(value: str) -> tuple[bool, str]:
    return True, count_text(value)


def _run_upper(value: str) -> tuple[bool, str]:
    return True, to_upper(value)


def _run_lower(value: str) -> tuple[bool, str]:
    return True, to_lower(value)


def _run_title(value: str) -> tuple[bool, str]:
    return True, to_title(value)


def _run_reverse(value: str) -> tuple[bool, str]:
    return True, reverse_text(value)


def _run_slug(value: str) -> tuple[bool, str]:
    return True, slugify(value)


def _run_trim(value: str) -> tuple[bool, str]:
    return True, clean_whitespace(value)


def _run_password(value: str) -> tuple[bool, str]:
    raw = (value or "").strip()
    length = 20
    if raw:
        try:
            length = int(raw)
        except ValueError:
            return False, "send a number for length (8-128)"
    return True, generate_password(length)


def _run_uuid(_value: str) -> tuple[bool, str]:
    return True, generate_uuid()


def _run_token(value: str) -> tuple[bool, str]:
    raw = (value or "").strip()
    n = 16
    if raw:
        try:
            n = int(raw)
        except ValueError:
            return False, "send length in bytes (4-64)"
    return True, generate_token_hex(n)


def _run_random_num(value: str) -> tuple[bool, str]:
    raw = (value or "0 100").strip()
    parts = raw.replace(",", " ").split()
    lo, hi = 0, 100
    if len(parts) >= 2:
        try:
            lo, hi = int(parts[0]), int(parts[1])
        except ValueError:
            return False, "send 'lo hi' (e.g. '1 1000')"
    return True, random_number(lo, hi)


def _run_lorem(value: str) -> tuple[bool, str]:
    raw = (value or "2").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 2
    return True, lorem_ipsum(n)


def _run_now(_value: str) -> tuple[bool, str]:
    return True, now_panel()


def _run_ts2date(value: str) -> tuple[bool, str]:
    return ts_to_date(value)


def _run_date2ts(value: str) -> tuple[bool, str]:
    return date_to_ts(value)


def _run_base(value: str) -> tuple[bool, str]:
    return base_convert(value)


def _run_color(value: str) -> tuple[bool, str]:
    return color_convert(value)


def _run_json(value: str) -> tuple[bool, str]:
    return json_format(value)


def _run_size(value: str) -> tuple[bool, str]:
    return size_convert(value)


def _run_jwt(value: str) -> tuple[bool, str]:
    return jwt_decode(value)


def _run_myip(_value: str) -> tuple[bool, str]:
    return get_public_ip()


def _run_rdns(value: str) -> tuple[bool, str]:
    return reverse_dns(value)


def _run_ipinfo(value: str) -> tuple[bool, str]:
    return ip_geo(value)


def _run_headers(value: str) -> tuple[bool, str]:
    return http_headers(value)


def _run_whois(value: str) -> tuple[bool, str]:
    return whois_lookup(value)


def _run_calc(value: str) -> tuple[bool, str]:
    return safe_calc(value)


# tool_id -> (prompt_i18n_key, runner, category: 'network' | 'utility',
#             needs_input: bool, run_in_thread: bool)
TOOL_CATALOG: dict[str, tuple[str, Callable[[str], tuple[bool, str]], str, bool, bool]] = {
    # Network
    "dns": ("tool_prompt_dns", _run_dns, "network", True, True),
    "ping": ("tool_prompt_ping", _run_ping, "network", True, True),
    "port": ("tool_prompt_port", _run_port, "network", True, True),
    "ssl": ("tool_prompt_ssl", _run_ssl, "network", True, True),
    "rdns": ("tool_prompt_rdns", _run_rdns, "network", True, True),
    "ipinfo": ("tool_prompt_ipinfo", _run_ipinfo, "network", True, True),
    "headers": ("tool_prompt_headers", _run_headers, "network", True, True),
    "whois": ("tool_prompt_whois", _run_whois, "network", True, True),
    "myip": ("tool_prompt_myip", _run_myip, "network", False, True),
    # Crypto / encoding
    "md5": ("tool_prompt_md5", _run_md5, "utility", True, False),
    "sha1": ("tool_prompt_sha1", _run_sha1, "utility", True, False),
    "sha256": ("tool_prompt_sha256", _run_sha256, "utility", True, False),
    "sha512": ("tool_prompt_sha512", _run_sha512, "utility", True, False),
    "b64e": ("tool_prompt_b64e", _run_b64e, "utility", True, False),
    "b64d": ("tool_prompt_b64d", _run_b64d, "utility", True, False),
    "urle": ("tool_prompt_urle", _run_urle, "utility", True, False),
    "urld": ("tool_prompt_urld", _run_urld, "utility", True, False),
    "jwt": ("tool_prompt_jwt", _run_jwt, "utility", True, False),
    # Text
    "count": ("tool_prompt_count", _run_count, "utility", True, False),
    "upper": ("tool_prompt_text", _run_upper, "utility", True, False),
    "lower": ("tool_prompt_text", _run_lower, "utility", True, False),
    "title": ("tool_prompt_text", _run_title, "utility", True, False),
    "reverse": ("tool_prompt_text", _run_reverse, "utility", True, False),
    "slug": ("tool_prompt_text", _run_slug, "utility", True, False),
    "trim": ("tool_prompt_text", _run_trim, "utility", True, False),
    # Generators
    "uuid": ("tool_prompt_uuid", _run_uuid, "utility", False, False),
    "password": ("tool_prompt_password", _run_password, "utility", False, False),
    "token": ("tool_prompt_token", _run_token, "utility", False, False),
    "random_num": ("tool_prompt_random_num", _run_random_num, "utility", False, False),
    "lorem": ("tool_prompt_lorem", _run_lorem, "utility", False, False),
    # Converters
    "now": ("tool_prompt_now", _run_now, "utility", False, False),
    "ts2date": ("tool_prompt_ts2date", _run_ts2date, "utility", True, False),
    "date2ts": ("tool_prompt_date2ts", _run_date2ts, "utility", True, False),
    "base": ("tool_prompt_base", _run_base, "utility", True, False),
    "color": ("tool_prompt_color", _run_color, "utility", True, False),
    "size": ("tool_prompt_size", _run_size, "utility", True, False),
    "json": ("tool_prompt_json", _run_json, "utility", True, False),
    "calc": ("tool_prompt_calc", _run_calc, "utility", True, False),
}


def _category_enabled(deps: ToolWizardDeps, category: str) -> bool:
    if category == "network":
        return deps.toolkit_network_light_enabled
    return deps.toolkit_utility_light_enabled


def _category_disabled_key(category: str) -> str:
    return "toolkit_network_disabled" if category == "network" else "toolkit_utility_disabled"


async def start_tool_wizard(deps: ToolWizardDeps, message: Message, tool_id: str) -> None:
    """Open the wizard for a tool. If the tool needs no input, run it now."""
    uid = message.from_user.id
    entry = TOOL_CATALOG.get(tool_id)
    if not entry:
        return
    prompt_key, runner, category, needs_input, run_in_thread = entry
    if not _category_enabled(deps, category):
        await message.reply_text(deps.tr(uid, _category_disabled_key(category)), parse_mode=None)
        return
    if not needs_input:
        await _execute_tool(deps, message, tool_id, "", runner, category, run_in_thread)
        return
    deps.set_state_preserving_menu(uid, {"step": "await_tool_input", "tool_id": tool_id})
    await message.reply_text(deps.tr(uid, prompt_key), parse_mode=None)


async def handle_tool_input(
    deps: ToolWizardDeps,
    message: Message,
    user_id: int,
    state: dict,
    text: str,
) -> bool:
    if state.get("step") != "await_tool_input":
        return False
    tool_id = state.get("tool_id") or ""
    entry = TOOL_CATALOG.get(tool_id)
    if not entry:
        deps.clear_state(user_id)
        return False
    prompt_key, runner, category, _needs_input, run_in_thread = entry
    if not _category_enabled(deps, category):
        deps.clear_state(user_id)
        await message.reply_text(deps.tr(user_id, _category_disabled_key(category)), parse_mode=None)
        return True
    deps.clear_state(user_id)
    await _execute_tool(deps, message, tool_id, text, runner, category, run_in_thread)
    return True


async def _execute_tool(
    deps: ToolWizardDeps,
    message: Message,
    tool_id: str,
    value: str,
    runner: Callable[[str], tuple[bool, str]],
    category: str,
    run_in_thread: bool,
) -> None:
    uid = message.from_user.id
    ok, msg = deps.toolkit_quota_try(uid)
    if not ok:
        await message.reply_text(msg, parse_mode=None)
        return
    try:
        if run_in_thread:
            ok_run, body = await asyncio.to_thread(runner, value)
        else:
            ok_run, body = runner(value)
    except Exception as exc:  # pragma: no cover - defensive
        ok_run, body = False, str(exc)
    if ok_run:
        deps.toolkit_quota_commit(uid)
        header = deps.tr(uid, "tool_result_header", tool=tool_id)
        await message.reply_text(f"{header}\n{body}", parse_mode=None)
    else:
        await message.reply_text(
            deps.tr(uid, "tool_result_error", tool=tool_id, error=body),
            parse_mode=None,
        )
