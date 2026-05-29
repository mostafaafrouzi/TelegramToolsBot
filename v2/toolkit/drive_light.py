"""Google Drive connect helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path


_FOLDER_RE = re.compile(r"drive\.google\.com/drive(?:/u/\d+)?/folders/([a-zA-Z0-9_-]+)")
_OPEN_RE = re.compile(r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)")
_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,}$")


def extract_folder_id(text: str) -> str:
    """Accept raw folder ID or full Google Drive folder URL."""
    raw = (text or "").strip()
    if not raw:
        return ""
    m = _FOLDER_RE.search(raw) or _OPEN_RE.search(raw)
    if m:
        return m.group(1)
    if _ID_RE.match(raw):
        return raw
    return raw


def service_account_email(json_path: Path) -> str:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return str(data.get("client_email") or "").strip()
    except (OSError, json.JSONDecodeError):
        return ""
