"""IP lookup helper (rich format via ip-api.com)."""

from __future__ import annotations

import ipaddress

from v2.toolkit.whois_light import _ip_lookup_rich


def normalize_ip(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    return str(ipaddress.ip_address(raw))


def get_ip_info(ip: str, *, timeout: float = 8.0) -> tuple[bool, str]:
    del timeout  # ip-api uses its own timeout in _ip_lookup_rich
    try:
        target = normalize_ip(ip)
    except ValueError:
        return False, "invalid_ip"
    return _ip_lookup_rich(target)
