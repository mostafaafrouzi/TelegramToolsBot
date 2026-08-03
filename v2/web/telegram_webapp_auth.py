"""Validate Telegram Mini App ``initData`` (HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import Any, Optional


def validate_init_data(
    init_data: str,
    *,
    bot_token: Optional[str] = None,
    max_age_sec: int = 86400,
) -> tuple[bool, dict[str, Any]]:
    """
    Returns ``(ok, payload)``. On success payload includes ``user`` dict when present.
    """
    token = (bot_token or os.getenv("BOT_TOKEN") or "").strip()
    raw = (init_data or "").strip()
    if not token or not raw:
        return False, {"error": "missing_init_data_or_token"}

    parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
    received_hash = (parsed.get("hash") or [""])[0]
    if not received_hash:
        return False, {"error": "missing_hash"}

    pairs = []
    for key, values in parsed.items():
        if key == "hash":
            continue
        pairs.append(f"{key}={values[0]}")
    pairs.sort()
    data_check = "\n".join(pairs)

    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    calc = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        return False, {"error": "bad_hash"}

    auth_date_s = (parsed.get("auth_date") or ["0"])[0]
    try:
        auth_date = int(auth_date_s)
    except ValueError:
        return False, {"error": "bad_auth_date"}
    if max_age_sec > 0 and abs(int(time.time()) - auth_date) > max_age_sec:
        return False, {"error": "expired"}

    out: dict[str, Any] = {"auth_date": auth_date}
    user_raw = (parsed.get("user") or [""])[0]
    if user_raw:
        try:
            out["user"] = json.loads(user_raw)
        except json.JSONDecodeError:
            out["user_raw"] = user_raw
    return True, out
