"""Bale Bot API client (Telegram-compatible send methods on tapi.bale.ai)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests

BALE_API_BASE = (os.getenv("BALE_API_BASE") or "https://tapi.bale.ai").rstrip("/")
BALE_MAX_BYTES = int(os.getenv("BALE_MAX_FILE_MB") or "20") * 1024 * 1024


def _api_url(token: str, method: str) -> str:
    return f"{BALE_API_BASE}/bot{token}/{method}"


def send_document(
    token: str,
    chat_id: str,
    file_path: str | Path,
    *,
    caption: str = "",
    timeout: int = 300,
) -> tuple[bool, str]:
    """Upload a file to Bale chat. Returns ``(ok, message_or_file_id)``."""
    path = Path(file_path)
    if not path.is_file():
        return False, "file not found"
    size = path.stat().st_size
    if size > BALE_MAX_BYTES:
        return False, f"file exceeds Bale limit ({BALE_MAX_BYTES // (1024 * 1024)} MB)"
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]
    try:
        with path.open("rb") as fh:
            r = requests.post(
                _api_url(token, "sendDocument"),
                data=data,
                files={"document": (path.name, fh)},
                timeout=timeout,
            )
        body = r.json() if r.content else {}
        if r.ok and body.get("ok"):
            fid = ""
            try:
                fid = body["result"]["document"]["file_id"]
            except (KeyError, TypeError):
                fid = "ok"
            return True, str(fid)
        desc = body.get("description") or r.text or f"HTTP {r.status_code}"
        return False, str(desc)[:900]
    except requests.RequestException as e:
        return False, str(e)[:900]


def send_photo(
    token: str,
    chat_id: str,
    file_path: str | Path,
    *,
    caption: str = "",
    timeout: int = 300,
) -> tuple[bool, str]:
    path = Path(file_path)
    if not path.is_file():
        return False, "file not found"
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]
    try:
        with path.open("rb") as fh:
            r = requests.post(
                _api_url(token, "sendPhoto"),
                data=data,
                files={"photo": (path.name, fh)},
                timeout=timeout,
            )
        body = r.json() if r.content else {}
        if r.ok and body.get("ok"):
            return True, "ok"
        desc = body.get("description") or r.text or f"HTTP {r.status_code}"
        return False, str(desc)[:900]
    except requests.RequestException as e:
        return False, str(e)[:900]


def send_file_auto(
    token: str,
    chat_id: str,
    file_path: str | Path,
    *,
    caption: str = "",
    mime_hint: Optional[str] = None,
) -> tuple[bool, str]:
    """Pick sendPhoto for common images, else sendDocument."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        ok, msg = send_photo(token, chat_id, path, caption=caption)
        if ok:
            return ok, msg
    return send_document(token, chat_id, path, caption=caption)
