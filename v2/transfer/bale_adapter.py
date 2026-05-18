"""Bale messenger transfer adapter (MVP stub; see docs/v2/05-transfer-adapters-spec.md §4.3)."""

from __future__ import annotations

import os
from typing import Any


class BaleTransferAdapter:
    """Token-based Bale bot path. Full bridge wired in worker backlog."""

    def validate_account(self, user_ctx: dict) -> bool:
        if not (os.getenv("BALE_BOT_TOKEN") or "").strip():
            return False
        return bool(user_ctx.get("bale_chat_id"))

    def healthcheck(self) -> tuple[bool, str]:
        if not (os.getenv("BALE_BOT_TOKEN") or "").strip():
            return False, "BALE_BOT_TOKEN not set on server"
        return True, "Bale bot token present (upload bridge: post-MVP worker hook)"

    def resolve_source(self, task: dict) -> Any:
        return task.get("source", {})

    def download(self, source_ref: Any, tmp_path: str) -> dict:
        return {"ok": False, "error": "bale_download_not_implemented"}

    def upload(self, local_path: str, destination_ref: Any) -> dict:
        token = (os.getenv("BALE_BOT_TOKEN") or "").strip()
        chat_id = ""
        if isinstance(destination_ref, dict):
            chat_id = str(destination_ref.get("chat_id") or "")
        if not token or not chat_id:
            return {"ok": False, "error": "bale_token_or_chat_missing"}
        from v2.transfer.bale_client import send_file_auto

        caption = ""
        if isinstance(destination_ref, dict):
            caption = str(destination_ref.get("caption") or "")
        ok, msg = send_file_auto(token, chat_id, local_path, caption=caption)
        return {"ok": ok, "provider_id": msg if ok else "", "error": "" if ok else msg}
