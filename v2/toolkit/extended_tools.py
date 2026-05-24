"""Expanded toolkit utilities (stdlib-only where possible).

Each function returns (ok: bool, message_or_result: str). Functions are sync
and intentionally lightweight so they can be safely run from async handlers
via ``asyncio.to_thread`` when needed.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import math
import os
import re
import secrets
import socket
import ssl
import string
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

from v2.toolkit.dns_light import normalized_toolkit_host

MAX_INPUT_CHARS = 12_000
DEFAULT_TIMEOUT = 6.0


# ---------------------------------------------------------------------------
# Hash & encoding helpers
# ---------------------------------------------------------------------------

def sha1_hex(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def sha512_hex(text: str) -> str:
    return hashlib.sha512(text.encode("utf-8")).hexdigest()


def url_encode(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def url_decode(text: str) -> tuple[bool, str]:
    try:
        return True, urllib.parse.unquote(text)
    except Exception as exc:  # pragma: no cover - extremely rare
        return False, str(exc)


def jwt_decode(token: str) -> tuple[bool, str]:
    """Decode header + payload of a JWT (no signature verification)."""
    token = (token or "").strip()
    parts = token.split(".")
    if len(parts) < 2:
        return False, "JWT format invalid (need at least header.payload)."

    def _b64(seg: str) -> str:
        pad = (-len(seg)) % 4
        try:
            raw = base64.urlsafe_b64decode(seg + ("=" * pad))
            return raw.decode("utf-8", errors="replace")
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError(str(exc))

    try:
        header = _b64(parts[0])
        payload = _b64(parts[1])
    except RuntimeError as exc:
        return False, f"base64 decode failed: {exc}"

    try:
        header_obj = json.loads(header)
        payload_obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        return False, f"JSON parse failed: {exc}"

    out = {
        "header": header_obj,
        "payload": payload_obj,
        "signature_present": len(parts) >= 3 and bool(parts[2]),
    }
    return True, json.dumps(out, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def to_upper(text: str) -> str:
    return text.upper()


def to_lower(text: str) -> str:
    return text.lower()


def to_title(text: str) -> str:
    return text.title()


def reverse_text(text: str) -> str:
    return text[::-1]


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    base = text.lower().strip()
    return _SLUG_RE.sub("-", base).strip("-") or "slug"


def count_text(text: str) -> str:
    chars = len(text)
    chars_no_ws = len(re.sub(r"\s+", "", text))
    words = len([w for w in re.split(r"\s+", text.strip()) if w])
    lines = text.count("\n") + (1 if text else 0)
    return (
        f"chars: {chars}\n"
        f"chars (no spaces): {chars_no_ws}\n"
        f"words: {words}\n"
        f"lines: {lines}"
    )


def clean_whitespace(text: str) -> str:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_uuid() -> str:
    import uuid

    return str(uuid.uuid4())


_PWD_AMBIGUOUS = "0O1lI|`'\""


def generate_password(length: int = 20, *, include_symbols: bool = True) -> str:
    length = max(8, min(int(length), 128))
    alphabet = string.ascii_letters + string.digits
    if include_symbols:
        alphabet += "!@#$%^&*()-_=+[]{}<>?"
    alphabet = "".join(ch for ch in alphabet if ch not in _PWD_AMBIGUOUS)
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_token_hex(nbytes: int = 16) -> str:
    nbytes = max(4, min(int(nbytes), 64))
    return secrets.token_hex(nbytes)


def random_number(lo: int = 0, hi: int = 100) -> str:
    if hi < lo:
        lo, hi = hi, lo
    return str(secrets.choice(range(lo, hi + 1)))


_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
    "nisi ut aliquip ex ea commodo consequat."
)


def lorem_ipsum(n_paragraphs: int = 2) -> str:
    n = max(1, min(int(n_paragraphs), 6))
    return "\n\n".join([_LOREM] * n)


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def ts_to_date(ts: str) -> tuple[bool, str]:
    raw = (ts or "").strip()
    if not raw:
        return False, "empty"
    try:
        ts_int = int(float(raw))
    except ValueError:
        return False, "not a number"
    if abs(ts_int) > 4_000_000_000_000:  # likely ms
        ts_int = ts_int // 1000
    try:
        dt_utc = datetime.fromtimestamp(ts_int, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        return False, str(exc)
    tehran = dt_utc.astimezone(timezone(timedelta(hours=3, minutes=30)))
    return True, (
        f"UTC : {dt_utc.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        f"Tehran: {tehran.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        f"ISO : {dt_utc.isoformat()}"
    )


def date_to_ts(text: str) -> tuple[bool, str]:
    raw = (text or "").strip()
    if not raw:
        return False, "empty"
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return True, str(int(dt.replace(tzinfo=timezone.utc).timestamp()))
        except ValueError:
            continue
    return False, "unrecognized date format"


def now_panel(timezone_label: str = "Asia/Tehran") -> str:
    now_utc = datetime.now(timezone.utc)
    tehran = now_utc.astimezone(timezone(timedelta(hours=3, minutes=30)))
    return (
        f"UTC : {now_utc.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        f"Tehran: {tehran.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        f"Unix: {int(now_utc.timestamp())}\n"
        f"Day of week (UTC): {now_utc.strftime('%A')}"
    )


def base_convert(text: str) -> tuple[bool, str]:
    raw = (text or "").strip().lower()
    if not raw:
        return False, "empty"
    base = 10
    value = raw
    if raw.startswith("0x"):
        base, value = 16, raw[2:]
    elif raw.startswith("0b"):
        base, value = 2, raw[2:]
    elif raw.startswith("0o"):
        base, value = 8, raw[2:]
    try:
        n = int(value, base)
    except ValueError:
        return False, "invalid number"
    return True, (
        f"dec: {n}\n"
        f"hex: 0x{n:x}\n"
        f"oct: 0o{n:o}\n"
        f"bin: 0b{n:b}"
    )


def color_convert(text: str) -> tuple[bool, str]:
    raw = (text or "").strip().lower().lstrip("#")
    if not raw:
        return False, "empty"
    if re.fullmatch(r"[0-9a-f]{6}", raw):
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        return True, f"#{raw}\nrgb({r}, {g}, {b})\nrgb({r/255:.2f}, {g/255:.2f}, {b/255:.2f})"
    parts = re.split(r"[,\s]+", raw.replace("rgb(", "").replace(")", ""))
    parts = [p for p in parts if p]
    if len(parts) == 3:
        try:
            r, g, b = (max(0, min(255, int(p))) for p in parts)
        except ValueError:
            return False, "invalid rgb"
        return True, f"#{r:02x}{g:02x}{b:02x}\nrgb({r}, {g}, {b})"
    return False, "use #hex (6 digits) or 'r,g,b'"


def json_format(text: str) -> tuple[bool, str]:
    raw = (text or "").strip()
    if not raw:
        return False, "empty"
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    return True, json.dumps(obj, ensure_ascii=False, indent=2)


_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(b|kb|mb|gb|tb|kib|mib|gib|tib)?\s*$", re.IGNORECASE)
_SIZE_MULT = {
    None: 1,
    "b": 1,
    "kb": 1000, "mb": 1000**2, "gb": 1000**3, "tb": 1000**4,
    "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4,
}


def size_convert(text: str) -> tuple[bool, str]:
    m = _SIZE_RE.match(text or "")
    if not m:
        return False, "use e.g. '500 MB' or '1.5 GiB'"
    value = float(m.group(1))
    unit = (m.group(2) or "").lower() or None
    bytes_ = int(value * _SIZE_MULT[unit])
    return True, (
        f"bytes : {bytes_}\n"
        f"KB    : {bytes_/1000:.3f}\n"
        f"MB    : {bytes_/1000**2:.3f}\n"
        f"GB    : {bytes_/1000**3:.3f}\n"
        f"KiB   : {bytes_/1024:.3f}\n"
        f"MiB   : {bytes_/1024**2:.3f}\n"
        f"GiB   : {bytes_/1024**3:.3f}"
    )


# ---------------------------------------------------------------------------
# Network tools
# ---------------------------------------------------------------------------

def reverse_dns(host_or_ip: str) -> tuple[bool, str]:
    raw = (host_or_ip or "").strip()
    if not raw:
        return False, "empty"
    try:
        ipaddress.ip_address(raw)
        target = raw
    except ValueError:
        host = normalized_toolkit_host(raw)
        if not host:
            return False, "invalid hostname/ip"
        try:
            target = socket.gethostbyname(host)
        except OSError as exc:
            return False, str(exc)
    try:
        hostname, aliases, _ = socket.gethostbyaddr(target)
    except OSError as exc:
        return False, str(exc)
    body = hostname
    if aliases:
        body += "\n" + "\n".join(aliases)
    return True, f"{target} ->\n{body}"


def port_check(host: str, port: int, *, timeout: float = 4.0) -> tuple[bool, str]:
    h = normalized_toolkit_host(host)
    if not h:
        return False, "invalid hostname"
    try:
        port = int(port)
    except (TypeError, ValueError):
        return False, "invalid port"
    if not (1 <= port <= 65535):
        return False, "port out of range"
    t0 = time.time()
    try:
        with socket.create_connection((h, port), timeout=float(timeout)):
            ms = (time.time() - t0) * 1000
            return True, f"open ({ms:.0f} ms)"
    except (socket.timeout, OSError) as exc:
        return False, f"closed/filtered: {exc}"


def ssl_info(host: str, port: int = 443, *, timeout: float = 6.0) -> tuple[bool, str]:
    h = normalized_toolkit_host(host)
    if not h:
        return False, "invalid hostname"
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((h, int(port)), timeout=float(timeout)) as sock:
            with ctx.wrap_socket(sock, server_hostname=h) as ssock:
                cert = ssock.getpeercert()
    except (socket.timeout, OSError, ssl.SSLError) as exc:
        return False, str(exc)
    subject = ", ".join("/".join(f"{k}={v}" for k, v in part) for part in cert.get("subject", []))
    issuer = ", ".join("/".join(f"{k}={v}" for k, v in part) for part in cert.get("issuer", []))
    not_after = cert.get("notAfter", "?")
    not_before = cert.get("notBefore", "?")
    try:
        exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        days_left = (exp - datetime.utcnow()).days
        exp_line = f"expires: {not_after} ({days_left} days)"
    except ValueError:
        exp_line = f"expires: {not_after}"
    sans = cert.get("subjectAltName", [])
    san_line = ", ".join(v for _, v in sans[:10]) or "—"
    return True, (
        f"host  : {h}:{port}\n"
        f"subject: {subject or '—'}\n"
        f"issuer : {issuer or '—'}\n"
        f"valid from: {not_before}\n"
        f"{exp_line}\n"
        f"SAN: {san_line}"
    )


def http_headers(url: str, *, timeout: float = 8.0) -> tuple[bool, str]:
    raw = (url or "").strip()
    if not raw.lower().startswith(("http://", "https://")):
        return False, "use a full http(s) URL"
    try:
        req = urllib.request.Request(raw, method="HEAD", headers={"User-Agent": "telegramtorubika/1"})
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            status = r.status
            headers = list(r.headers.items())
    except Exception as exc:
        try:
            req = urllib.request.Request(raw, headers={"User-Agent": "telegramtorubika/1"})
            with urllib.request.urlopen(req, timeout=float(timeout)) as r:
                status = r.status
                headers = list(r.headers.items())
        except Exception as exc2:
            return False, str(exc2)
    lines = [f"HTTP {status}"]
    for k, v in headers[:30]:
        lines.append(f"{k}: {v}")
    return True, "\n".join(lines)


def ip_geo(ip_or_host: str, *, timeout: float = 6.0) -> tuple[bool, str]:
    raw = (ip_or_host or "").strip()
    if not raw:
        return False, "empty"
    try:
        ipaddress.ip_address(raw)
        target = raw
    except ValueError:
        h = normalized_toolkit_host(raw)
        if not h:
            return False, "invalid host"
        try:
            target = socket.gethostbyname(h)
        except OSError as exc:
            return False, str(exc)
    try:
        req = urllib.request.Request(
            f"https://ipapi.co/{target}/json/",
            headers={"User-Agent": "telegramtorubika/1"},
        )
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            body = r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return False, str(exc)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False, "bad response"
    if data.get("error"):
        return False, data.get("reason", "lookup failed")
    out = []
    for k in (
        "ip", "city", "region", "country_name", "country_code",
        "org", "asn", "timezone", "latitude", "longitude",
    ):
        if data.get(k) not in (None, ""):
            out.append(f"{k}: {data[k]}")
    return True, "\n".join(out) or "no data"


def whois_lookup(host: str, *, timeout: float = 8.0) -> tuple[bool, str]:
    """Very small whois TCP query (port 43) against IANA + TLD whois server."""
    h = normalized_toolkit_host(host)
    if not h:
        return False, "invalid domain"
    iana = "whois.iana.org"
    try:
        sock = socket.create_connection((iana, 43), timeout=float(timeout))
        sock.sendall((h + "\r\n").encode("ascii"))
        body = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            body += chunk
        sock.close()
        text = body.decode("utf-8", errors="replace")
    except (socket.timeout, OSError) as exc:
        return False, str(exc)
    referral = ""
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("refer:") or low.startswith("whois:"):
            referral = line.split(":", 1)[1].strip()
            break
    if not referral:
        snippet = "\n".join(text.splitlines()[:25])
        return True, snippet or "no data"
    try:
        sock = socket.create_connection((referral, 43), timeout=float(timeout))
        sock.sendall((h + "\r\n").encode("ascii"))
        body = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            body += chunk
        sock.close()
        text = body.decode("utf-8", errors="replace")
    except (socket.timeout, OSError) as exc:
        return False, f"referral '{referral}' failed: {exc}"
    snippet_lines = []
    for line in text.splitlines():
        if line.strip().startswith("%") or not line.strip():
            continue
        snippet_lines.append(line)
        if len(snippet_lines) >= 25:
            break
    return True, "\n".join(snippet_lines) or text[:1000]


# ---------------------------------------------------------------------------
# Tiny calculator (safe)
# ---------------------------------------------------------------------------

_SAFE_CALC = re.compile(r"^[\d\s\.\+\-\*\/\(\)\%\^]+$")


def safe_calc(expr: str) -> tuple[bool, str]:
    raw = (expr or "").strip().replace("^", "**")
    if not raw:
        return False, "empty"
    if not _SAFE_CALC.match(raw.replace("**", "")):
        return False, "only digits and + - * / ( ) % ^ allowed"
    try:
        # eval is constrained by the regex above; no names or function calls allowed.
        value = eval(raw, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:
        return False, str(exc)
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return False, "non-finite result"
        return True, f"{value:g}"
    return True, str(value)
