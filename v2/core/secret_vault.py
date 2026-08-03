"""At-rest secret wrapping for SQLite token/password columns.

Uses Fernet when ``cryptography`` is installed; otherwise a HMAC-sealed XOR
fallback (still better than plaintext). Key from ``SECRET_VAULT_KEY`` or
derived from ``BOT_TOKEN``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

_PREFIX_FERNET = "enc:f1:"
_PREFIX_XOR = "enc:x1:"


def _raw_key_material() -> bytes:
    raw = (os.getenv("SECRET_VAULT_KEY") or os.getenv("BOT_TOKEN") or "tele2rub-dev-key").strip()
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _fernet():
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except Exception:
        return None
    key = base64.urlsafe_b64encode(_raw_key_material())
    return Fernet(key)


def seal(plain: Optional[str]) -> str:
    text = (plain or "").strip()
    if not text:
        return ""
    if text.startswith((_PREFIX_FERNET, _PREFIX_XOR)):
        return text
    f = _fernet()
    if f is not None:
        token = f.encrypt(text.encode("utf-8")).decode("ascii")
        return _PREFIX_FERNET + token
    key = _raw_key_material()
    data = text.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    mac = hmac.new(key, xored, hashlib.sha256).digest()[:16]
    blob = base64.urlsafe_b64encode(mac + xored).decode("ascii")
    return _PREFIX_XOR + blob


def open_secret(stored: Optional[str]) -> str:
    text = (stored or "").strip()
    if not text:
        return ""
    if text.startswith(_PREFIX_FERNET):
        f = _fernet()
        if f is None:
            return ""
        try:
            return f.decrypt(text[len(_PREFIX_FERNET) :].encode("ascii")).decode("utf-8")
        except Exception:
            return ""
    if text.startswith(_PREFIX_XOR):
        key = _raw_key_material()
        try:
            raw = base64.urlsafe_b64decode(text[len(_PREFIX_XOR) :].encode("ascii"))
            mac, xored = raw[:16], raw[16:]
            expect = hmac.new(key, xored, hashlib.sha256).digest()[:16]
            if not hmac.compare_digest(mac, expect):
                return ""
            return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode("utf-8")
        except Exception:
            return ""
    # Legacy plaintext
    return text
