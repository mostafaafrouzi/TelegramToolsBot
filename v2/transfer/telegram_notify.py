"""Send files/messages to Telegram chat from worker (uses BOT_TOKEN)."""

from __future__ import annotations

import os
from pathlib import Path

import requests

TG_API = "https://api.telegram.org"


def send_document(
    chat_id: int,
    file_path: str | Path,
    *,
    caption: str = "",
    reply_to_message_id: int | None = None,
    timeout: int = 300,
) -> tuple[bool, str]:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        return False, "BOT_TOKEN missing"
    path = Path(file_path)
    if not path.is_file():
        return False, "file not found"
    data: dict = {"chat_id": int(chat_id)}
    if caption:
        data["caption"] = caption[:1024]
    if reply_to_message_id:
        data["reply_to_message_id"] = int(reply_to_message_id)
    try:
        with path.open("rb") as fh:
            r = requests.post(
                f"{TG_API}/bot{token}/sendDocument",
                data=data,
                files={"document": (path.name, fh)},
                timeout=timeout,
            )
        body = r.json() if r.content else {}
        if r.ok and body.get("ok"):
            return True, "ok"
        return False, str(body.get("description") or r.text)[:900]
    except requests.RequestException as e:
        return False, str(e)[:900]
