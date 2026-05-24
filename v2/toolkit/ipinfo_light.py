"""Small IP information helper using public HTTP APIs."""

from __future__ import annotations

import ipaddress
import json
import urllib.request


def normalize_ip(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    return str(ipaddress.ip_address(raw))


def get_ip_info(ip: str, *, timeout: float = 8.0) -> tuple[bool, str]:
    try:
        target = normalize_ip(ip)
    except ValueError:
        return False, "invalid_ip"
    try:
        req = urllib.request.Request(
            f"https://ipinfo.io/{target}/json",
            headers={"User-Agent": "telegramtorubika-toolkit/1"},
        )
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return False, str(e)[:500]

    lines = [
        f"IP: {data.get('ip') or target}",
        f"City: {data.get('city') or '-'}",
        f"Region: {data.get('region') or '-'}",
        f"Country: {data.get('country') or '-'}",
        f"Org: {data.get('org') or '-'}",
        f"Location: {data.get('loc') or '-'}",
        f"Timezone: {data.get('timezone') or '-'}",
    ]
    return True, "\n".join(lines)
