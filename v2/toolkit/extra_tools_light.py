"""Misc utility tools (stdlib-only)."""

from __future__ import annotations

import ipaddress
import random
import re
import secrets
import socket
import string
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests

from v2.toolkit.dns_light import normalized_toolkit_host


def generate_password(
    length: int = 16,
    *,
    use_symbols: bool = True,
) -> str:
    n = max(8, min(int(length), 64))
    alphabet = string.ascii_letters + string.digits
    if use_symbols:
        alphabet += "!@#$%&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def reverse_dns(ip: str) -> tuple[bool, str]:
    try:
        addr = str(ipaddress.ip_address((ip or "").strip()))
    except ValueError:
        return False, "invalid_ip"
    try:
        host, _, _ = socket.gethostbyaddr(addr)
        return True, f"IP: {addr}\nPTR: {host}"
    except OSError as e:
        return False, str(e)


def expand_url(url: str, *, timeout: float = 12.0) -> tuple[bool, str]:
    target = (url or "").strip()
    if not target:
        return False, "empty_url"
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        r = requests.head(
            target,
            allow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "Tele2Rub-Toolkit/1.0"},
        )
        chain = [target]
        if r.url and r.url != target:
            chain.append(r.url)
        return True, " → ".join(chain) + f"\nStatus: {r.status_code}"
    except requests.RequestException as e:
        return False, str(e)[:400]


def unix_timestamp_convert(text: str) -> tuple[bool, str]:
    raw = (text or "").strip().lower()
    if not raw:
        return False, "empty"
    if raw.isdigit():
        ts = int(raw)
        if ts > 10_000_000_000:
            ts //= 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return True, f"Timestamp: {raw}\nUTC: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    try:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                return True, f"Date: {raw}\nUnix: {int(dt.timestamp())}"
            except ValueError:
                continue
    except Exception:
        pass
    return False, "use unix number or YYYY-MM-DD HH:MM:SS"


def lorem_ipsum(words: int = 50) -> str:
    w = max(5, min(int(words), 200))
    pool = (
        "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
        "incididunt ut labore et dolore magna aliqua".split()
    )
    out = []
    for _ in range(w):
        out.append(random.choice(pool))
    return " ".join(out).capitalize() + "."
