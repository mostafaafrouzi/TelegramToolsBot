"""MAC address vendor lookup (macvendors.com)."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request


def normalize_mac(mac: str) -> str:
    raw = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(raw) != 12:
        return ""
    return ":".join(raw[i : i + 2] for i in range(0, 12, 2)).upper()


def mac_vendor_lookup(mac: str) -> tuple[bool, str]:
    norm = normalize_mac(mac)
    if not norm:
        return False, "invalid_mac"
    url = f"https://api.macvendors.com/{urllib.parse.quote(norm)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Tele2Rub-Toolkit/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            vendor = resp.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return False, str(e)[:400]
    if not vendor or "not found" in vendor.lower():
        return False, vendor or "not_found"
    return True, f"MAC: {norm}\nVendor: {vendor}"
