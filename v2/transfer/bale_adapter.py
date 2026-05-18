"""Bale messenger transfer adapter (per-user bot token; see docs/v2/05)."""

from __future__ import annotations

import os
from typing import Any, Optional


class BaleTransferAdapter:
    def validate_account(self, user_ctx: dict) -> bool:
        token = (user_ctx.get("bale_bot_token") or "").strip()
        if not token:
            token = (os.getenv("BALE_BOT_TOKEN") or "").strip()
        return bool(token and user_ctx.get("bale_chat_id"))

    def healthcheck(self, bot_token: Optional[str] = None) -> tuple[bool, str]:
        from v2.transfer.bale_client import validate_bot_token

        token = (bot_token or os.getenv("BALE_BOT_TOKEN") or "").strip()
        if not token:
            return False, "Bale bot token not set for this user"
        ok, detail = validate_bot_token(token)
        if ok:
            return True, f"@{detail}" if detail and detail != "ok" else "token OK"
        return False, detail

    def resolve_source(self, task: dict) -> Any:
        return task.get("source", {})

    def download(self, source_ref: Any, tmp_path: str) -> dict:
        return {"ok": False, "error": "bale_download_not_implemented"}

    def upload(self, local_path: str, destination_ref: Any) -> dict:
        token = ""
        chat_id = ""
        if isinstance(destination_ref, dict):
            token = str(destination_ref.get("bot_token") or destination_ref.get("token") or "").strip()
            chat_id = str(destination_ref.get("chat_id") or "")
        if not token:
            token = (os.getenv("BALE_BOT_TOKEN") or "").strip()
        if not token or not chat_id:
            return {"ok": False, "error": "bale_token_or_chat_missing"}
        from v2.transfer.bale_client import send_file_auto

        caption = ""
        if isinstance(destination_ref, dict):
            caption = str(destination_ref.get("caption") or "")
        ok, msg = send_file_auto(token, chat_id, local_path, caption=caption)
        return {"ok": ok, "provider_id": msg if ok else "", "error": "" if ok else msg}
